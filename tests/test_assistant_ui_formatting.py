# tests/test_assistant_ui_formatting.py
import pytest
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from frontend.modules.assistant import format_ai_response

class TestAssistantUIFormatting:
    """Test suite for AI Assistant UI output formatting."""
    
    def test_format_basic_text(self):
        """Test basic text formatting without special elements."""
        input_text = "This is a simple response from the AI assistant."
        result = format_ai_response(input_text)
        
        # Should contain the text wrapped in proper HTML
        assert "This is a simple response from the AI assistant." in result
        assert '<div style="font-family: \'Inter\'' in result
        assert '<p style="margin: 0.8rem 0; line-height: 1.6; color: #374151;">' in result
    
    def test_format_headers(self):
        """Test formatting of different header levels."""
        input_text = """### Main Header
## Secondary Header
# Small Header

Regular text content."""
        
        result = format_ai_response(input_text)
        
        # Check for proper header formatting
        assert '<h3 style="color: #1e40af; margin-top: 1.5rem; margin-bottom: 0.5rem; font-weight: 600;">Main Header</h3>' in result
        assert '<h4 style="color: #1e40af; margin-top: 1.2rem; margin-bottom: 0.5rem; font-weight: 600;">Secondary Header</h4>' in result
        assert '<h5 style="color: #1e40af; margin-top: 1rem; margin-bottom: 0.5rem; font-weight: 600;">Small Header</h5>' in result
    
    def test_format_bullet_lists(self):
        """Test formatting of bullet point lists."""
        input_text = """Here are some key points:

- First bullet point
- Second bullet point with **bold text**
- Third bullet point"""
        
        result = format_ai_response(input_text)
        
        # Check for proper list formatting
        assert '<ul style="margin: 0.8rem 0; padding-left: 1.5rem; color: #374151;">' in result
        assert '<li style="margin: 0.3rem 0; line-height: 1.5;">First bullet point</li>' in result
        assert '<strong>bold text</strong>' in result
    
    def test_format_numbered_lists(self):
        """Test formatting of numbered lists."""
        input_text = """Steps to follow:

1. First step
2. Second step with **emphasis**
3. Third step"""
        
        result = format_ai_response(input_text)
        
        # Check for proper numbered list formatting
        assert '<ol style="margin: 0.8rem 0; padding-left: 1.5rem; color: #374151;">' in result
        assert '<li style="margin: 0.3rem 0; line-height: 1.5;">First step</li>' in result
        assert '<strong>emphasis</strong>' in result
    
    def test_format_inline_bold(self):
        """Test formatting of inline bold text."""
        input_text = "This text has **bold sections** and **multiple bold** parts."
        
        result = format_ai_response(input_text)
        
        # Check for proper bold formatting
        assert '<strong>bold sections</strong>' in result
        assert '<strong>multiple bold</strong>' in result
    
    def test_format_inline_code(self):
        """Test formatting of inline code snippets."""
        input_text = "Use the `format_ai_response` function to format text."
        
        result = format_ai_response(input_text)
        
        # Check for proper code formatting
        assert '<code style="background-color: #f3f4f6; padding: 0.2rem 0.4rem; border-radius: 0.25rem; font-family: monospace; font-size: 0.9em;">format_ai_response</code>' in result
    
    def test_format_complex_response(self):
        """Test formatting of a complex AI response with multiple elements."""
        input_text = """### Market Analysis Results

Based on my research, here are the key findings:

## Salary Insights
- **Average Salary**: $95,000 - $130,000
- **Market Demand**: High demand for software developers
- **Growth Rate**: 15% year-over-year

## Recommendations
1. Focus on candidates with `Python` and `JavaScript` skills
2. **Competitive salary** is essential for top talent
3. Consider remote work options

**Summary**: The market is competitive but offers good opportunities."""
        
        result = format_ai_response(input_text)
        
        # Verify all elements are properly formatted
        assert '<h3 style="color: #1e40af' in result  # Main header
        assert '<h4 style="color: #1e40af' in result  # Secondary header
        assert '<ul style="margin: 0.8rem 0' in result  # Bullet list
        assert '<ol style="margin: 0.8rem 0' in result  # Numbered list
        assert '<strong>Average Salary</strong>' in result  # Bold text
        assert '<code style="background-color: #f3f4f6' in result  # Inline code
        assert 'font-family: \'Inter\'' in result  # Font family
    
    def test_format_empty_text(self):
        """Test handling of empty or None input."""
        result = format_ai_response("")
        assert '<div style="font-family: \'Inter\'' in result
        
        result = format_ai_response(None)
        assert '<div style="font-family: \'Inter\'' in result
    
    def test_format_special_characters(self):
        """Test handling of special characters and HTML escaping."""
        input_text = "Text with <script>alert('test')</script> and & symbols."
        
        result = format_ai_response(input_text)
        
        # Should not contain raw script tags (should be escaped)
        assert '<script>' not in result
        assert 'alert(' not in result
        # Should contain the text but safely escaped
        assert 'Text with' in result
    
    def test_format_long_text_blocks(self):
        """Test formatting of longer text blocks to ensure readability."""
        input_text = """This is a very long paragraph that contains multiple sentences and should be formatted properly for readability. It includes various punctuation marks, numbers like 123, and should maintain proper line spacing and font styling.

This is a second paragraph that should be separated from the first with proper spacing."""
        
        result = format_ai_response(input_text)
        
        # Check for proper paragraph separation and styling
        assert result.count('<p style="margin: 0.8rem 0; line-height: 1.6; color: #374151;">') == 2
        assert 'overflow-wrap: break-word' in result
    
    def test_format_mixed_content(self):
        """Test formatting of mixed content types in a single response."""
        input_text = """## Job Market Analysis

Here's what I found:

- **High demand** for software engineers
- Salary range: `$80k - $120k`
- Remote work is **increasingly popular**

### Next Steps
1. Review candidate profiles
2. Adjust salary expectations
3. Consider remote-first approach

Contact me if you need more details."""
        
        result = format_ai_response(input_text)
        
        # Verify all content types are handled
        assert '<h4 style="color: #1e40af' in result  # Header
        assert '<ul style="margin: 0.8rem 0' in result  # Bullet list
        assert '<h3 style="color: #1e40af' in result  # Another header
        assert '<ol style="margin: 0.8rem 0' in result  # Numbered list
        assert '<strong>High demand</strong>' in result  # Bold
        assert '<code style="background-color: #f3f4f6' in result  # Code
        assert '<p style="margin: 0.8rem 0' in result  # Regular paragraph

def test_integration_with_real_response():
    """Integration test with a realistic AI assistant response."""
    realistic_response = """### Market Analysis: Software Developers in Madison, Wisconsin

Based on my research, here's a comprehensive analysis of hiring software developers in Madison:

## Market Overview
- **Total Tech Jobs**: Approximately 15,000+ technology positions
- **Software Developer Roles**: 2,500+ active openings
- **Market Growth**: 12% annual growth in tech sector

## Salary Benchmarks
- **Entry Level**: $65,000 - $80,000
- **Mid Level**: $80,000 - $110,000  
- **Senior Level**: $110,000 - $150,000

## Key Findings
1. **Strong talent pool** from University of Wisconsin-Madison
2. Major employers include `Epic Systems`, `American Family Insurance`, and `Zendesk`
3. **Competitive market** with good work-life balance
4. Remote work options are **increasingly expected**

## Recommendations
- Offer competitive salaries in the $85k-$120k range
- Emphasize company culture and benefits
- Consider hybrid/remote work arrangements
- Partner with local universities for talent pipeline

**Conclusion**: Madison offers excellent opportunities for hiring quality software developers with reasonable competition and strong local talent."""
    
    result = format_ai_response(realistic_response)
    
    # Verify the response is well-formatted and readable
    assert len(result) > len(realistic_response)  # Should be longer due to HTML formatting
    assert '<div style="font-family: \'Inter\'' in result
    assert '<h3 style="color: #1e40af' in result
    assert '<strong>' in result
    assert '<code style="background-color: #f3f4f6' in result
    assert 'overflow-wrap: break-word' in result

if __name__ == "__main__":
    # Run a quick test to verify formatting works
    test_response = """### Test Response

This is a **test response** with:

- Bullet points
- Code snippets with `format_ai_response`
- Multiple paragraphs

1. Numbered items
2. More items

Regular text at the end."""
    
    formatted = format_ai_response(test_response)
    print("✅ Formatting test completed successfully!")
    print(f"Original length: {len(test_response)}")
    print(f"Formatted length: {len(formatted)}")
    print("\nFormatted output preview:")
    print(formatted)
    
    # Verify key elements are properly formatted
    print("Checking for header...")
    assert '<h3 style="color: #1e40af' in formatted, "Header not found"
    print("Checking for bullet list...")
    assert '<ul style="margin: 0.8rem 0' in formatted, f"Bullet list not found. Content: {formatted}"
    print("Checking for numbered list...")
    assert '<ol style="margin: 0.8rem 0' in formatted, "Numbered list not found"
    print("Checking for bold text...")
    assert '<strong>test response</strong>' in formatted, "Bold text not found"
    print("Checking for code...")
    assert '<code style="background-color: #f3f4f6' in formatted, "Code formatting not found"
    print("Checking for paragraph...")
    assert '<p style="margin: 0.8rem 0' in formatted, "Paragraph not found"
    print("✅ All formatting elements verified!")
    
    # Test a simple case to debug
    simple_test = "### Header\n\n- Item 1\n- Item 2"
    simple_result = format_ai_response(simple_test)
    print(f"\nSimple test result: {simple_result}")
    assert '<ul style="margin: 0.8rem 0' in simple_result, f"Simple bullet list failed: {simple_result}"
