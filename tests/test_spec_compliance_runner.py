"""Automated SPEC compliance test runner and validation framework."""

import subprocess
import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple


class SpecComplianceTestRunner:
    """Automated runner for SPEC compliance tests with comprehensive reporting."""
    
    def __init__(self, ghoo_root: Path):
        self.ghoo_root = ghoo_root
        self.test_results = {}
        
    def run_all_spec_tests(self) -> Dict[str, Any]:
        """Run all SPEC compliance tests and return comprehensive results."""
        print("🔍 RUNNING COMPREHENSIVE SPEC COMPLIANCE TESTS")
        print("=" * 60)
        
        # 1. Run static violation detection
        violation_results = self._run_violation_detection()
        
        # 2. Run unit tests for SPEC enforcement
        unit_results = self._run_unit_spec_tests()
        
        # 3. Run integration tests
        integration_results = self._run_integration_spec_tests()
        
        # 4. Run E2E tests (if environment available)
        e2e_results = self._run_e2e_spec_tests()
        
        # Compile comprehensive report
        return {
            'violation_detection': violation_results,
            'unit_tests': unit_results,
            'integration_tests': integration_results,
            'e2e_tests': e2e_results,
            'overall_compliance': self._assess_overall_compliance()
        }
    
    def _run_violation_detection(self) -> Dict[str, Any]:
        """Run the automated violation detection script."""
        print("\\n🔍 Running static SPEC violation detection...")
        
        try:
            script_path = self.ghoo_root / "scripts" / "verify_spec_compliance.py"
            result = subprocess.run([
                sys.executable, str(script_path)
            ], capture_output=True, text=True, cwd=self.ghoo_root)
            
            return {
                'success': result.returncode == 0,
                'output': result.stdout,
                'errors': result.stderr,
                'violations_found': result.returncode != 0
            }
        except Exception as e:
            return {
                'success': False,
                'output': '',
                'errors': str(e),
                'violations_found': True
            }
    
    def _run_unit_spec_tests(self) -> Dict[str, Any]:
        """Run unit tests specifically for SPEC compliance."""
        print("\\n🧪 Running unit tests for SPEC violation prevention...")
        
        return self._run_pytest_tests([
            "tests/unit/test_spec_violation_prevention.py"
        ])
    
    def _run_integration_spec_tests(self) -> Dict[str, Any]:
        """Run integration tests for SPEC compliance."""
        print("\\n🔧 Running integration tests for SPEC compliance...")
        
        return self._run_pytest_tests([
            "tests/integration/test_spec_compliance_integration.py"
        ])
    
    def _run_e2e_spec_tests(self) -> Dict[str, Any]:
        """Run E2E tests for SPEC compliance (if environment available)."""
        print("\\n🌐 Running E2E tests for SPEC compliance...")
        
        # Check if E2E environment is available
        if not os.getenv('TESTING_GITHUB_TOKEN'):
            return {
                'success': False,
                'skipped': True,
                'reason': 'No TESTING_GITHUB_TOKEN environment variable'
            }
        
        return self._run_pytest_tests([
            "tests/e2e/test_spec_compliance_e2e.py"
        ])
    
    def _run_pytest_tests(self, test_files: List[str]) -> Dict[str, Any]:
        """Run specific pytest test files."""
        try:
            # Set up environment
            env = os.environ.copy()
            env['PYTHONPATH'] = str(self.ghoo_root / "src")
            
            cmd = [sys.executable, "-m", "pytest"] + test_files + ["-v", "--tb=short"]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.ghoo_root,
                env=env
            )
            
            return {
                'success': result.returncode == 0,
                'output': result.stdout,
                'errors': result.stderr,
                'test_files': test_files
            }
        except Exception as e:
            return {
                'success': False,
                'output': '',
                'errors': str(e),
                'test_files': test_files
            }
    
    def _assess_overall_compliance(self) -> Dict[str, Any]:
        """Assess overall SPEC compliance based on all test results."""
        all_success = all([
            self.test_results.get('violation_detection', {}).get('success', False),
            self.test_results.get('unit_tests', {}).get('success', False),
            self.test_results.get('integration_tests', {}).get('success', False),
            self.test_results.get('e2e_tests', {}).get('success', False) or 
            self.test_results.get('e2e_tests', {}).get('skipped', False)
        ])
        
        return {
            'compliant': all_success,
            'critical_violations': not self.test_results.get('violation_detection', {}).get('success', False),
            'enforcement_tested': self.test_results.get('unit_tests', {}).get('success', False),
            'integration_verified': self.test_results.get('integration_tests', {}).get('success', False),
            'e2e_validated': self.test_results.get('e2e_tests', {}).get('success', False)
        }
    
    def print_compliance_report(self, results: Dict[str, Any]):
        """Print a comprehensive compliance report."""
        print("\\n" + "=" * 60)
        print("📊 SPEC COMPLIANCE TEST RESULTS")
        print("=" * 60)
        
        # Violation Detection
        vd = results['violation_detection']
        status = "✅ PASS" if vd['success'] else "❌ FAIL"
        print(f"\\n🔍 Static Violation Detection: {status}")
        if not vd['success']:
            print(f"   ⚠️  Violations found in codebase")
            print(f"   📄 Output: {vd['output'][:200]}...")
        
        # Unit Tests
        ut = results['unit_tests']
        status = "✅ PASS" if ut['success'] else "❌ FAIL"
        print(f"\\n🧪 Unit Test Enforcement: {status}")
        if not ut['success']:
            print(f"   ⚠️  SPEC enforcement mechanisms failing")
        
        # Integration Tests
        it = results['integration_tests']
        status = "✅ PASS" if it['success'] else "❌ FAIL"
        print(f"\\n🔧 Integration Tests: {status}")
        if not it['success']:
            print(f"   ⚠️  Configuration behavior not compliant")
        
        # E2E Tests
        e2e = results['e2e_tests']
        if e2e.get('skipped'):
            status = "⏭️  SKIPPED"
            print(f"\\n🌐 E2E Live Tests: {status}")
            print(f"   ℹ️  {e2e['reason']}")
        else:
            status = "✅ PASS" if e2e['success'] else "❌ FAIL"
            print(f"\\n🌐 E2E Live Tests: {status}")
            if not e2e['success']:
                print(f"   ⚠️  Live GitHub integration not compliant")
        
        # Overall Assessment
        overall = results['overall_compliance']
        print(f"\\n" + "=" * 60)
        if overall['compliant']:
            print("🎉 OVERALL RESULT: SPEC COMPLIANT")
            print("✅ All critical requirements enforced")
            print("✅ No violations detected in codebase")
            print("✅ Enforcement mechanisms tested and working")
        else:
            print("🚨 OVERALL RESULT: SPEC VIOLATIONS DETECTED")
            if overall['critical_violations']:
                print("❌ Critical violations found in codebase")
            if not overall['enforcement_tested']:
                print("❌ Enforcement mechanisms not properly tested")
            if not overall['integration_verified']:
                print("❌ Integration behavior not verified")
            if not overall['e2e_validated']:
                print("❌ Live behavior not validated")
        print("=" * 60)


def main():
    """Main entry point for SPEC compliance testing."""
    ghoo_root = Path(__file__).parent.parent
    runner = SpecComplianceTestRunner(ghoo_root)
    
    try:
        results = runner.run_all_spec_tests()
        runner.test_results = results
        runner.print_compliance_report(results)
        
        # Exit with appropriate code
        sys.exit(0 if results['overall_compliance']['compliant'] else 1)
        
    except Exception as e:
        print(f"❌ SPEC compliance testing failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()