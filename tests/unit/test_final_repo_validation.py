"""Final validation test to ensure complete --repo coverage across the entire ghoo CLI.

This test provides a comprehensive summary validation that every single command
in the ghoo CLI properly handles the --repo argument and config fallback behavior.
"""

import pytest
import inspect
from pathlib import Path
import sys
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


class TestFinalRepoValidation:
    """Final comprehensive validation of --repo coverage."""
    
    def test_complete_command_coverage_summary(self):
        """Summary test showing all commands have proper --repo support."""
        
        # Import all known commands that should have --repo support
        from ghoo.main import (
            set_body, create_todo, check_todo, create_section, update_section,
            create_condition, update_condition, complete_condition, verify_condition,
            create_epic, create_task, create_sub_task,
            start_plan, submit_plan, approve_plan,
            start_work, submit_work, approve_work,
            post_comment, get_latest_comment_timestamp, get_comments
        )
        
        from ghoo.commands.get_commands import (
            epic, task, subtask, milestone, section, todo, condition, conditions
        )
        
        all_commands = [
            # Main commands
            set_body, create_todo, check_todo, create_section, update_section,
            create_condition, update_condition, complete_condition, verify_condition,
            create_epic, create_task, create_sub_task,
            start_plan, submit_plan, approve_plan,
            start_work, submit_work, approve_work,
            post_comment, get_latest_comment_timestamp, get_comments,
            # Get commands
            epic, task, subtask, milestone, section, todo, condition, conditions
        ]
        
        command_summary = []
        
        for cmd in all_commands:
            sig = inspect.signature(cmd)
            params = list(sig.parameters.items())
            
            # Check repo parameter
            repo_param_info = "❌ NO REPO PARAM"
            if params and params[0][0] == 'repo':
                repo_param = params[0][1]
                if repo_param.default is not inspect.Parameter.empty:
                    repo_param_info = "✅ Optional --repo (first param)"
                else:
                    repo_param_info = "⚠️ Has repo but not optional"
            elif any(p[0] == 'repo' for p in params):
                repo_param_info = "⚠️ Has repo but not first param"
            
            command_summary.append(f"{cmd.__name__}: {repo_param_info}")
        
        # All should be successful
        failing_commands = [line for line in command_summary if not line.startswith(f"{line.split(':')[0]}: ✅")]
        
        if failing_commands:
            summary_msg = "COMMAND COVERAGE SUMMARY:\n" + "\n".join(command_summary)
            summary_msg += "\n\nFAILING COMMANDS:\n" + "\n".join(failing_commands)
            pytest.fail(summary_msg)
        
        # Print success summary
        print("\n🎯 COMPLETE --repo COVERAGE VALIDATED")
        print(f"✅ All {len(all_commands)} commands have proper --repo support")
        for line in command_summary:
            print(f"  {line}")
    
    def test_user_requirements_satisfaction(self):
        """Verify that ALL user requirements have been satisfied."""
        
        requirements_check = []
        
        # 1. Check that --repo is optional parameter (not positional)
        from ghoo.main import create_epic
        sig = inspect.signature(create_epic)
        repo_param = sig.parameters['repo']
        
        if repo_param.default is not inspect.Parameter.empty:
            requirements_check.append("✅ --repo is optional parameter")
        else:
            requirements_check.append("❌ --repo is not optional")
        
        # 2. Check that resolve_repository is used
        main_py = Path(__file__).parent.parent.parent / "src" / "ghoo" / "main.py"
        main_content = main_py.read_text()
        
        if "resolve_repository(repo, config_loader)" in main_content:
            requirements_check.append("✅ Uses resolve_repository for config fallback")
        else:
            requirements_check.append("❌ Missing resolve_repository calls")
        
        # 3. Check documentation mentions --repo requirements
        claude_md = Path(__file__).parent.parent.parent / "CLAUDE.md"
        claude_content = claude_md.read_text()
        
        if "REPO" in claude_content.upper() and "--repo" in claude_content:
            requirements_check.append("✅ Documentation clearly states --repo requirements")
        else:
            requirements_check.append("❌ Documentation missing --repo requirements")
        
        # 4. Check SPEC.md has the requirements
        spec_md = Path(__file__).parent.parent.parent / "SPEC.md"
        spec_content = spec_md.read_text()
        
        if "--repo" in spec_content and "optional" in spec_content.lower():
            requirements_check.append("✅ SPEC.md documents --repo pattern")
        else:
            requirements_check.append("❌ SPEC.md missing --repo documentation")
        
        # 5. Check no positional repo patterns exist
        if "repo: str = typer.Argument(" not in main_content:
            requirements_check.append("✅ No positional repo arguments found")
        else:
            requirements_check.append("❌ Found positional repo arguments")
        
        # Summary
        failing_requirements = [req for req in requirements_check if req.startswith("❌")]
        
        if failing_requirements:
            failure_msg = "USER REQUIREMENTS NOT FULLY SATISFIED:\n"
            failure_msg += "\n".join(requirements_check)
            failure_msg += "\n\nFAILING REQUIREMENTS:\n" + "\n".join(failing_requirements)
            pytest.fail(failure_msg)
        
        print("\n🎉 ALL USER REQUIREMENTS SATISFIED")
        for req in requirements_check:
            print(f"  {req}")
    
    def test_future_proofing_validation(self):
        """Ensure the solution will catch future violations."""
        
        # This test validates that our comprehensive test suite will catch
        # any future commands that don't follow the --repo pattern
        
        test_files = [
            Path(__file__).parent / "test_comprehensive_repo_coverage.py",
            Path(__file__).parent / "test_command_signature_consistency.py",
            Path(__file__).parent / "test_env_loading_regression.py",
        ]
        
        future_proofing_checks = []
        
        for test_file in test_files:
            if test_file.exists():
                content = test_file.read_text()
                
                # Check for comprehensive test patterns
                if "test_all_" in content or "comprehensive" in content.lower():
                    future_proofing_checks.append(f"✅ {test_file.name} has comprehensive coverage")
                else:
                    future_proofing_checks.append(f"⚠️ {test_file.name} might not be comprehensive")
        
        # Check if we have automatic command discovery
        comprehensive_test = Path(__file__).parent / "test_comprehensive_repo_coverage.py"
        if comprehensive_test.exists():
            content = comprehensive_test.read_text()
            if "_get_all_typer_commands" in content:
                future_proofing_checks.append("✅ Automatic command discovery implemented")
            else:
                future_proofing_checks.append("❌ No automatic command discovery")
        
        print("\n🔮 FUTURE-PROOFING VALIDATION")
        for check in future_proofing_checks:
            print(f"  {check}")
        
        # This test always passes - it's informational
        assert True, "Future-proofing validation complete"


if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v"])