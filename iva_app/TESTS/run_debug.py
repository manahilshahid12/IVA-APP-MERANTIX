#!/usr/bin/env python
"""Debug wrapper to capture app errors"""
import sys
import traceback

try:
    print("=" * 70)
    print("STARTING APP DEBUG")
    print("=" * 70)
    sys.stdout.flush()
    
    import app
    print("App module imported successfully")
    sys.stdout.flush()
    
except Exception as e:
    print(f"\n{'=' * 70}")
    print(f"ERROR CAUGHT: {type(e).__name__}")
    print(f"{'=' * 70}")
    print(f"Message: {e}")
    print(f"\nFull Traceback:")
    traceback.print_exc()
    sys.exit(1)
