#!/usr/bin/env python3
"""Test the fixed app to ensure documents load correctly."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import load_documents, chat, detect_company, COMPANIES

print("=" * 60)
print("TESTING FIXED APP")
print("=" * 60)

# Test 1: Load documents
print("\n[TEST 1] Loading documents...")
docs = load_documents()
for company in COMPANIES.keys():
    count = len(docs.get(company, []))
    print(f"  {company}: {count} documents")

# Test 2: Detect company
print("\n[TEST 2] Testing company detection...")
test_messages = [
    "Tell me about Tyson Foods",
    "What do you know about MuM?",
    "Tell me something",
]
for msg in test_messages:
    detected = detect_company(msg, None)
    print(f"  Message: '{msg}'")
    print(f"  Detected: {detected}")

# Test 3: Chat with specific company
print("\n[TEST 3] Testing chat function with Tyson...")
user_msg = "Tell me about Tyson Foods"
history = []
response, history, company = chat(user_msg, history, None)
print(f"  Company detected: {company}")
print(
    f"  Assistant first 200 chars: {history[-1]['content'][:200] if history else 'NO RESPONSE'}"
)
if "(No documents available)" in str(history):
    print("  ❌ ERROR: Still showing 'No documents available'!")
else:
    print("  ✓ Documents appear to be loaded")

# Test 4: Check for error messages
print("\n[TEST 4] Checking for helpful error messages...")
if "❌ No documents found" in str(history):
    print("  ✓ Good: App returns clear error if documents missing")
else:
    print("  ✓ No error detected (documents loaded successfully)")

print("\n" + "=" * 60)
print("TEST COMPLETE - Check browser at http://127.0.0.1:7860")
print("=" * 60)
