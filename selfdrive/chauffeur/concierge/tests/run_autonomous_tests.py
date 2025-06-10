#!/usr/bin/env python3
"""Autonomous test runner for Concierge backend."""
import os
import sys
import subprocess
import time
import json
from datetime import datetime

# Add packages to path
sys.path.insert(0, "/data/openpilot/.local/lib/python3.11/site-packages")
sys.path.insert(0, "/data/openpilot")

def run_tests():
    """Run all autonomous tests and generate report."""
    print("=" * 80)
    print("CONCIERGE AUTONOMOUS TESTING SUITE")
    print("=" * 80)
    print(f"Started at: {datetime.now()}")
    print("-" * 80)
    
    # Set environment
    env = os.environ.copy()
    env["PYTHONPATH"] = "/data/openpilot:/data/openpilot/.local/lib/python3.11/site-packages"
    
    # Test categories
    test_suites = [
        {
            "name": "Terminal WebSocket Tests",
            "file": "test_terminal_websocket.py",
            "critical": True
        },
        {
            "name": "Security Tests", 
            "file": "test_security.py",
            "critical": True
        },
        {
            "name": "API Endpoint Tests",
            "file": "test_api_endpoints.py", 
            "critical": False
        },
        {
            "name": "Performance Tests",
            "file": "test_performance.py",
            "critical": False
        }
    ]
    
    results = []
    
    for suite in test_suites:
        print(f"\nRunning {suite['name']}...")
        print("-" * 40)
        
        test_file = os.path.join(os.path.dirname(__file__), suite['file'])
        
        if not os.path.exists(test_file):
            print(f"⚠️  Test file not found: {suite['file']}")
            results.append({
                "suite": suite['name'],
                "status": "SKIPPED",
                "reason": "File not found"
            })
            continue
        
        # Run pytest
        cmd = [
            "python3", "-m", "pytest",
            test_file,
            "-v",
            "--tb=short",
            "--color=yes",
            "-x" if suite['critical'] else "-r fE"
        ]
        
        start_time = time.time()
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        duration = time.time() - start_time
        
        # Parse results
        if result.returncode == 0:
            status = "PASSED"
            print(f"✅ {suite['name']} - PASSED ({duration:.2f}s)")
        else:
            status = "FAILED"
            print(f"❌ {suite['name']} - FAILED ({duration:.2f}s)")
            if result.stdout:
                print("\nOutput:")
                print(result.stdout[-1000:])  # Last 1000 chars
            if result.stderr:
                print("\nErrors:")
                print(result.stderr[-1000:])
        
        results.append({
            "suite": suite['name'],
            "status": status,
            "duration": duration,
            "critical": suite['critical']
        })
    
    # Generate report
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for r in results if r['status'] == 'PASSED')
    failed = sum(1 for r in results if r['status'] == 'FAILED')
    skipped = sum(1 for r in results if r['status'] == 'SKIPPED')
    
    print(f"Total: {len(results)} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}")
    print("-" * 80)
    
    for result in results:
        icon = "✅" if result['status'] == 'PASSED' else "❌" if result['status'] == 'FAILED' else "⚠️"
        print(f"{icon} {result['suite']:<40} {result['status']:<10}")
        if 'duration' in result:
            print(f"   Duration: {result['duration']:.2f}s")
        if 'reason' in result:
            print(f"   Reason: {result['reason']}")
    
    # Save JSON report
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "skipped": skipped
        },
        "results": results
    }
    
    report_file = os.path.join(os.path.dirname(__file__), "test_report.json")
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nReport saved to: {report_file}")
    
    # Return exit code
    critical_failed = any(r['status'] == 'FAILED' and r.get('critical', False) for r in results)
    return 1 if critical_failed else 0

if __name__ == "__main__":
    sys.exit(run_tests())