#!/usr/bin/env python3
"""
Simple script to fix the tab corruption issue in your enhanced parser
"""

import re
from pathlib import Path
from typing import Dict, List

def find_parser_file():
    """Find the enhanced_parse_service.py file"""
    possible_paths = [
        Path("backend/services/enhanced_parse_service.py"),
        Path("enhanced_parse_service.py"),
        Path("backend/enhanced_parse_service.py"),
        Path("services/enhanced_parse_service.py")
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return None

def fix_tab_corruption_method(content):
    """Update the tab corruption fix method"""
    
    # Check if method already exists
    if '_fix_tab_corruption' in content:
        print("   ℹ️ Tab fix method already exists")
        return content
    
    # Find a good place to insert (before the last method)
    insert_pos = content.rfind('\n    def _')
    
    if insert_pos > 0:
        tab_fix_method = '''
    def _fix_tab_corruption(self, text: str) -> str:
        """Fix tab corruption from PDF extraction"""
        # Replace tabs with single spaces
        text = re.sub(r'\\t+', ' ', text)
        
        # Fix multiple spaces
        text = re.sub(r' {2,}', ' ', text)
        
        # Clean up line breaks
        text = re.sub(r' *\\n *', '\\n', text)
        text = re.sub(r'\\n{3,}', '\\n\\n', text)
        
        return text
'''
        content = content[:insert_pos] + tab_fix_method + content[insert_pos:]
        print("   ✅ Added tab fix method")
    
    return content

def fix_experience_extraction(content):
    """Fix the experience extraction to handle your specific format"""
    
    # Look for the _post_process_resume_data method
    post_process_pattern = r'def _post_process_resume_data\(self, resume_data: ResumeData\) -> ResumeData:'
    
    if re.search(post_process_pattern, content):
        # Add a call to fix tabs in experience descriptions
        exp_fix_pattern = r'(if resume_data\.experience:)'
        exp_replacement = r'''\1
            for exp in resume_data.experience:
                if exp.description:
                    exp.description = self._fix_tab_corruption(exp.description)
                if exp.title:
                    exp.title = self._fix_tab_corruption(exp.title)
                if exp.company:
                    exp.company = self._fix_tab_corruption(exp.company)'''
        
        if re.search(exp_fix_pattern, content):
            content = re.sub(exp_fix_pattern, exp_replacement, content)
            print("   ✅ Added tab fix to experience processing")
    
    return content

def apply_fixes():
    """Apply all the tab corruption fixes"""
    
    print("🔧 APPLYING SIMPLE TAB CORRUPTION FIX")
    print("=" * 40)
    
    # Find the parser file
    parser_file = find_parser_file()
    if not parser_file:
        print("❌ Could not find enhanced_parse_service.py file")
        print("   Make sure you're in the project root directory")
        return False
    
    print(f"📁 Found parser file: {parser_file}")
    
    try:
        # Read the current content
        with open(parser_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Create backup
        backup_file = parser_file.with_suffix('.py.backup_tab_fix')
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"💾 Created backup: {backup_file}")
        
        # Apply fixes
        print("\n🔧 Applying fixes:")
        
        # Fix 1: Add tab fix method
        content = fix_tab_corruption_method(content)
        
        # Fix 2: Fix experience extraction
        content = fix_experience_extraction(content)
        
        # Make sure we have the necessary imports
        if 'import re' not in content[:500]:  # Check if import is at the top
            print("   ⚠️ Adding 'import re' to the file")
            content = 'import re\n' + content
        
        # Write the fixed content back
        with open(parser_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("\n✅ Fixes applied successfully!")
        print("\n📋 What was fixed:")
        print("   - Added tab corruption fix method")
        print("   - Experience extraction uses tab-cleaned text")
        
        return True
        
    except Exception as e:
        print(f"❌ Error applying fixes: {e}")
        return False

def main():
    """Main function"""
    if apply_fixes():
        print("\n🧪 Now test the fix:")
        print("   poetry run python test_enhanced_api.py")
        print("\n🎯 Expected result:")
        print("   Experience entries should now be > 0")
    else:
        print("\n❌ Fix failed - check error messages above")

if __name__ == "__main__":
    main()