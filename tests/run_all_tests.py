#!/usr/bin/env python3
"""
Test Runner for DreamLayer AI - Comprehensive Test Suite
"""
import sys
import os
import subprocess
import argparse

def run_tests(test_type="all", verbose=False):
    """Run tests based on type"""
    
    # Add project root to path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)
    
    print("🧪 DreamLayer AI Test Suite")
    print("=" * 40)
    
    # Base pytest command
    cmd = [sys.executable, "-m", "pytest"]
    
    if verbose:
        cmd.append("-v")
    
    # Add coverage if available
    try:
        import pytest_cov
        cmd.extend(["--cov=dream_layer_backend", "--cov-report=term-missing"])
    except ImportError:
        print("📊 Coverage reporting not available (install pytest-cov)")
    
    # Select tests based on type
    if test_type == "all":
        cmd.append("tests/")
    elif test_type == "unit":
        cmd.extend([
            "tests/test_clip_score.py",
            "tests/test_database_integration.py"
        ])
    elif test_type == "integration":
        cmd.extend([
            "tests/test_txt2img_server.py",
            "tests/test_run_registry.py",
            "tests/test_report_bundle.py"
        ])
    elif test_type == "api":
        cmd.extend([
            "tests/test_txt2img_server.py",
            "tests/test_run_registry.py"
        ])
    elif test_type == "clipscore":
        cmd.append("tests/test_clip_score.py")
    else:
        cmd.append(f"tests/test_{test_type}.py")
    
    print(f"🚀 Running {test_type} tests...")
    print(f"Command: {' '.join(cmd)}")
    print()
    
    # Run tests
    try:
        result = subprocess.run(cmd, cwd=project_root)
        return result.returncode
    except FileNotFoundError:
        print("❌ pytest not found. Install with: pip install pytest")
        return 1
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1

def main():
    parser = argparse.ArgumentParser(description="DreamLayer AI Test Runner")
    parser.add_argument(
        "test_type", 
        nargs="?", 
        default="all",
        choices=["all", "unit", "integration", "api", "clipscore", "txt2img_server", "run_registry", "report_bundle", "database_integration"],
        help="Type of tests to run"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    return run_tests(args.test_type, args.verbose)

if __name__ == "__main__":
    sys.exit(main())
