#!/usr/bin/env python3
"""
Parse all Draw Steel data from markdown files into JSON.

This script runs all parsers in sequence:
1. parse_classes.py - Extract class data
2. parse_abilities.py - Extract ability data
3. parse_features.py - Extract feature data

Run this script to regenerate all JSON data files.
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime


def run_parser(script_name: str) -> tuple[bool, str]:
    """Run a parser script and return success status and output."""
    print(f"\n{'=' * 70}")
    print(f"Running {script_name}...")
    print('=' * 70)
    
    script_path = Path(__file__).parent / script_name
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        print(f"ERROR: {script_name} failed with exit code {e.returncode}")
        print(e.stdout)
        print(e.stderr, file=sys.stderr)
        return False, e.stdout


def main():
    """Run all parsers in sequence."""
    start_time = datetime.now()
    
    print("=" * 70)
    print("DRAW STEEL DATA PARSER - BATCH PROCESSING")
    print("=" * 70)
    print(f"Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    parsers = [
        'parse_classes.py',
        'parse_abilities.py',
        'parse_features.py'
    ]
    
    results = {}
    
    for parser in parsers:
        success, output = run_parser(parser)
        results[parser] = success
        
        if not success:
            print(f"\n{'!' * 70}")
            print(f"BATCH PROCESSING STOPPED - {parser} failed")
            print('!' * 70)
            sys.exit(1)
    
    # Summary
    end_time = datetime.now()
    duration = end_time - start_time
    
    print("\n" + "=" * 70)
    print("BATCH PROCESSING COMPLETE")
    print("=" * 70)
    print(f"Finished at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Duration: {duration.total_seconds():.2f} seconds")
    print()
    print("Results:")
    for parser, success in results.items():
        status = "✓ SUCCESS" if success else "✗ FAILED"
        print(f"  {parser:25} {status}")
    print()
    print("Output files generated:")
    print("  - data/classes.json")
    print("  - data/abilities.json")
    print("  - data/features.json")
    print("=" * 70)


if __name__ == '__main__':
    main()
