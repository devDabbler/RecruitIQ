import re
from typing import Any

def clean_generated_text(text: Any) -> Any:
    """Remove trailing placeholder or orphan headings/outlines from model output.
    Safe no-op for non-strings.
    Examples removed at the end of the text: "Factors A", "A.", "### Notes", "1." with no content.
    """
    if not isinstance(text, str):
        return text
    s = text.strip()
    if not s:
        return s
    lines = s.splitlines()
    heading_patterns = [
        r"^\s{0,3}#{1,6}\s+.*$",                 # Markdown headings
        r"^\s*(Factors?|Appendix|Notes?)\s*[A-Z]?:?\s*$",  # Placeholder like 'Factors A'
        r"^\s*[A-Z]\.\s*$",                     # Single-letter outline like 'A.'
        r"^\s*\d+\.\s*$"                        # Numbered item with no content
    ]
    # Trim consecutive orphan headings at the end
    while lines:
        last = lines[-1].strip()
        if last == "":
            lines.pop()
            continue
        if any(re.match(p, last, flags=re.IGNORECASE) for p in heading_patterns):
            lines.pop()
            continue
        break
    return "\n".join(lines).strip()
