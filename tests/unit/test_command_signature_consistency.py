"""Tests to ensure ALL state-changing commands have consistent signatures.

This test module verifies that all state-changing commands use positional
'repo' parameter as the first argument, ensuring complete consistency.
"""

import pytest
import inspect
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ghoo.main import (
    set_body, create_todo, check_todo, create_section, update_section,
    create_condition, update_condition, complete_condition, verify_condition,
    create_epic, create_task, create_sub_task,
    start_plan, submit_plan, approve_plan,
    start_work, submit_work, approve_work,
    post_comment
)


class TestCommandSignatureConsistency:
    """Test that all state-changing commands have consistent signatures."""
    
    def test_all_state_changing_commands_have_positional_repo(self):
        """Test that ALL state-changing commands use positional repo parameter."""
        
        # All state-changing commands that should have repo as FIRST positional argument
        state_changing_commands = [
            set_body, create_todo, check_todo, create_section, update_section,
            create_condition, update_condition, complete_condition, verify_condition,
            create_epic, create_task, create_sub_task,
            start_plan, submit_plan, approve_plan,
            start_work, submit_work, approve_work,
            post_comment
        ]
        
        for cmd in state_changing_commands:
            sig = inspect.signature(cmd)
            params = list(sig.parameters.items())
            
            # First parameter should be 'repo'
            assert len(params) > 0, f"Command {cmd.__name__} has no parameters"
            
            first_param_name, first_param = params[0]
            assert first_param_name == 'repo', f"Command {cmd.__name__} first parameter is '{first_param_name}', should be 'repo'"
            
            # repo parameter should be positional (Typer adds metadata so we check kind instead of default)
            assert first_param.kind in [inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD], \
                f"Command {cmd.__name__} repo parameter is not positional"
    
    def test_no_command_has_repo_as_option(self):
        """Test that no state-changing command uses --repo as an option."""
        
        state_changing_commands = [
            set_body, create_todo, check_todo, create_section, update_section,
            create_condition, update_condition, complete_condition, verify_condition,
            create_epic, create_task, create_sub_task,
            start_plan, submit_plan, approve_plan,
            start_work, submit_work, approve_work,
            post_comment
        ]
        
        for cmd in state_changing_commands:
            sig = inspect.signature(cmd)
            params = list(sig.parameters.items())
            
            # Repo should be first parameter and positional
            if len(params) > 0 and params[0][0] == 'repo':
                repo_param = params[0][1]
                # Should be positional, not keyword-only
                assert repo_param.kind != inspect.Parameter.KEYWORD_ONLY, \
                    f"Command {cmd.__name__} has --repo as option, should be positional"
    
    def test_condition_commands_consistency_with_others(self):
        """Test that condition commands have the same signature pattern as other commands."""
        
        # Condition commands
        condition_commands = [create_condition, update_condition, complete_condition, verify_condition]
        
        for cond_cmd in condition_commands:
            cond_sig = inspect.signature(cond_cmd)
            cond_params = list(cond_sig.parameters.items())
            
            # Should start with repo parameter
            assert len(cond_params) >= 2, f"Command {cond_cmd.__name__} should have at least repo and issue_number"
            assert cond_params[0][0] == 'repo'
            
            # Should have issue_number as second parameter
            assert cond_params[1][0] == 'issue_number'
            
    def test_all_commands_importable_and_callable(self):
        """Test that all state-changing commands are importable and callable."""
        
        commands = [
            set_body, create_todo, check_todo, create_section, update_section,
            create_condition, update_condition, complete_condition, verify_condition,
            create_epic, create_task, create_sub_task,
            start_plan, submit_plan, approve_plan,
            start_work, submit_work, approve_work,
            post_comment
        ]
        
        for cmd in commands:
            assert callable(cmd), f"Command {cmd.__name__} is not callable"
            assert hasattr(cmd, '__doc__'), f"Command {cmd.__name__} has no docstring"
            assert cmd.__doc__ is not None, f"Command {cmd.__name__} docstring is None"
    
    def test_command_signature_consistency_pattern(self):
        """Test that commands follow consistent signature patterns."""
        
        # Commands that modify issues should all follow the pattern:
        # def command(repo: str, issue_number: int, ...)
        issue_modifying_commands = [
            set_body, create_todo, check_todo, create_section, update_section,
            create_condition, update_condition, complete_condition, verify_condition,
            start_plan, submit_plan, approve_plan,
            start_work, submit_work, approve_work,
            post_comment
        ]
        
        for cmd in issue_modifying_commands:
            sig = inspect.signature(cmd)
            params = list(sig.parameters.items())
            
            # Should have at least repo and issue_number
            assert len(params) >= 2, f"Command {cmd.__name__} should have at least repo and issue_number parameters"
            
            # First two should be repo and issue_number (or similar)
            assert params[0][0] == 'repo'
            
            # Second parameter should be issue-related
            second_param_name = params[1][0]
            assert 'issue' in second_param_name or 'number' in second_param_name, \
                f"Command {cmd.__name__} second parameter '{second_param_name}' should be issue-related"
    
    def test_no_optional_repo_parameters_exist(self):
        """Comprehensive test to ensure state-changing commands use positional repo."""
        
        # Focus on the specific commands we know should be consistent
        state_changing_commands = [
            set_body, create_todo, check_todo, create_section, update_section,
            create_condition, update_condition, complete_condition, verify_condition,
            create_epic, create_task, create_sub_task,
            start_plan, submit_plan, approve_plan,
            start_work, submit_work, approve_work,
            post_comment
        ]
        
        for cmd in state_changing_commands:
            sig = inspect.signature(cmd)
            params = list(sig.parameters.items())
            
            # First parameter should be repo
            if len(params) > 0:
                assert params[0][0] == 'repo', f"Command {cmd.__name__} should have repo as first parameter"


class TestSpecificCommandPatterns:
    """Test specific patterns for different command types."""
    
    def test_creation_commands_pattern(self):
        """Test that creation commands follow consistent pattern."""
        creation_commands = [create_epic, create_task, create_sub_task, create_condition, create_todo, create_section]
        
        for cmd in creation_commands:
            sig = inspect.signature(cmd)
            params = list(sig.parameters.items())
            
            # All creation commands should start with repo
            assert params[0][0] == 'repo'
            
            # Should be callable
            assert callable(cmd)
    
    def test_workflow_commands_pattern(self):
        """Test that workflow commands follow consistent pattern."""
        workflow_commands = [start_plan, submit_plan, approve_plan, start_work, submit_work, approve_work]
        
        for cmd in workflow_commands:
            sig = inspect.signature(cmd)
            params = list(sig.parameters.items())
            
            # All workflow commands should start with repo, issue_number
            assert len(params) >= 2, f"Command {cmd.__name__} should have at least repo and issue_number"
            assert params[0][0] == 'repo'
            assert params[1][0] == 'issue_number'
    
    def test_condition_commands_specific_pattern(self):
        """Test condition commands follow their specific pattern."""
        condition_commands = {
            create_condition: ['repo', 'issue_number', 'condition_text'],
            update_condition: ['repo', 'issue_number', 'condition_match'],
            complete_condition: ['repo', 'issue_number', 'condition_match'],
            verify_condition: ['repo', 'issue_number', 'condition_match']
        }
        
        for cmd, expected_params in condition_commands.items():
            sig = inspect.signature(cmd)
            params = list(sig.parameters.items())
            
            # Check first few parameters match expected pattern
            for i, expected_param in enumerate(expected_params):
                assert i < len(params), f"Command {cmd.__name__} missing parameter {expected_param}"
                assert params[i][0] == expected_param, f"Command {cmd.__name__} parameter {i} is '{params[i][0]}', expected '{expected_param}'"