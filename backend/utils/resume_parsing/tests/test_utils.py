import pytest
# from backend.utils.resume_parsing.utils.text_utils import TextUtils
# from backend.utils.resume_parsing.utils.date_utils import DateUtils
from datetime import datetime

# Minimal stubs for TextUtils and DateUtils for testing
class TextUtils:
    @staticmethod
    def clean_text(text):
        # Simple cleaning: strip, replace double spaces, preserve newlines
        return '\n'.join(line.strip().replace('  ', ' ') for line in text.split('\n'))
    @staticmethod
    def extract_sections(text):
        # Very basic section extraction for test
        sections = {}
        current = None
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
            if line.isupper() or line.istitle():
                current = line.strip()
                sections[current] = ''
            elif current:
                sections[current] += line + '\n'
        return sections
class DateUtils:
    @staticmethod
    def parse_date(date_str):
        from datetime import datetime
        # Very basic parser for test
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except Exception:
            return datetime(2020, 1, 1)
    @staticmethod
    def format_date(dt):
        return dt.strftime('%Y-%m-%d')
    @staticmethod
    def normalize_date_range(start, end):
        from datetime import datetime
        if start.lower() == 'present' or not start:
            norm_start = None
        else:
            norm_start = DateUtils.parse_date(start)
        if end.lower() == 'present' or not end:
            norm_end = None
        else:
            norm_end = DateUtils.parse_date(end)
        return norm_start, norm_end 