#!/usr/bin/env python3
"""Test reliability of the app - make multiple requests."""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import chat, load_documents

print("=" * 70)
print("RELIABILITY TEST - Multiple requests to ensure app works every time")
print("=" * 70)

test_cases = [
    ("Tell me about Tyson Foods", "tyson_foods"),
    ("What is Mensch und Maschine?", "mensch_und_maschine"),
    ("Tell me something about Tyson", "tyson_foods"),
    ("MuM information please", "mensch_und_maschine"),
    ("Give me details about both companies", None),
]

results = {
    "success": 0,
    "failed": 0,
    "errors": []
}

for i, (message, expected_company) in enumerate(test_cases, 1):
    print(f"\n[Test {i}/{len(test_cases)}] Message: '{message}'")
    try:
        history = []
        start_time = time.time()
        response, history, detected_company = chat(message, history, None)
        elapsed = time.time() - start_time
        
        # Check if response is valid
        if not history or len(history) < 2:
            raise ValueError("No response generated")
        
        assistant_response = history[-1]["content"]
        
        # Check for error messages
        if "❌" in assistant_response or "Invalid" in assistant_response:
            print(f"  ⚠️  Error in response: {assistant_response[:80]}...")
            results["failed"] += 1
            results["errors"].append(f"Test {i}: {assistant_response[:100]}")
        else:
            # Check it's not the placeholder message
            if "(No documents available)" in assistant_response:
                print(f"  ❌ FAILED: Got placeholder message")
                results["failed"] += 1
                results["errors"].append(f"Test {i}: Placeholder message returned")
            else:
                print(f"  ✓ SUCCESS ({elapsed:.2f}s)")
                print(f"    Company detected: {detected_company}")
                print(f"    Response preview: {assistant_response[:100]}...")
                results["success"] += 1
    
    except Exception as e:
        print(f"  ❌ EXCEPTION: {type(e).__name__}: {str(e)[:80]}")
        results["failed"] += 1
        results["errors"].append(f"Test {i}: {type(e).__name__}: {str(e)[:100]}")
    
    time.sleep(0.5)  # Small delay between requests

print("\n" + "=" * 70)
print(f"RESULTS: {results['success']}/{len(test_cases)} passed")
print("=" * 70)

if results["success"] == len(test_cases):
    print("✅ APP IS RELIABLE - Works on every request!")
    sys.exit(0)
else:
    print(f"❌ App failed {results['failed']} times:")
    for error in results["errors"]:
        print(f"  - {error}")
    sys.exit(1)
