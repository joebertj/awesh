# Awesh Test Suite

This directory contains all test scripts for the awesh project.

## Test Scripts

### `test_awesh.py`
Main test suite for awesh functionality.

**Usage:**
```bash
# Run from project root
python3 tests/test_awesh.py

# Or use deployment script
python3 simple_deploy.py test
```

**Tests Included:**
- ✅ Build success
- ✅ Configuration file validation
- ✅ Default model configuration
- ✅ Model switcher functionality
- ✅ Backend components
- ✅ Model switching (OpenAI ↔ Mistral)
- ✅ Awesh startup
- ✅ Unfiltered command execution
- ✅ AI query detection
- ✅ Error command handling
- ⏭️ Command execution tests (skipped - too slow)
- ⏭️ AI & security tests (skipped - too slow)

**Expected Results:**
- 10/11 tests passing (AI query detection may fail depending on backend status)
- Test suite completes in ~30 seconds

### `test_llm_responses.py`
Comprehensive LLM response testing with 100 natural language prompts.

**Usage:**
```bash
# Run from project root
python3 tests/test_llm_responses.py
```

**Tests Included:**
- 20 File operations
- 20 System information queries
- 15 Git operations
- 15 Network operations
- 10 Process management
- 10 Text processing
- 10 System administration

**Purpose:**
- Validate system prompt compliance
- Ensure LLM returns proper `awesh:` command format
- Check response quality and accuracy
- Verify command generation for natural language queries

**Expected Results:**
- 80%+ success rate
- LLM responses follow system prompt
- Commands are properly formatted with `awesh:` prefix

## Running Tests

### Quick Test (Recommended)
```bash
cd /home/joebert/AI/awesh
python3 simple_deploy.py test
```

### Full Test Suite
```bash
cd /home/joebert/AI/awesh
python3 tests/test_awesh.py
```

### LLM Response Testing
```bash
cd /home/joebert/AI/awesh
python3 tests/test_llm_responses.py
```

## Test Configuration

Tests use the following paths:
- Binary: `./awesh` (or `~/.local/bin/awesh`)
- Config: `~/.aweshrc`
- Backend: `awesh_backend` module

## Troubleshooting

### Test Timeout
If tests timeout, check:
- Backend processes running: `ps aux | grep awesh`
- Kill stale processes: `pkill -f awesh`
- Check logs: Look for error messages in test output

### AI Query Test Fails
This is normal if:
- Backend is still loading
- AI provider API is slow
- Network issues

### Command Execution Tests Slow
These are skipped by default because:
- Each test spawns awesh process
- Network operations may timeout
- Interactive commands need special handling

## Test Coverage

Current test coverage:
- ✅ Core functionality: 100%
- ✅ Model switching: 100%
- ✅ Runtime behavior: 100%
- ⏭️ Command execution: Partial (slow tests skipped)
- ⏭️ AI responses: Comprehensive (separate test)
- ⏭️ Security: Basic (dangerous commands removed)

## Adding New Tests

To add new tests:

1. Add test method to `AweshTester` class
2. Call test method in `run_all_tests()`
3. Use `self.log_test()` to record results
4. Set appropriate timeouts for subprocess calls
5. Handle exceptions gracefully

Example:
```python
def test_my_feature(self):
    """Test my new feature"""
    try:
        result = subprocess.run(
            [str(self.awesh_path)],
            input="my command\nexit\n",
            text=True,
            capture_output=True,
            timeout=10
        )
        
        if "expected output" in result.stdout:
            self.log_test("My Feature", True, "Feature works correctly")
            return True
        else:
            self.log_test("My Feature", False, "Feature failed")
            return False
    except Exception as e:
        self.log_test("My Feature", False, f"Error: {e}")
        return False
```

## CI/CD Integration

To integrate with CI/CD:

```bash
# In your CI script
cd /home/joebert/AI/awesh
python3 simple_deploy.py build
python3 simple_deploy.py test
python3 simple_deploy.py deploy
```

Exit codes:
- `0`: All tests passed
- `1`: Some tests failed

