#!/usr/bin/env python
"""Test the chat function directly to diagnose issues"""
import sys
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import app module
import app

print("=" * 70)
print("TESTING CHAT FUNCTION DIRECTLY")
print("=" * 70)

# Test with a simple message
user_msg = "Tell me about Mensch und Maschine"
history = []
last_company = None

print(f"\nTest message: {user_msg}")
print(f"History: {history}")
print(f"Last company: {last_company}")

print("\nCalling chat()...")
try:
    response_msg, updated_history, current_company = app.chat(
        user_msg, history, last_company
    )
    
    print(f"\n✓ Chat function succeeded!")
    print(f"\nAssistant response (first 500 chars):")
    print(f"{updated_history[-1]['content'][:500] if updated_history else 'No response'}")
    
except Exception as e:
    print(f"\n✗ Error in chat function: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("Checking debug.log...")
print("=" * 70)

debug_log = Path("debug.log")
if debug_log.exists():
    content = debug_log.read_text()
    lines = content.split('\n')
    print("\nLast 30 lines of debug.log:")
    for line in lines[-30:]:
        if line.strip():
            print(line)
else:
    print("No debug.log found")
