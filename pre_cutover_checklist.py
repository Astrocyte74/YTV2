#!/usr/bin/env python3
"""
Pre-Cutover GO/NO-GO Checklist for YTV2 PostgreSQL Migration
Implements OpenAI's comprehensive pre-cutover verification
"""

import requests
import sys
import os
from datetime import datetime
from typing import Dict, Any, List

class PreCutoverChecklist:
    def __init__(self):
        self.postgres_base = "https://ytv2-dashboard-postgres.onrender.com"
        self.sqlite_base = "https://ytv2-vy9k.onrender.com"

        self.checks_passed = 0
        self.checks_failed = 0
        self.checks_warning = 0

        # Expected counts from OpenAI's checklist
        self.expected_content_count = 81
        self.expected_categorized_count = 74  # content with subcategories_json
        self.expected_summaries_count = 81    # v_latest_summaries

    def log_result(self, check_name: str, status: str, details: str = "", recommendation: str = ""):
        """Log a check result with status (PASS/FAIL/WARN)."""
        symbols = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}
        symbol = symbols.get(status, "❓")

        print(f"{symbol} {check_name}")
        if details:
            print(f"   {details}")
        if recommendation:
            print(f"   💡 {recommendation}")

        if status == "PASS":
            self.checks_passed += 1
        elif status == "FAIL":
            self.checks_failed += 1
        elif status == "WARN":
            self.checks_warning += 1

    def check_database_counts(self):
        """Verify PostgreSQL database record counts match expectations."""
        print("\n📊 DATABASE COUNT VERIFICATION")
        print("-" * 50)

        try:
            # Get backend info including record count
            response = requests.get(f"{self.postgres_base}/health/backend", timeout=10)

            if response.status_code == 200:
                data = response.json()
                actual_count = data.get("record_count", 0)

                if actual_count == self.expected_content_count:
                    self.log_result("Content table count", "PASS",
                                  f"Found {actual_count} records (expected {self.expected_content_count})")
                else:
                    self.log_result("Content table count", "WARN",
                                  f"Found {actual_count} records (expected {self.expected_content_count})",
                                  "Verify if new content was added since last sync")

                # Check backend type
                backend = data.get("backend", "")
                if backend == "PostgreSQLContentIndex":
                    self.log_result("PostgreSQL backend active", "PASS", f"Backend: {backend}")
                else:
                    self.log_result("PostgreSQL backend active", "FAIL", f"Backend: {backend}")

            else:
                self.log_result("Backend health check", "FAIL",
                              f"HTTP {response.status_code}")

        except Exception as e:
            self.log_result("Database count check", "FAIL", f"Error: {str(e)}")

    def check_health_endpoints(self):
        """Test health endpoints with latency requirements."""
        print("\n🏥 HEALTH ENDPOINT VERIFICATION")
        print("-" * 50)

        # Test /health endpoint
        try:
            response = requests.get(f"{self.postgres_base}/health", timeout=10)
            if response.status_code == 200:
                self.log_result("Basic health endpoint", "PASS", "Status 200")
            else:
                self.log_result("Basic health endpoint", "FAIL", f"HTTP {response.status_code}")
        except Exception as e:
            self.log_result("Basic health endpoint", "FAIL", f"Error: {str(e)}")

        # Test /health/db endpoint with latency check
        try:
            import time
            start_time = time.time()
            response = requests.get(f"{self.postgres_base}/health/db", timeout=10)
            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                db_latency = data.get("latency_ms", latency_ms)

                if db_latency < 300:  # OpenAI's 300ms threshold
                    self.log_result("Database health & latency", "PASS",
                                  f"Latency: {db_latency:.1f}ms (< 300ms target)")
                else:
                    self.log_result("Database health & latency", "WARN",
                                  f"Latency: {db_latency:.1f}ms (> 300ms target)",
                                  "Monitor latency during cutover")

                # Check database type
                db_type = data.get("database_type", "unknown")
                if db_type == "postgresql":
                    self.log_result("Database type confirmation", "PASS", f"Type: {db_type}")
                else:
                    self.log_result("Database type confirmation", "FAIL", f"Type: {db_type}")

            else:
                self.log_result("Database health endpoint", "FAIL", f"HTTP {response.status_code}")

        except Exception as e:
            self.log_result("Database health endpoint", "FAIL", f"Error: {str(e)}")

    def check_api_parity(self):
        """Run spot-checks on key API endpoints."""
        print("\n🔍 API PARITY SPOT-CHECKS")
        print("-" * 50)

        # Test /api/filters
        try:
            pg_response = requests.get(f"{self.postgres_base}/api/filters", timeout=10)
            sqlite_response = requests.get(f"{self.sqlite_base}/api/filters", timeout=10)

            if pg_response.status_code == 200 and sqlite_response.status_code == 200:
                pg_data = pg_response.json()
                sqlite_data = sqlite_response.json()

                # Compare categories count as a proxy for data consistency
                pg_cats = len(pg_data.get("categories", []))
                sqlite_cats = len(sqlite_data.get("categories", []))

                if pg_cats == sqlite_cats:
                    self.log_result("API filters parity", "PASS",
                                  f"Categories match: {pg_cats} items")
                else:
                    self.log_result("API filters parity", "WARN",
                                  f"Category count diff: PG={pg_cats}, SQLite={sqlite_cats}")
            else:
                self.log_result("API filters parity", "FAIL",
                              f"PG:{pg_response.status_code}, SQLite:{sqlite_response.status_code}")

        except Exception as e:
            self.log_result("API filters parity", "FAIL", f"Error: {str(e)}")

        # Test /api/reports pagination
        try:
            pg_response = requests.get(f"{self.postgres_base}/api/reports?page=1&size=5", timeout=10)
            sqlite_response = requests.get(f"{self.sqlite_base}/api/reports?page=1&size=5", timeout=10)

            if pg_response.status_code == 200 and sqlite_response.status_code == 200:
                pg_data = pg_response.json()
                sqlite_data = sqlite_response.json()

                pg_total = pg_data.get("total", 0)
                sqlite_total = sqlite_data.get("total", 0)
                pg_count = len(pg_data.get("reports", []))
                sqlite_count = len(sqlite_data.get("reports", []))

                if pg_count == 5 and sqlite_count == 5:
                    self.log_result("API reports pagination", "PASS",
                                  f"Both returned 5 reports, totals: PG={pg_total}, SQLite={sqlite_total}")
                else:
                    self.log_result("API reports pagination", "FAIL",
                                  f"Report counts: PG={pg_count}, SQLite={sqlite_count}")
            else:
                self.log_result("API reports pagination", "FAIL",
                              f"PG:{pg_response.status_code}, SQLite:{sqlite_response.status_code}")

        except Exception as e:
            self.log_result("API reports pagination", "FAIL", f"Error: {str(e)}")

    def check_environment_config(self):
        """Verify environment configuration is correct."""
        print("\n⚙️ ENVIRONMENT CONFIGURATION")
        print("-" * 50)

        try:
            response = requests.get(f"{self.postgres_base}/health/backend", timeout=10)

            if response.status_code == 200:
                data = response.json()

                read_from_postgres = data.get("read_from_postgres", False)
                dsn_set = data.get("dsn_set", False)
                psycopg2_available = data.get("psycopg2_available", False)

                if read_from_postgres:
                    self.log_result("READ_FROM_POSTGRES flag", "PASS", "Set to true")
                else:
                    self.log_result("READ_FROM_POSTGRES flag", "FAIL", "Not set to true")

                if dsn_set:
                    self.log_result("DATABASE_URL_POSTGRES_NEW", "PASS", "Connection string configured")
                else:
                    self.log_result("DATABASE_URL_POSTGRES_NEW", "FAIL", "Connection string missing")

                if psycopg2_available:
                    self.log_result("psycopg2 availability", "PASS", "PostgreSQL driver available")
                else:
                    self.log_result("psycopg2 availability", "FAIL", "PostgreSQL driver missing")

            else:
                self.log_result("Environment config check", "FAIL", f"HTTP {response.status_code}")

        except Exception as e:
            self.log_result("Environment config check", "FAIL", f"Error: {str(e)}")

    def check_logging_level(self):
        """Verify logging configuration shows PostgreSQL usage."""
        print("\n📝 LOGGING VERIFICATION")
        print("-" * 50)

        # This is more of a manual check, but we can verify the backend type
        try:
            response = requests.get(f"{self.postgres_base}/health/backend", timeout=10)
            if response.status_code == 200:
                data = response.json()
                backend = data.get("backend", "")

                if "PostgreSQL" in backend:
                    self.log_result("PostgreSQL logging visibility", "PASS",
                                  "Backend type indicates PostgreSQL usage will be logged")
                else:
                    self.log_result("PostgreSQL logging visibility", "WARN",
                                  f"Backend: {backend}",
                                  "Check application logs for PostgreSQL connection messages")
            else:
                self.log_result("Logging check", "FAIL", f"HTTP {response.status_code}")

        except Exception as e:
            self.log_result("Logging check", "FAIL", f"Error: {str(e)}")

    def generate_go_no_go_decision(self):
        """Generate final GO/NO-GO decision."""
        print("\n" + "=" * 60)
        print("🚦 GO/NO-GO DECISION")
        print("=" * 60)

        total_checks = self.checks_passed + self.checks_failed + self.checks_warning

        print(f"Total Checks: {total_checks}")
        print(f"✅ Passed: {self.checks_passed}")
        print(f"⚠️  Warnings: {self.checks_warning}")
        print(f"❌ Failed: {self.checks_failed}")

        # Decision logic
        if self.checks_failed == 0:
            if self.checks_warning <= 2:  # Allow minor warnings
                print(f"\n🟢 **GO FOR CUTOVER**")
                print("✅ All critical checks passed")
                print("✅ System ready for production cutover")
                if self.checks_warning > 0:
                    print("⚠️  Monitor warnings during cutover")
                return True
            else:
                print(f"\n🟡 **GO WITH CAUTION**")
                print(f"⚠️  {self.checks_warning} warnings detected")
                print("🔧 Consider resolving warnings before cutover")
                return True
        else:
            print(f"\n🔴 **NO-GO**")
            print(f"❌ {self.checks_failed} critical failure(s) detected")
            print("🔧 Resolve all failures before attempting cutover")
            return False

    def generate_cutover_commands(self):
        """Generate ready-to-use cutover commands."""
        print(f"\n📋 READY-TO-USE CUTOVER COMMANDS")
        print("=" * 60)

        print("# Final verification before cutover:")
        print(f"curl -sSf '{self.postgres_base}/health'")
        print(f"curl -sSf '{self.postgres_base}/health/db'")
        print(f"curl -sSf '{self.postgres_base}/api/reports?page=1&size=5'")
        print()

        print("# DNS cutover (recommended method):")
        print("# 1. Set DNS TTL to 60s and wait 5-10 minutes")
        print("# 2. Update CNAME/ALIAS to point to:")
        print(f"#    {self.postgres_base.replace('https://', '')}")
        print("# 3. Verify cutover:")
        print('#    curl "https://YOUR-DOMAIN/health/backend" | jq .backend')
        print('#    Expected: "PostgreSQLContentIndex"')
        print()

        print("# Emergency rollback:")
        print("# Revert DNS CNAME to point back to:")
        print(f"#    {self.sqlite_base.replace('https://', '')}")

    def run_complete_checklist(self):
        """Run the complete pre-cutover checklist."""
        print("🚀 YTV2 PostgreSQL Migration - Pre-Cutover Checklist")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print(f"PostgreSQL System: {self.postgres_base}")
        print("=" * 70)

        # Run all checks
        self.check_database_counts()
        self.check_health_endpoints()
        self.check_api_parity()
        self.check_environment_config()
        self.check_logging_level()

        # Generate decision
        go_decision = self.generate_go_no_go_decision()

        if go_decision:
            self.generate_cutover_commands()

        return go_decision

def main():
    """Run the pre-cutover checklist."""
    checklist = PreCutoverChecklist()

    ready = checklist.run_complete_checklist()

    sys.exit(0 if ready else 1)

if __name__ == "__main__":
    main()