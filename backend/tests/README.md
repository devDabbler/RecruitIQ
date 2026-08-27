# AI Assistant Comprehensive Test Suite

This directory contains a comprehensive test suite for the RecruitIQ AI assistant chatbot functionality. The tests are designed to be lightweight, fast, and cover all major aspects of the assistant system without requiring heavy external dependencies.

## Overview

The test suite covers:

- **Intent Detection**: Tests the AI's ability to understand user queries and categorize them into appropriate intents
- **Chat Endpoint**: Tests the main chat API endpoint with various message types
- **Error Handling**: Tests edge cases and error scenarios
- **Performance**: Tests response times and system stability
- **Service Integration**: Tests integration with various backend services

## Test Structure

### Core Test Files

- `test_ai_assistant_comprehensive.py` - Main test suite with 53 test cases

### Test Categories

1. **Intent Detection Tests** (30+ test cases)
   - Basic edge cases (empty messages, very long messages)
   - Travel-related queries
   - Candidate search queries
   - Email generation requests
   - Salary and company information queries
   - General questions and help requests

2. **Chat Endpoint Tests** (15+ test cases)
   - Basic message processing
   - Conversation history handling
   - Context-aware responses
   - Error handling (malformed payloads, missing fields)
   - Performance testing

3. **Service Integration Tests** (8 test cases)
   - Intent processor initialization
   - Travel service integration
   - Email service integration
   - Search service integration
   - Error handling scenarios

## Key Features

### Lightweight Mocking
- Uses dummy services instead of real LLM calls
- Minimal token usage while maintaining test coverage
- Fast execution (all tests complete in ~11 seconds)

### Flexible Intent Detection
- Accepts multiple valid intents for ambiguous queries
- Handles the dynamic nature of AI intent classification
- Tests both exact matches and acceptable alternatives

### Comprehensive Coverage
- Edge cases and error scenarios
- Conversation context and history
- Performance and stability
- API validation and error responses

## Running the Tests

```bash
# Run all tests
poetry run pytest fast_tests/test_ai_assistant_comprehensive.py -q

# Run with verbose output
poetry run pytest fast_tests/test_ai_assistant_comprehensive.py -v

# Run specific test categories
poetry run pytest fast_tests/test_ai_assistant_comprehensive.py::test_detect_intent -v
poetry run pytest fast_tests/test_ai_assistant_comprehensive.py::test_chat_endpoint -v
```

## Test Data

### Intent Test Cases
The test suite includes 30+ intent detection test cases covering:

- **Travel Queries**: "How long does it take to drive from Boston to New York?"
- **Search Queries**: "Find python developers", "Search for React developers"
- **Email Generation**: "Generate recruiter outreach email for software engineer role"
- **Salary Queries**: "What is the average salary for DevOps engineer in Seattle?"
- **General Questions**: "What's the weather like on Mars?"

### Chat Endpoint Test Cases
Tests various message types and scenarios:

- Empty messages and whitespace
- Very long messages (500+ characters)
- Normal queries in different categories
- Conversation history and context
- Malformed payloads and error conditions

## Mock Services

The test suite uses lightweight mock services to avoid external dependencies:

- **DummyLLMService**: Returns fixed responses without making real LLM calls
- **DummyTravelService**: Simulates travel information responses
- **DummyWebSearchService**: Simulates web search results

## Configuration

The test suite is configured to:

- Use session-scoped fixtures for service stubbing
- Run with minimal external dependencies
- Provide comprehensive coverage without heavy resource usage
- Handle dynamic intent detection gracefully

## Expected Results

When all tests pass, you should see:
```
53 passed in 11.38s
```

This indicates that:
- All intent detection scenarios work correctly
- The chat endpoint responds properly to all test cases
- Error handling works as expected
- Performance is within acceptable limits
- Service integration is functioning correctly

## Troubleshooting

If tests fail:

1. **Check endpoint paths**: Ensure `/api/assistant/chat` is the correct endpoint
2. **Verify intent expectations**: The intent processor may return different intents for similar queries
3. **Check service stubbing**: Ensure mock services are properly injected
4. **Review error messages**: Look for specific failure reasons in test output

## Adding New Tests

To add new test cases:

1. Add new intent test cases to `intent_cases` or `additional_test_cases`
2. Add new chat endpoint tests to `chat_messages`
3. Create new test functions for specific scenarios
4. Ensure tests are flexible enough to handle dynamic AI responses

## Integration with CI/CD

This test suite is designed to run quickly in CI/CD pipelines:

- No external API dependencies
- Fast execution time
- Comprehensive coverage
- Reliable results

The tests can be integrated into your CI/CD pipeline to ensure the AI assistant functionality remains stable across deployments. 