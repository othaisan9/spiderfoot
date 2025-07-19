#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Script to run async framework tests."""

import sys
import subprocess
import os
from pathlib import Path

def run_command(cmd, description):
    """Run a command and print results."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.stdout:
            print("STDOUT:")
            print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
            
        if result.returncode == 0:
            print(f"✅ {description} - PASSED")
        else:
            print(f"❌ {description} - FAILED (exit code: {result.returncode})")
            
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} - TIMEOUT")
        return False
    except Exception as e:
        print(f"💥 {description} - ERROR: {e}")
        return False

def main():
    """Run all async framework tests."""
    # Get the test directory
    test_dir = Path(__file__).parent
    integration_dir = test_dir / "integration"
    
    # Change to test directory
    original_dir = os.getcwd()
    os.chdir(test_dir.parent)  # Go to spiderfoot root
    
    print("🚀 SpiderFoot Async Framework Test Suite")
    print(f"Test directory: {test_dir}")
    print(f"Integration directory: {integration_dir}")
    
    results = []
    
    try:
        # Test 1: Framework Components
        success = run_command([
            sys.executable, "-m", "pytest", 
            str(integration_dir / "test_async_framework.py"),
            "-v", "-s", "--tb=short"
        ], "Async Framework Components")
        results.append(("Framework Components", success))
        
        # Test 2: Async Modules
        success = run_command([
            sys.executable, "-m", "pytest",
            str(integration_dir / "modules" / "test_async_modules.py"),
            "-v", "-s", "--tb=short"
        ], "Async Modules")
        results.append(("Async Modules", success))
        
        # Test 3: Performance Benchmarks
        success = run_command([
            sys.executable, "-m", "pytest",
            str(integration_dir / "test_async_performance.py"),
            "-v", "-s", "--tb=short"
        ], "Performance Benchmarks")
        results.append(("Performance Benchmarks", success))
        
        # Test 4: Import Tests (check if all modules can be imported)
        success = run_command([
            sys.executable, "-c",
            """
import sys
sys.path.insert(0, '.')
try:
    from spiderfoot.http_async import AsyncHttpClient
    from spiderfoot.dns_async import AsyncDnsResolver
    from spiderfoot.db_async import AsyncSpiderFootDb
    from spiderfoot.rate_limiter import RateLimiter
    from spiderfoot.event_queue_async import AsyncEventQueue
    from spiderfoot.plugin_async import AsyncSpiderFootPlugin
    print('✅ All async framework imports successful')
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
"""
        ], "Import Tests")
        results.append(("Import Tests", success))
        
        # Test 5: Async Module Imports
        success = run_command([
            sys.executable, "-c",
            """
import sys
sys.path.insert(0, '.')
modules_to_test = [
    'modules.sfp_shodan_async',
    'modules.sfp_virustotal_async', 
    'modules.sfp_censys_async',
    'modules.sfp_unified_ip_info_async'
]

failed = []
for module in modules_to_test:
    try:
        __import__(module)
        print(f'✅ {module} imported successfully')
    except ImportError as e:
        print(f'❌ {module} import failed: {e}')
        failed.append(module)

if failed:
    print(f'Failed modules: {failed}')
    sys.exit(1)
else:
    print('✅ All async modules imported successfully')
"""
        ], "Async Module Imports")
        results.append(("Async Module Imports", success))
        
    finally:
        os.chdir(original_dir)
    
    # Summary
    print(f"\n{'='*80}")
    print("📊 TEST SUMMARY")
    print(f"{'='*80}")
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{test_name:<30} {status}")
        if success:
            passed += 1
    
    print(f"\n📈 Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 All tests passed! Async framework is ready to use.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())