#!/usr/bin/env python3
"""
Latency Monitoring Script for YTV2 PostgreSQL Migration
Monitors /health/db endpoint performance over time for both SQLite and PostgreSQL systems
"""

import requests
import time
import json
import csv
import sys
from datetime import datetime, timezone
from typing import Dict, List, Any
from statistics import mean, median, stdev
import threading
from pathlib import Path

class LatencyMonitor:
    def __init__(self, output_dir: str = "latency_data"):
        self.sqlite_base = "https://ytv2-vy9k.onrender.com"
        self.postgres_base = "https://ytv2-dashboard-postgres.onrender.com"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        self.running = False
        self.data_points = []

        # Start time for this monitoring session
        self.session_start = datetime.now(timezone.utc)

    def measure_endpoint_latency(self, base_url: str, endpoint: str = "/health") -> Dict[str, Any]:
        """Measure latency for a single endpoint request."""
        url = f"{base_url}{endpoint}"

        try:
            start_time = time.time()
            response = requests.get(url, timeout=30)
            end_time = time.time()

            latency_ms = (end_time - start_time) * 1000

            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "url": url,
                "status_code": response.status_code,
                "latency_ms": round(latency_ms, 2),
                "success": response.status_code == 200,
                "error": None
            }

        except Exception as e:
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "url": url,
                "status_code": None,
                "latency_ms": None,
                "success": False,
                "error": str(e)
            }

    def sample_both_systems(self) -> Dict[str, Any]:
        """Sample latency from both SQLite and PostgreSQL systems."""
        sqlite_result = self.measure_endpoint_latency(self.sqlite_base)
        postgres_result = self.measure_endpoint_latency(self.postgres_base)

        data_point = {
            "sample_timestamp": datetime.now(timezone.utc).isoformat(),
            "sqlite": sqlite_result,
            "postgres": postgres_result
        }

        # Calculate comparison if both succeeded
        if sqlite_result["success"] and postgres_result["success"]:
            sqlite_latency = sqlite_result["latency_ms"]
            postgres_latency = postgres_result["latency_ms"]

            data_point["comparison"] = {
                "postgres_faster": postgres_latency < sqlite_latency,
                "difference_ms": round(postgres_latency - sqlite_latency, 2),
                "ratio": round(postgres_latency / sqlite_latency, 3) if sqlite_latency > 0 else None
            }

        self.data_points.append(data_point)
        return data_point

    def print_sample_result(self, data_point: Dict[str, Any]):
        """Print a formatted sample result."""
        timestamp = data_point["sample_timestamp"]
        sqlite = data_point["sqlite"]
        postgres = data_point["postgres"]

        time_str = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).strftime('%H:%M:%S')

        if sqlite["success"] and postgres["success"]:
            sqlite_ms = sqlite["latency_ms"]
            postgres_ms = postgres["latency_ms"]

            if "comparison" in data_point:
                comp = data_point["comparison"]
                faster_symbol = "🟢" if comp["postgres_faster"] else "🔴"
                print(f"{time_str} | SQLite: {sqlite_ms:6.1f}ms | PostgreSQL: {postgres_ms:6.1f}ms | Diff: {comp['difference_ms']:+6.1f}ms {faster_symbol}")
            else:
                print(f"{time_str} | SQLite: {sqlite_ms:6.1f}ms | PostgreSQL: {postgres_ms:6.1f}ms")
        else:
            sqlite_status = "✅" if sqlite["success"] else f"❌({sqlite.get('status_code', 'ERR')})"
            postgres_status = "✅" if postgres["success"] else f"❌({postgres.get('status_code', 'ERR')})"
            print(f"{time_str} | SQLite: {sqlite_status} | PostgreSQL: {postgres_status}")

    def save_data_point(self, data_point: Dict[str, Any]):
        """Save data point to CSV and JSON files."""
        # CSV file for easy analysis
        csv_file = self.output_dir / f"latency_samples_{self.session_start.strftime('%Y%m%d_%H%M%S')}.csv"

        # Create CSV if it doesn't exist
        csv_exists = csv_file.exists()

        with open(csv_file, 'a', newline='') as f:
            writer = csv.writer(f)

            if not csv_exists:
                # Write header
                writer.writerow([
                    'timestamp', 'sqlite_latency_ms', 'sqlite_status', 'sqlite_success',
                    'postgres_latency_ms', 'postgres_status', 'postgres_success',
                    'postgres_faster', 'difference_ms', 'ratio'
                ])

            # Extract values
            sqlite = data_point["sqlite"]
            postgres = data_point["postgres"]
            comp = data_point.get("comparison", {})

            writer.writerow([
                data_point["sample_timestamp"],
                sqlite.get("latency_ms", ""),
                sqlite.get("status_code", ""),
                sqlite.get("success", False),
                postgres.get("latency_ms", ""),
                postgres.get("status_code", ""),
                postgres.get("success", False),
                comp.get("postgres_faster", ""),
                comp.get("difference_ms", ""),
                comp.get("ratio", "")
            ])

        # JSON file for complete data
        json_file = self.output_dir / f"latency_complete_{self.session_start.strftime('%Y%m%d_%H%M%S')}.json"

        with open(json_file, 'w') as f:
            json.dump(self.data_points, f, indent=2)

    def calculate_statistics(self) -> Dict[str, Any]:
        """Calculate statistics from collected data points."""
        if not self.data_points:
            return {}

        successful_sqlite = [dp["sqlite"]["latency_ms"] for dp in self.data_points
                           if dp["sqlite"]["success"] and dp["sqlite"]["latency_ms"] is not None]
        successful_postgres = [dp["postgres"]["latency_ms"] for dp in self.data_points
                             if dp["postgres"]["success"] and dp["postgres"]["latency_ms"] is not None]

        stats = {
            "total_samples": len(self.data_points),
            "sqlite": {
                "successful_samples": len(successful_sqlite),
                "mean_ms": round(mean(successful_sqlite), 2) if successful_sqlite else None,
                "median_ms": round(median(successful_sqlite), 2) if successful_sqlite else None,
                "min_ms": round(min(successful_sqlite), 2) if successful_sqlite else None,
                "max_ms": round(max(successful_sqlite), 2) if successful_sqlite else None,
                "stdev_ms": round(stdev(successful_sqlite), 2) if len(successful_sqlite) > 1 else None
            },
            "postgres": {
                "successful_samples": len(successful_postgres),
                "mean_ms": round(mean(successful_postgres), 2) if successful_postgres else None,
                "median_ms": round(median(successful_postgres), 2) if successful_postgres else None,
                "min_ms": round(min(successful_postgres), 2) if successful_postgres else None,
                "max_ms": round(max(successful_postgres), 2) if successful_postgres else None,
                "stdev_ms": round(stdev(successful_postgres), 2) if len(successful_postgres) > 1 else None
            }
        }

        # Comparison stats
        if successful_sqlite and successful_postgres:
            postgres_faster_count = sum(1 for dp in self.data_points
                                      if dp.get("comparison", {}).get("postgres_faster", False))
            stats["comparison"] = {
                "postgres_faster_percentage": round(postgres_faster_count / min(len(successful_sqlite), len(successful_postgres)) * 100, 1),
                "average_difference_ms": round(mean([dp["comparison"]["difference_ms"] for dp in self.data_points
                                                   if "comparison" in dp]), 2)
            }

        return stats

    def print_statistics(self):
        """Print current statistics."""
        stats = self.calculate_statistics()

        if not stats:
            print("No statistics available yet.")
            return

        print("\n" + "=" * 60)
        print("📊 LATENCY MONITORING STATISTICS")
        print("=" * 60)
        print(f"Total Samples: {stats['total_samples']}")

        print(f"\n🗄️  SQLite Production ({stats['sqlite']['successful_samples']} successful):")
        if stats['sqlite']['mean_ms']:
            print(f"   Mean: {stats['sqlite']['mean_ms']}ms | Median: {stats['sqlite']['median_ms']}ms")
            print(f"   Range: {stats['sqlite']['min_ms']}ms - {stats['sqlite']['max_ms']}ms")
            if stats['sqlite']['stdev_ms']:
                print(f"   Std Dev: {stats['sqlite']['stdev_ms']}ms")

        print(f"\n🐘 PostgreSQL Test ({stats['postgres']['successful_samples']} successful):")
        if stats['postgres']['mean_ms']:
            print(f"   Mean: {stats['postgres']['mean_ms']}ms | Median: {stats['postgres']['median_ms']}ms")
            print(f"   Range: {stats['postgres']['min_ms']}ms - {stats['postgres']['max_ms']}ms")
            if stats['postgres']['stdev_ms']:
                print(f"   Std Dev: {stats['postgres']['stdev_ms']}ms")

        if "comparison" in stats:
            print(f"\n🏁 Performance Comparison:")
            print(f"   PostgreSQL faster: {stats['comparison']['postgres_faster_percentage']}% of time")
            print(f"   Average difference: {stats['comparison']['average_difference_ms']}ms")

    def run_continuous_monitoring(self, interval_seconds: int = 10, duration_minutes: int = 5):
        """Run continuous latency monitoring."""
        total_samples = int((duration_minutes * 60) / interval_seconds)

        print(f"🔍 Starting latency monitoring for {duration_minutes} minutes")
        print(f"📊 Sampling every {interval_seconds} seconds ({total_samples} total samples)")
        print(f"📁 Data will be saved to: {self.output_dir}")
        print("=" * 60)
        print("Time     | SQLite Latency | PostgreSQL Latency | Difference")
        print("-" * 60)

        self.running = True
        sample_count = 0

        try:
            while self.running and sample_count < total_samples:
                data_point = self.sample_both_systems()
                self.print_sample_result(data_point)
                self.save_data_point(data_point)

                sample_count += 1

                if sample_count < total_samples:
                    time.sleep(interval_seconds)

        except KeyboardInterrupt:
            print("\n⏹️  Monitoring stopped by user")
            self.running = False

        self.print_statistics()

        print(f"\n📁 Results saved to {self.output_dir}/")
        print("✅ Monitoring complete")

    def run_quick_sample(self, num_samples: int = 5):
        """Run a quick sampling session."""
        print(f"🔍 Taking {num_samples} quick latency samples")
        print("=" * 60)
        print("Time     | SQLite Latency | PostgreSQL Latency | Difference")
        print("-" * 60)

        for i in range(num_samples):
            data_point = self.sample_both_systems()
            self.print_sample_result(data_point)
            self.save_data_point(data_point)

            if i < num_samples - 1:
                time.sleep(2)  # Brief pause between samples

        self.print_statistics()
        print(f"\n📁 Results saved to {self.output_dir}/")

def main():
    """Main function with command line interface."""
    import argparse

    parser = argparse.ArgumentParser(description='YTV2 Latency Monitor for PostgreSQL Migration')
    parser.add_argument('--mode', choices=['quick', 'continuous'], default='quick',
                       help='Monitoring mode (default: quick)')
    parser.add_argument('--samples', type=int, default=5,
                       help='Number of samples for quick mode (default: 5)')
    parser.add_argument('--duration', type=int, default=5,
                       help='Duration in minutes for continuous mode (default: 5)')
    parser.add_argument('--interval', type=int, default=10,
                       help='Interval in seconds for continuous mode (default: 10)')
    parser.add_argument('--output-dir', default='latency_data',
                       help='Output directory for data files (default: latency_data)')

    args = parser.parse_args()

    monitor = LatencyMonitor(output_dir=args.output_dir)

    print(f"🏥 YTV2 Health Endpoint Latency Monitor")
    print(f"SQLite Production: {monitor.sqlite_base}/health")
    print(f"PostgreSQL Test: {monitor.postgres_base}/health")
    print()

    if args.mode == 'quick':
        monitor.run_quick_sample(args.samples)
    else:
        monitor.run_continuous_monitoring(args.interval, args.duration)

if __name__ == "__main__":
    main()