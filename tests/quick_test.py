import sys
import os
sys.path.insert(0, '.')

from frontend.modules.assistant import format_ai_response

# Test the exact same input as the failing test
test_input = """### Test Response

This is a **test response** with:

- Bullet points
- Code snippets with `format_ai_response`
- Multiple paragraphs

1. Numbered items
2. More items

Regular text at the end."""

print("Input:")
print(repr(test_input))
print("\nOutput:")
result = format_ai_response(test_input)
print(result)

# Check for expected elements
checks = [
    ('<h3 style="color: #1e40af', 'Header'),
    ('<ul style="margin: 0.8rem 0', 'Bullet list'),
    ('<ol style="margin: 0.8rem 0', 'Numbered list'),
    ('<strong>test response</strong>', 'Bold text'),
    ('<code style="background-color: #f3f4f6', 'Code'),
    ('<p style="margin: 0.8rem 0', 'Paragraph')
]

print("\nChecks:")
for check, name in checks:
    found = check in result
    print(f"{name}: {'✅' if found else '❌'}")
    if not found:
        print(f"  Looking for: {check}")
        print(f"  In result: {result[:200]}...")
