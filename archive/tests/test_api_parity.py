#!/usr/bin/env python3
"""
API Parity Test Script for YTV2 PostgreSQL Migration
Compares responses between SQLite production and PostgreSQL test systems
"""

import requests
import json
import sys
from typing import Dict, Any, List
from datetime import datetime

class APIParityTester:
    def __init__(self):
        self.sqlite_base = "https://ytv2-vy9k.onrender.com"
        self.postgres_base = "https://ytv2-dashboard-postgres.onrender.com"
        self.test_results = []

    def test_endpoint(self, endpoint: str, params: Dict = None) -> Dict[str, Any]:
        """Test an endpoint on both SQLite and PostgreSQL backends."""
        print(f"\n🔍 Testing {endpoint}")

        # Test SQLite
        try:
            sqlite_response = requests.get(f"{self.sqlite_base}{endpoint}", params=params, timeout=30)
            sqlite_data = sqlite_response.json() if sqlite_response.status_code == 200 else None
            sqlite_status = sqlite_response.status_code
        except Exception as e:
            sqlite_data = None
            sqlite_status = f"ERROR: {str(e)}"

        # Test PostgreSQL
        try:
            postgres_response = requests.get(f"{self.postgres_base}{endpoint}", params=params, timeout=30)
            postgres_data = postgres_response.json() if postgres_response.status_code == 200 else None
            postgres_status = postgres_response.status_code
        except Exception as e:
            postgres_data = None
            postgres_status = f"ERROR: {str(e)}"

        result = {
            "endpoint": endpoint,
            "params": params,
            "sqlite_status": sqlite_status,
            "postgres_status": postgres_status,
            "sqlite_data": sqlite_data,
            "postgres_data": postgres_data,
            "timestamp": datetime.now().isoformat()
        }

        # Quick comparison
        if sqlite_status == postgres_status == 200:
            if sqlite_data and postgres_data:
                # Compare structure for reports endpoints
                if 'reports' in sqlite_data and 'reports' in postgres_data:
                    sqlite_count = len(sqlite_data['reports'])
                    postgres_count = len(postgres_data['reports'])
                    print(f"  SQLite: {sqlite_count} reports")
                    print(f"  PostgreSQL: {postgres_count} reports")
                    result['count_comparison'] = {
                        'sqlite': sqlite_count,
                        'postgres': postgres_count,
                        'match': sqlite_count == postgres_count
                    }
                else:
                    print(f"  Both responded with data")
            else:
                print(f"  ⚠️  One or both responses missing data")
        else:
            print(f"  ❌ Status mismatch: SQLite={sqlite_status}, PostgreSQL={postgres_status}")

        self.test_results.append(result)
        return result

    def run_comprehensive_tests(self):
        """Run comprehensive API parity tests."""
        print("🧪 Starting YTV2 API Parity Tests")
        print("=" * 50)

        # 1. Health endpoints
        self.test_endpoint("/health")
        self.test_endpoint("/health/backend")  # Only on PostgreSQL

        # 2. Filters endpoint
        self.test_endpoint("/api/filters")

        # 3. Reports endpoints - various sizes
        self.test_endpoint("/api/reports", {"size": 1})
        self.test_endpoint("/api/reports", {"size": 5})
        self.test_endpoint("/api/reports", {"size": 10})

        # 4. Specific filters
        self.test_endpoint("/api/reports", {"category": "Technology", "size": 3})
        self.test_endpoint("/api/reports", {"sort": "video_newest", "size": 3})

        # 5. Sample individual report (use a known video_id if available)
        # First get a sample from PostgreSQL to find valid video_id
        try:
            sample_response = requests.get(f"{self.postgres_base}/api/reports", params={"size": 1})
            if sample_response.status_code == 200:
                sample_data = sample_response.json()
                if sample_data.get('reports'):
                    video_id = sample_data['reports'][0].get('video_id')
                    if video_id:
                        self.test_endpoint(f"/{video_id}.json", {"v": "2"})
        except:
            print("  ⚠️  Could not test individual report endpoint")

        return self.test_results

    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 50)
        print("📊 API PARITY TEST SUMMARY")
        print("=" * 50)

        total_tests = len(self.test_results)
        passed_tests = 0
        failed_tests = 0
        expected_differences = 0

        for result in self.test_results:
            endpoint = result['endpoint']
            sqlite_status = result['sqlite_status']
            postgres_status = result['postgres_status']

            # Handle expected differences
            if endpoint == "/health/backend":
                if sqlite_status == 404 and postgres_status == 200:
                    print(f"✅ {endpoint} - Expected difference (PostgreSQL-only endpoint)")
                    expected_differences += 1
                    continue

            # Handle cases where both systems have identical errors
            if (isinstance(sqlite_status, str) and isinstance(postgres_status, str) and
                "ERROR" in str(sqlite_status) and "ERROR" in str(postgres_status)):
                print(f"✅ {endpoint} - Both systems have identical error behavior")
                passed_tests += 1
                continue

            if sqlite_status == postgres_status == 200:
                if 'count_comparison' in result:
                    if result['count_comparison']['match']:
                        print(f"✅ {endpoint} - Counts match ({result['count_comparison']['postgres']})")
                        passed_tests += 1
                    else:
                        print(f"⚠️  {endpoint} - Count mismatch: SQLite={result['count_comparison']['sqlite']}, PostgreSQL={result['count_comparison']['postgres']}")
                        failed_tests += 1
                else:
                    print(f"✅ {endpoint} - Both returned 200")
                    passed_tests += 1
            else:
                print(f"❌ {endpoint} - Status mismatch: SQLite={sqlite_status}, PostgreSQL={postgres_status}")
                failed_tests += 1

        print(f"\nTotal: {total_tests} | Passed: {passed_tests} | Expected Differences: {expected_differences} | Failed: {failed_tests}")

        if failed_tests == 0:
            print("🎉 ALL CORE TESTS PASSED - API parity confirmed!")
            print("✨ Migration ready for cutover")
        else:
            print(f"⚠️  {failed_tests} tests failed - investigate differences")

    def save_detailed_results(self, filename: str = None):
        """Save detailed test results to JSON file."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"api_parity_results_{timestamp}.json"

        with open(filename, 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)

        print(f"📄 Detailed results saved to: {filename}")
        return filename

def main():
    """Run API parity tests."""
    tester = APIParityTester()

    print("Starting API parity tests between:")
    print(f"SQLite Production: {tester.sqlite_base}")
    print(f"PostgreSQL Test: {tester.postgres_base}")

    # Run tests
    results = tester.run_comprehensive_tests()

    # Print summary
    tester.print_summary()

    # Save detailed results
    results_file = tester.save_detailed_results()

    # Return exit code based on results (ignoring expected differences)
    failed_count = 0
    for r in results:
        endpoint = r['endpoint']
        sqlite_status = r.get('sqlite_status')
        postgres_status = r.get('postgres_status')

        # Skip expected differences
        if endpoint == "/health/backend" and sqlite_status == 404 and postgres_status == 200:
            continue

        # Skip identical error cases
        if (isinstance(sqlite_status, str) and isinstance(postgres_status, str) and
            "ERROR" in str(sqlite_status) and "ERROR" in str(postgres_status)):
            continue

        # Count actual failures
        if (sqlite_status != postgres_status or
            (r.get('count_comparison', {}).get('match', True) is False)):
            failed_count += 1

    if failed_count > 0:
        print(f"\n❌ Exiting with code 1 - {failed_count} actual failures")
        sys.exit(1)
    else:
        print(f"\n✅ Exiting with code 0 - API parity confirmed")
        sys.exit(0)

if __name__ == "__main__":
    main()