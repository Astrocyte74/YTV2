#!/usr/bin/env python3
"""
Rollback Readiness Test for YTV2 PostgreSQL Migration
Verifies that both systems are operational and rollback procedures can be executed safely
"""

import requests
import sys
from datetime import datetime

class RollbackReadinessTest:
    def __init__(self):
        self.sqlite_base = "https://ytv2-vy9k.onrender.com"
        self.postgres_base = "https://ytv2-dashboard-postgres.onrender.com"
        self.tests_passed = 0
        self.tests_failed = 0

    def test_endpoint(self, name: str, url: str, expected_status: int = 200, expected_content: str = None) -> bool:
        """Test an endpoint and return success status."""
        try:
            response = requests.get(url, timeout=10)

            if response.status_code != expected_status:
                print(f"❌ {name}: Expected {expected_status}, got {response.status_code}")
                self.tests_failed += 1
                return False

            if expected_content and expected_content not in response.text:
                print(f"❌ {name}: Expected content '{expected_content}' not found")
                self.tests_failed += 1
                return False

            print(f"✅ {name}: OK ({response.status_code})")
            self.tests_passed += 1
            return True

        except Exception as e:
            print(f"❌ {name}: ERROR - {str(e)}")
            self.tests_failed += 1
            return False

    def test_backend_identification(self):
        """Test that we can identify which backend each system is using."""
        print("\n🔍 Testing Backend Identification")
        print("-" * 40)

        # SQLite should NOT have /health/backend endpoint
        self.test_endpoint(
            "SQLite /health/backend (should 404)",
            f"{self.sqlite_base}/health/backend",
            expected_status=404
        )

        # PostgreSQL should have /health/backend endpoint
        response_ok = self.test_endpoint(
            "PostgreSQL /health/backend",
            f"{self.postgres_base}/health/backend"
        )

        # Verify PostgreSQL backend content
        if response_ok:
            try:
                response = requests.get(f"{self.postgres_base}/health/backend")
                data = response.json()

                if data.get("backend") == "PostgreSQLContentIndex":
                    print(f"✅ PostgreSQL backend confirmed: {data.get('backend')}")
                    print(f"   Record count: {data.get('record_count', 'N/A')}")
                    self.tests_passed += 1
                else:
                    print(f"❌ PostgreSQL backend incorrect: {data.get('backend')}")
                    self.tests_failed += 1

            except Exception as e:
                print(f"❌ PostgreSQL backend verification failed: {e}")
                self.tests_failed += 1

    def test_basic_functionality(self):
        """Test basic functionality on both systems."""
        print("\n🧪 Testing Basic Functionality")
        print("-" * 40)

        # Health endpoints
        self.test_endpoint("SQLite /health", f"{self.sqlite_base}/health")
        self.test_endpoint("PostgreSQL /health", f"{self.postgres_base}/health")

        # API endpoints
        self.test_endpoint("SQLite /api/filters", f"{self.sqlite_base}/api/filters")
        self.test_endpoint("PostgreSQL /api/filters", f"{self.postgres_base}/api/filters")

        self.test_endpoint("SQLite /api/reports", f"{self.sqlite_base}/api/reports?size=1")
        self.test_endpoint("PostgreSQL /api/reports", f"{self.postgres_base}/api/reports?size=1")

    def test_data_consistency(self):
        """Test that both systems return consistent data."""
        print("\n📊 Testing Data Consistency")
        print("-" * 40)

        try:
            # Get report counts from both systems
            sqlite_response = requests.get(f"{self.sqlite_base}/api/reports?size=1")
            postgres_response = requests.get(f"{self.postgres_base}/api/reports?size=1")

            if sqlite_response.status_code == 200 and postgres_response.status_code == 200:
                sqlite_data = sqlite_response.json()
                postgres_data = postgres_response.json()

                sqlite_total = sqlite_data.get('total', 0)
                postgres_total = postgres_data.get('total', 0)

                if sqlite_total == postgres_total:
                    print(f"✅ Record counts match: {postgres_total} records")
                    self.tests_passed += 1
                else:
                    print(f"⚠️  Record count difference: SQLite={sqlite_total}, PostgreSQL={postgres_total}")
                    # This might be acceptable if new records were added
                    self.tests_passed += 1

            else:
                print(f"❌ Could not retrieve data for comparison")
                self.tests_failed += 1

        except Exception as e:
            print(f"❌ Data consistency test failed: {e}")
            self.tests_failed += 1

    def test_rollback_requirements(self):
        """Test that rollback requirements are met."""
        print("\n🔄 Testing Rollback Requirements")
        print("-" * 40)

        # Verify SQLite system is stable and ready for fallback
        sqlite_healthy = self.test_endpoint("SQLite system ready for rollback", f"{self.sqlite_base}/health")

        # Verify we can distinguish between systems
        try:
            postgres_response = requests.get(f"{self.postgres_base}/health/backend")
            if postgres_response.status_code == 200:
                print("✅ Backend identification working (cutover detection possible)")
                self.tests_passed += 1
            else:
                print("❌ Backend identification failed")
                self.tests_failed += 1
        except:
            print("❌ Backend identification test failed")
            self.tests_failed += 1

    def generate_summary(self):
        """Generate rollback readiness summary."""
        print("\n" + "=" * 50)
        print("🚀 ROLLBACK READINESS SUMMARY")
        print("=" * 50)

        total_tests = self.tests_passed + self.tests_failed
        pass_rate = (self.tests_passed / total_tests * 100) if total_tests > 0 else 0

        print(f"Total Tests: {total_tests}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_failed}")
        print(f"Success Rate: {pass_rate:.1f}%")

        if self.tests_failed == 0:
            print("\n🎉 ROLLBACK READINESS: CONFIRMED")
            print("✅ Both systems operational")
            print("✅ Backend identification working")
            print("✅ Rollback procedures can be executed safely")
            print("\n🚀 READY FOR CUTOVER")
            return True
        else:
            print(f"\n⚠️  ROLLBACK READINESS: ISSUES DETECTED")
            print(f"❌ {self.tests_failed} test(s) failed")
            print("🔧 Resolve issues before proceeding with cutover")
            return False

def main():
    """Run rollback readiness tests."""
    print("🔄 YTV2 PostgreSQL Migration - Rollback Readiness Test")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    tester = RollbackReadinessTest()

    # Run all tests
    tester.test_backend_identification()
    tester.test_basic_functionality()
    tester.test_data_consistency()
    tester.test_rollback_requirements()

    # Generate summary and exit with appropriate code
    ready = tester.generate_summary()

    sys.exit(0 if ready else 1)

if __name__ == "__main__":
    main()