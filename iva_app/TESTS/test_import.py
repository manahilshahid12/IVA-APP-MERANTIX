#!/usr/bin/env python
import sys
import traceback

print("Starting import test...")
sys.stdout.flush()

try:
    print("About to import app...")
    sys.stdout.flush()
    import app

    print("Import successful!")
except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()
    sys.exit(1)
