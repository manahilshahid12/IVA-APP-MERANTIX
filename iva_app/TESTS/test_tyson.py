#!/usr/bin/env python
"""Test chat with Tyson question"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import app

print("=" * 70)
print("TESTING TYSON CHAT")
print("=" * 70)

# Test with Tyson question
user_msg = "Tell me about Tyson Foods"
history = []
last_company = None

print(f"\nTest message: {user_msg}")

try:
    response_msg, updated_history, current_company = app.chat(
        user_msg, history, last_company
    )
    
    print(f"\nAssistant response:")
    print(updated_history[-1]['content'][:800])
    
except Exception as e:
    print(f"\nError: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

# Check debug log
debug_log = Path("debug.log")
if debug_log.exists():
    content = debug_log.read_text()
    lines = content.split('\n')
    print("\n" + "=" * 70)
    print("LAST LINES FROM DEBUG LOG:")
    print("=" * 70)
    for line in lines[-20:]:
        if line.strip():
            print(line)
