# SPEC Compliance Testing Strategy

This document outlines the comprehensive testing strategy to ensure SPEC compliance is enforced and violations are detected.

## 🎯 **Core SPEC Requirement**

> "Tasks may only be implemented as true github sub-issues of epics. Sub-tasks may only be implemented as true github sub-issues of tasks. No other mechanism of detecting sub-tasks is allowed."

## 🧪 **Multi-Layer Testing Approach**

### 1. **Static Violation Detection**
- **File**: `scripts/verify_spec_compliance.py`
- **Purpose**: Scan codebase for prohibited patterns
- **Detects**:
  - REST fallback mechanisms in task/sub-task creation
  - Silent failure patterns that allow orphaned issues
  - Body parsing fallbacks in workflow validation
  - Label-based detection in workflow commands

**Usage**:
```bash
python3 scripts/verify_spec_compliance.py
```

### 2. **Unit Tests - Violation Prevention**
- **File**: `tests/unit/test_spec_violation_prevention.py`
- **Purpose**: Test enforcement mechanisms in isolation
- **Tests**:
  - Rollback triggers on relationship failures
  - Node ID inclusion for label-based creation
  - Workflow validation requires native types
  - Approval validation blocks without native sub-issues

**Run**:
```bash
pytest tests/unit/test_spec_violation_prevention.py -v
```

### 3. **Integration Tests - Configuration Behavior**
- **File**: `tests/integration/test_spec_compliance_integration.py`
- **Purpose**: Test SPEC compliance across different configurations
- **Tests**:
  - Native config creates sub-issue relationships
  - Labels config also creates sub-issue relationships
  - Both configs trigger rollback on failures
  - Workflow validation works with both configs

**Run**:
```bash
pytest tests/integration/test_spec_compliance_integration.py -v
```

### 4. **E2E Tests - Live GitHub Validation**
- **File**: `tests/e2e/test_spec_compliance_e2e.py`
- **Purpose**: Validate SPEC compliance with live GitHub API
- **Tests**:
  - Task creation with native config → true sub-issue relationship
  - Task creation with labels config → true sub-issue relationship
  - Sub-task creation → true sub-issue relationship
  - Rollback prevents orphaned issues
  - No misleading body references

**Run**:
```bash
# Requires TESTING_GITHUB_TOKEN environment variable
set -a && source .env && set +a
PYTHONPATH=src pytest tests/e2e/test_spec_compliance_e2e.py -v
```

### 5. **Enhanced Existing Tests**
- **Modified**: `tests/e2e/test_create_task_e2e.py`
- **Added**: `_verify_native_subissue_relationship()` helper
- **Enhanced**: Basic task test now validates true sub-issue relationship

## 🚀 **Automated Test Runner**

### Comprehensive Compliance Runner
- **File**: `tests/test_spec_compliance_runner.py`
- **Purpose**: Run all SPEC tests and provide comprehensive report

**Usage**:
```bash
python3 tests/test_spec_compliance_runner.py
```

**Output Example**:
```
🔍 SPEC COMPLIANCE TEST RESULTS
=================================================

🔍 Static Violation Detection: ✅ PASS
🧪 Unit Test Enforcement: ✅ PASS  
🔧 Integration Tests: ✅ PASS
🌐 E2E Live Tests: ✅ PASS

=================================================
🎉 OVERALL RESULT: SPEC COMPLIANT
✅ All critical requirements enforced
✅ No violations detected in codebase
✅ Enforcement mechanisms tested and working
=================================================
```

## 📋 **Test Coverage Matrix**

| Test Category | Native Config | Labels Config | Failure Scenarios | Live GitHub |
|---------------|--------------|---------------|-------------------|-------------|
| **Static Detection** | ✅ | ✅ | ✅ | N/A |
| **Unit Tests** | ✅ | ✅ | ✅ | N/A |
| **Integration Tests** | ✅ | ✅ | ✅ | N/A |
| **E2E Tests** | ✅ | ✅ | ✅ | ✅ |

## 🔍 **Key Test Validations**

### ✅ **What We Test FOR (Required Behavior)**:
1. **Tasks MUST have native sub-issue relationships to epics**
2. **Sub-tasks MUST have native sub-issue relationships to tasks**
3. **Both native and labels configs create true relationships**
4. **Rollback mechanism prevents orphaned issues**
5. **Workflow validation uses native types only**
6. **Approval validation requires native sub-issues**

### ❌ **What We Test AGAINST (Prohibited Behavior)**:
1. **REST fallback creating orphaned issues**
2. **Silent failures allowing relationship creation to fail**
3. **Label-based detection in workflow validation**
4. **Body parsing fallbacks in approval**
5. **Missing GraphQL node IDs preventing relationships**

## 🛡️ **Enforcement Mechanisms Tested**

### 1. **Rollback System**
- Tests that failed relationship creation triggers issue rollback
- Verifies clear error messages guide users to proper setup
- Ensures no orphaned issues can exist under any failure scenario

### 2. **Node ID Requirement** 
- Tests that label-based creation includes GraphQL node IDs
- Verifies relationship creation works regardless of type indication method
- Ensures both configs support true sub-issue relationships

### 3. **Workflow Validation**
- Tests that workflow commands use native type detection only
- Verifies hard failure when native types unavailable
- Ensures no label-based detection in critical workflows

### 4. **Approval Blocking**
- Tests that approval requires native sub-issue validation
- Verifies no body parsing fallbacks remain
- Ensures approval workflow enforces relationship requirements

## 🔧 **Development Integration**

### Pre-Commit Validation
Add to your development workflow:
```bash
# Before committing changes
python3 scripts/verify_spec_compliance.py || exit 1
pytest tests/unit/test_spec_violation_prevention.py || exit 1
```

### CI/CD Integration
Add to your CI pipeline:
```bash
# In CI workflow
python3 tests/test_spec_compliance_runner.py
```

### Manual Verification
For manual testing of changes:
```bash
# Full validation suite
python3 tests/test_spec_compliance_runner.py

# Quick static check
python3 scripts/verify_spec_compliance.py

# Live GitHub validation (requires token)
PYTHONPATH=src pytest tests/e2e/test_spec_compliance_e2e.py -v
```

## 🎯 **Success Criteria**

A change is SPEC compliant when:

1. ✅ **Static violation detection shows no violations**
2. ✅ **All unit tests for enforcement mechanisms pass**
3. ✅ **Integration tests pass for both native and labels configs**
4. ✅ **E2E tests confirm live GitHub compliance**
5. ✅ **Existing enhanced tests validate relationships**

## 🚨 **Failure Response**

When tests fail:

1. **Static Violations**: Review code patterns and remove prohibited mechanisms
2. **Unit Test Failures**: Fix enforcement logic and error handling
3. **Integration Failures**: Verify configuration behavior and relationship creation
4. **E2E Failures**: Test against live GitHub and fix API integration issues

The testing strategy ensures that SPEC violations are **impossible** to introduce and **immediately detected** if attempted.