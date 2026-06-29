#!/usr/bin/env python3
"""
Test runner for FlipCTL.
Executes the test suite and reports results.
"""

import subprocess
import sys
import os
from pathlib import Path


def run_tests():
    """Run the test suite using pytest."""
    # Change to project directory
    project_dir = Path(__file__).parent
    os.chdir(project_dir)

    # Install test dependencies if needed
    print("Checking test dependencies...")
    try:
        import pytest
    except ImportError:
        print("Installing test dependencies...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements-test.txt"])

    # Run tests
    print("Running test suite...")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v"],
        capture_output=True,
        text=True
    )

    # Print results
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    # Return exit code
    return result.returncode


def run_specific_test(test_path):
    """Run a specific test file or test function."""
    project_dir = Path(__file__).parent
    os.chdir(project_dir)

    result = subprocess.run(
        [sys.executable, "-m", "pytest", test_path, "-v"],
        capture_output=True,
        text=True
    )

    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    return result.returncode


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Run specific test
        test_arg = sys.argv[1]
        exit_code = run_specific_test(test_arg)
    else:
        # Run all tests
        exit_code = run_tests()

    sys.exit(exit_code)