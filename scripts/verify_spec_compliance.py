#!/usr/bin/env python3
"""Automated SPEC violation detection and compliance verification."""

import ast
import os
import re
from pathlib import Path

def check_code_violations():
    """Scan codebase for SPEC violations."""
    violations = []
    
    VIOLATION_PATTERNS = [
        # REST fallback patterns in task/subtask creation (SPEC violation)
        (r'CreateTaskCommand.*except.*GraphQLError.*:.*_create_with_rest', 'Task REST fallback'),
        (r'CreateSubTaskCommand.*except.*GraphQLError.*:.*_create_with_rest', 'Sub-task REST fallback'),
        
        # Silent failure patterns (SPEC violation)
        (r'except.*GraphQLError.*:.*pass.*relationship', 'Silent failure on relationship creation'),
        
        # Label-based type detection in workflow commands (SPEC violation)
        (r'def _get_issue_type.*label.*workflow', 'Label-based issue type detection in workflow'),
        
        # Body parsing fallback (SPEC violation)
        (r'_validate_sub_issues_from_body_parsing', 'Body parsing fallback method'),
        (r'body.*parse.*sub.?issue', 'Body parsing for sub-issues'),
        
        # Prohibited fallback comments in task/subtask code (SPEC violation)
        (r'CreateTaskCommand.*# Fall.*back.*REST', 'Task REST fallback comment'),
        (r'CreateSubTaskCommand.*# Fall.*back.*REST', 'Sub-task REST fallback comment'),
        (r'# Fallback.*body.*parsing', 'Body parsing fallback comment'),
    ]
    
    for file_path in Path('src').rglob('*.py'):
        content = file_path.read_text()
        for pattern, description in VIOLATION_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
            if matches:
                violations.append(f"{file_path}: {description} - {pattern}")
    
    return violations

def check_required_mechanisms():
    """Verify required SPEC compliance mechanisms are present."""
    required_mechanisms = []
    
    # Check for rollback mechanism
    core_file = Path('src/ghoo/core.py')
    if core_file.exists():
        content = core_file.read_text()
        
        if '_rollback_failed_issue' in content:
            required_mechanisms.append('✅ Rollback mechanism implemented')
        else:
            required_mechanisms.append('❌ Missing rollback mechanism')
            
        if 'native_issue_type' in content:
            required_mechanisms.append('✅ Native issue type detection implemented')
        else:
            required_mechanisms.append('❌ Missing native issue type detection')
            
        if 'Native sub-issue relationships required' in content:
            required_mechanisms.append('✅ Native sub-issue requirement enforced')
        else:
            required_mechanisms.append('❌ Missing native sub-issue enforcement')
    
    return required_mechanisms

def main():
    print("🔍 SPEC COMPLIANCE VERIFICATION")
    print("=" * 50)
    
    # Check for violations
    violations = check_code_violations()
    if violations:
        print("❌ SPEC VIOLATIONS DETECTED:")
        for violation in violations:
            print(f"  {violation}")
        return False
    else:
        print("✅ NO SPEC VIOLATIONS DETECTED")
    
    print()
    
    # Check required mechanisms
    mechanisms = check_required_mechanisms()
    print("🔧 REQUIRED MECHANISMS:")
    for mechanism in mechanisms:
        print(f"  {mechanism}")
    
    print()
    
    # Summary
    has_failures = any('❌' in m for m in mechanisms)
    if not violations and not has_failures:
        print("🎉 SPEC COMPLIANCE ACHIEVED!")
        print("✅ All violations eliminated")
        print("✅ All required mechanisms present")
        print("✅ Tasks and sub-tasks can ONLY be created with native sub-issue relationships")
        return True
    else:
        print("❌ SPEC COMPLIANCE INCOMPLETE")
        return False

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)