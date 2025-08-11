# E2E Testing Prevention Checklist

## **MANDATORY Pre-Test Validation**
Always complete these steps before claiming E2E tests pass:

### 1. **Environment Setup**
- [ ] Verify `.env` file exists and contains `TESTING_GITHUB_TOKEN` and `TESTING_GH_REPO`
- [ ] Use `set -a && source .env && set +a` to properly export all variables
- [ ] Validate environment variables are visible to Python: 
  ```bash
  python3 -c "import os; print(f'TOKEN: {len(os.getenv(\"TESTING_GITHUB_TOKEN\", \"\"))} chars')"
  ```

### 2. **Test Execution**
- [ ] Run E2E tests with proper environment:
  ```bash
  set -a && source .env && set +a && PYTHONPATH=/home/justyn/ghoo/src python3 -m pytest tests/e2e/test_workflow_logging_e2e.py -v
  ```
- [ ] Verify tests are **RUNNING** (not SKIPPED)
- [ ] Verify tests are **PASSING** (not FAILING)

### 3. **Documentation Compliance**
- [ ] Check CLAUDE.md requirements for E2E testing
- [ ] Ensure testing follows documented procedures
- [ ] Validate against any "MANDATORY" requirements

### 4. **Result Validation**
- [ ] **NEVER** claim tests are passing if they are skipped
- [ ] **ALWAYS** run actual tests against live GitHub when available
- [ ] **VERIFY** test output shows expected behavior

## **Common Pitfalls to Avoid**

### ❌ **Wrong**: `source .env && pytest`
This doesn't export variables for child processes.

### ✅ **Correct**: `set -a && source .env && set +a && pytest`
This properly exports all variables from .env file.

### ❌ **Wrong**: Assuming skipped tests = passing tests
Skipped tests provide NO validation of functionality.

### ✅ **Correct**: Only count actually executed tests as validation

## **Repository Format Issues**
- Check if `TESTING_GH_REPO` is URL format (`https://github.com/owner/repo`)
- Extract `owner/repo` format if needed: `'/'.join(url.split('/')[-2:])`

## **Quick Validation Commands**

```bash
# 1. Check environment is loaded
set -a && source .env && set +a && python3 -c "import os; print('TOKEN:', len(os.getenv('TESTING_GITHUB_TOKEN', ''))); print('REPO:', os.getenv('TESTING_GH_REPO'))"

# 2. Run single test to verify setup
set -a && source .env && set +a && PYTHONPATH=/home/justyn/ghoo/src python3 -m pytest tests/e2e/test_workflow_logging_e2e.py::TestWorkflowLoggingE2E::test_workflow_logging_unicode_support -v

# 3. Run all tests for complete validation
set -a && source .env && set +a && PYTHONPATH=/home/justyn/ghoo/src python3 -m pytest tests/e2e/test_workflow_logging_e2e.py -v
```

## **Final Rule**
**NEVER claim E2E tests are passing without seeing actual PASSED results, not SKIPPED results.**