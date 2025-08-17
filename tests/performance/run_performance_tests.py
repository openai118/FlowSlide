#!/usr/bin/env python3
"""
FlowSlide Performance Test Runner
Automated performance testing with different scenarios
"""

import os
import sys
import subprocess
import time
import json
import argparse
from datetime import datetime
from pathlib import Path


class PerformanceTestRunner:
    """Manages and runs performance tests"""
    
    def __init__(self, host="http://localhost:8000"):
        self.host = host
        self.results_dir = Path("performance_results")
        self.results_dir.mkdir(exist_ok=True)
        
    def run_test(self, test_name, users, spawn_rate, duration, test_file="locustfile.py"):
        """Run a specific performance test"""
        print(f"🚀 Running {test_name} performance test")
        print(f"   Users: {users}, Spawn rate: {spawn_rate}/s, Duration: {duration}s")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.results_dir / f"{test_name}_{timestamp}.json"
        html_file = self.results_dir / f"{test_name}_{timestamp}.html"
        
        cmd = [
            "locust",
            "-f", f"tests/performance/{test_file}",
            "--host", self.host,
            "--users", str(users),
            "--spawn-rate", str(spawn_rate),
            "--run-time", f"{duration}s",
            "--headless",
            "--json",
            "--html", str(html_file)
        ]
        
        print(f"📋 Command: {' '.join(cmd)}")
        
        try:
            # Run the test
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 60)
            
            # Parse results
            if result.returncode == 0:
                print(f"✅ {test_name} test completed successfully")
                self._save_results(test_name, timestamp, result.stdout, results_file)
                return True
            else:
                print(f"❌ {test_name} test failed")
                print(f"Error: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"⏰ {test_name} test timed out")
            return False
        except Exception as e:
            print(f"💥 {test_name} test error: {e}")
            return False
    
    def _save_results(self, test_name, timestamp, output, results_file):
        """Save test results to file"""
        results = {
            "test_name": test_name,
            "timestamp": timestamp,
            "host": self.host,
            "output": output
        }
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"📊 Results saved to {results_file}")
    
    def run_baseline_test(self):
        """Run baseline performance test"""
        return self.run_test(
            test_name="baseline",
            users=10,
            spawn_rate=2,
            duration=60
        )
    
    def run_load_test(self):
        """Run load test with moderate traffic"""
        return self.run_test(
            test_name="load",
            users=50,
            spawn_rate=5,
            duration=300  # 5 minutes
        )
    
    def run_stress_test(self):
        """Run stress test with high traffic"""
        return self.run_test(
            test_name="stress",
            users=100,
            spawn_rate=10,
            duration=600  # 10 minutes
        )
    
    def run_spike_test(self):
        """Run spike test with sudden traffic increase"""
        return self.run_test(
            test_name="spike",
            users=200,
            spawn_rate=50,  # Rapid spawn
            duration=180  # 3 minutes
        )
    
    def run_endurance_test(self):
        """Run endurance test for extended period"""
        return self.run_test(
            test_name="endurance",
            users=30,
            spawn_rate=3,
            duration=1800  # 30 minutes
        )
    
    def run_api_only_test(self):
        """Run API-only performance test"""
        return self.run_test(
            test_name="api_only",
            users=25,
            spawn_rate=5,
            duration=300,
            test_file="api_performance.py"
        )
    
    def run_all_tests(self):
        """Run all performance test scenarios"""
        tests = [
            ("Baseline", self.run_baseline_test),
            ("Load", self.run_load_test),
            ("Stress", self.run_stress_test),
            ("Spike", self.run_spike_test),
            ("API Only", self.run_api_only_test),
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            print(f"\n{'='*50}")
            print(f"Starting {test_name} Test")
            print(f"{'='*50}")
            
            success = test_func()
            results[test_name] = success
            
            if success:
                print(f"✅ {test_name} test passed")
            else:
                print(f"❌ {test_name} test failed")
            
            # Wait between tests
            if test_name != tests[-1][0]:  # Not the last test
                print("⏳ Waiting 30 seconds before next test...")
                time.sleep(30)
        
        # Print summary
        print(f"\n{'='*50}")
        print("Performance Test Summary")
        print(f"{'='*50}")
        
        for test_name, success in results.items():
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{test_name:15} {status}")
        
        passed = sum(results.values())
        total = len(results)
        print(f"\nOverall: {passed}/{total} tests passed")
        
        return passed == total
    
    def generate_report(self):
        """Generate performance test report"""
        print("📊 Generating performance test report...")
        
        # Find all result files
        result_files = list(self.results_dir.glob("*.json"))
        
        if not result_files:
            print("No performance test results found")
            return
        
        report_file = self.results_dir / f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        
        html_content = self._generate_html_report(result_files)
        
        with open(report_file, 'w') as f:
            f.write(html_content)
        
        print(f"📋 Performance report generated: {report_file}")
    
    def _generate_html_report(self, result_files):
        """Generate HTML performance report"""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>FlowSlide Performance Test Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .header { background: #f0f0f0; padding: 20px; border-radius: 5px; }
                .test-result { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
                .pass { border-left: 5px solid #4CAF50; }
                .fail { border-left: 5px solid #f44336; }
                .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }
                .metric { background: #f9f9f9; padding: 10px; border-radius: 3px; }
                pre { background: #f5f5f5; padding: 10px; border-radius: 3px; overflow-x: auto; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>FlowSlide Performance Test Report</h1>
                <p>Generated: {timestamp}</p>
                <p>Host: {host}</p>
            </div>
        """.format(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            host=self.host
        )
        
        for result_file in sorted(result_files):
            try:
                with open(result_file) as f:
                    data = json.load(f)
                
                html += f"""
                <div class="test-result">
                    <h2>{data['test_name'].title()} Test</h2>
                    <p><strong>Timestamp:</strong> {data['timestamp']}</p>
                    <div class="metrics">
                        <div class="metric">
                            <strong>Test Output:</strong>
                            <pre>{data.get('output', 'No output available')[:500]}...</pre>
                        </div>
                    </div>
                </div>
                """
            except Exception as e:
                html += f"""
                <div class="test-result fail">
                    <h2>Error loading {result_file.name}</h2>
                    <p>Error: {e}</p>
                </div>
                """
        
        html += """
        </body>
        </html>
        """
        
        return html


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="FlowSlide Performance Test Runner")
    parser.add_argument("--host", default="http://localhost:8000", help="Target host")
    parser.add_argument("--test", choices=["baseline", "load", "stress", "spike", "endurance", "api", "all"], 
                       default="baseline", help="Test type to run")
    parser.add_argument("--report", action="store_true", help="Generate performance report")
    
    args = parser.parse_args()
    
    runner = PerformanceTestRunner(host=args.host)
    
    if args.report:
        runner.generate_report()
        return
    
    print("🎯 FlowSlide Performance Test Runner")
    print(f"Target: {args.host}")
    print(f"Test: {args.test}")
    print("-" * 50)
    
    # Check if locust is installed
    try:
        subprocess.run(["locust", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Locust is not installed. Install with: pip install locust")
        sys.exit(1)
    
    # Run the specified test
    success = False
    
    if args.test == "baseline":
        success = runner.run_baseline_test()
    elif args.test == "load":
        success = runner.run_load_test()
    elif args.test == "stress":
        success = runner.run_stress_test()
    elif args.test == "spike":
        success = runner.run_spike_test()
    elif args.test == "endurance":
        success = runner.run_endurance_test()
    elif args.test == "api":
        success = runner.run_api_only_test()
    elif args.test == "all":
        success = runner.run_all_tests()
    
    if success:
        print("\n🎉 Performance tests completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Performance tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
