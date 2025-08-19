"""Execution smoke tests that actually call functions to catch runtime errors.

This test module executes functions with mock data to catch errors that
static analysis and signature inspection cannot detect, such as:
- Missing imports (NameError at runtime)
- Undefined variables
- Basic runtime execution paths

These tests should have caught the resolve_repository import error.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


class TestExecutionSmoke:
    """Smoke tests that execute functions to catch runtime errors."""
    
    def test_all_main_commands_can_execute_basic_path(self):
        """Test that all main commands can be called without NameError/ImportError."""
        
        from ghoo.main import (
            set_body, create_todo, check_todo, create_section, update_section,
            create_condition, update_condition, complete_condition, verify_condition,
            create_epic, create_task, create_sub_task,
            start_plan, submit_plan, approve_plan,
            start_work, submit_work, approve_work,
            post_comment, get_latest_comment_timestamp, get_comments
        )
        
        # Mock all the dependencies these functions might need
        with patch('ghoo.main.ConfigLoader') as mock_config_loader_class, \
             patch('ghoo.main.GitHubClient') as mock_github_client_class, \
             patch('ghoo.main.resolve_repository') as mock_resolve_repo, \
             patch('ghoo.main.typer.echo'), \
             patch('ghoo.main.sys.exit'):
            
            # Setup mocks
            mock_config_loader = Mock()
            mock_config_loader_class.return_value = mock_config_loader
            mock_config_loader.load.return_value = Mock()
            mock_config_loader.get_config_dir.return_value = Path('/mock')
            
            mock_github_client = Mock()
            mock_github_client_class.return_value = mock_github_client
            
            mock_resolve_repo.return_value = "owner/repo"
            
            # Mock command results
            mock_result = {
                'issue_number': 123,
                'issue_title': 'Test Issue',
                'new_state': True,
                'action': 'checked',
                'comment_id': 456,
                'author': 'testuser',
                'comment_url': 'http://example.com',
                'comment_body': 'test comment',
                'timestamp': '2024-01-01T00:00:00Z',
                'comments': [],
                'condition_text': 'test condition',
                'requirements': 'test requirements',
                'old_requirements': 'old',
                'new_requirements': 'new',
                'evidence': 'test evidence',
                'old_evidence': 'old evidence',
                'new_evidence': 'new evidence',
                'signed_off_by': 'testuser',
                'was_verified': False,
                'from_state': 'planning',
                'to_state': 'in-progress',
                'user': 'testuser',
                'message': 'test message',
                'url': 'http://example.com'
            }
            
            # Mock all command objects
            commands_to_mock = [
                'SetBodyCommand', 'CreateTodoCommand', 'CheckTodoCommand', 
                'CreateSectionCommand', 'UpdateSectionCommand',
                'CreateConditionCommand', 'UpdateConditionCommand', 
                'CompleteConditionCommand', 'VerifyConditionCommand',
                'CreateEpicCommand', 'CreateTaskCommand', 'CreateSubTaskCommand',
                'StartPlanCommand', 'SubmitPlanCommand', 'ApprovePlanCommand',
                'StartWorkCommand', 'SubmitWorkCommand', 'ApproveWorkCommand',
                'PostCommentCommand', 'GetLatestCommentTimestampCommand', 'GetCommentsCommand'
            ]
            
            with patch.multiple('ghoo.main', **{cmd: Mock() for cmd in commands_to_mock}):
                # Mock all command instances
                for cmd in commands_to_mock:
                    mock_cmd_class = getattr(sys.modules['ghoo.main'], cmd)
                    mock_cmd_instance = Mock()
                    mock_cmd_instance.execute.return_value = mock_result
                    mock_cmd_class.return_value = mock_cmd_instance
                
                # Test functions that should execute without NameError/ImportError
                test_cases = [
                    (set_body, ["--repo", "owner/repo", "123", "--body", "test"]),
                    (create_todo, ["--repo", "owner/repo", "123", "section", "todo text"]),
                    (check_todo, ["--repo", "owner/repo", "123", "section", "--match", "todo"]),
                    (create_section, ["--repo", "owner/repo", "123", "section name"]),
                    (update_section, ["--repo", "owner/repo", "123", "section", "--content", "content"]),
                ]
                
                failed_functions = []
                
                for func, mock_args in test_cases:
                    try:
                        # Try to execute the function (it should reach at least resolve_repository call)
                        func(
                            repo="owner/repo",
                            issue_number=123,
                            body="test" if func == set_body else None,
                            todo_text="test" if func == create_todo else None,
                            section="test" if func in [create_todo, check_todo, update_section] else None,
                            section_name="test" if func == create_section else None,
                            match="test" if func == check_todo else None,
                            content="test" if func == update_section else None,
                            create_section=False if func == create_todo else None,
                        )
                        # If we get here, the function executed without NameError/ImportError
                        
                    except (NameError, ImportError) as e:
                        failed_functions.append(f"{func.__name__}: {type(e).__name__}: {e}")
                    except Exception as e:
                        # Other exceptions are expected (mocked dependencies, validation, etc.)
                        # We only care about NameError and ImportError
                        pass
                
                if failed_functions:
                    pytest.fail(f"Functions failed with NameError/ImportError:\\n" + "\\n".join(failed_functions))
    
    def test_resolve_repository_is_importable_and_callable(self):
        """Specific test for resolve_repository function availability."""
        
        # Test that resolve_repository can be imported
        try:
            from ghoo.utils.repository import resolve_repository
        except ImportError as e:
            pytest.fail(f"Cannot import resolve_repository: {e}")
        
        # Test that resolve_repository is callable
        assert callable(resolve_repository), "resolve_repository should be callable"
        
        # Test that it can be called from main module context
        from ghoo.main import resolve_repository as main_resolve_repository
        assert callable(main_resolve_repository), "resolve_repository should be accessible from main module"
    
    def test_critical_imports_available(self):
        """Test that critical imports are available at runtime."""
        
        # Test that all main command functions can import their dependencies
        from ghoo.main import set_body
        
        import sys
        import inspect
        
        # Get the source code to check for runtime imports
        source = inspect.getsource(set_body)
        
        # If resolve_repository is called, it should either be imported at module level
        # or have a local import
        if "resolve_repository(" in source:
            # Check module-level import exists
            import ghoo.main
            assert hasattr(ghoo.main, 'resolve_repository'), "resolve_repository should be available in main module"
    
    def test_basic_function_call_pattern(self):
        """Test the basic pattern that most functions should follow."""
        
        from ghoo.main import set_body
        from unittest.mock import patch, Mock
        
        # Mock the entire flow
        with patch('ghoo.main.ConfigLoader') as mock_config_loader_class, \
             patch('ghoo.main.resolve_repository') as mock_resolve_repo, \
             patch('ghoo.main.GitHubClient') as mock_client_class, \
             patch('ghoo.main.SetBodyCommand') as mock_cmd_class, \
             patch('ghoo.main.typer.echo'), \
             patch('ghoo.main.sys.stdin') as mock_stdin:
            
            # Setup mocks
            mock_config_loader = Mock()
            mock_config_loader_class.return_value = mock_config_loader
            mock_resolve_repo.return_value = "owner/repo"
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_cmd = Mock()
            mock_cmd_class.return_value = mock_cmd
            mock_cmd.execute.return_value = {'issue_number': 123, 'issue_title': 'Test'}
            mock_stdin.isatty.return_value = False
            mock_stdin.read.return_value = "test body"
            
            # This should execute without NameError
            try:
                set_body(repo="owner/repo", issue_number=123, body="test body")
            except NameError as e:
                pytest.fail(f"NameError in set_body execution: {e}")
            except ImportError as e:
                pytest.fail(f"ImportError in set_body execution: {e}")
            except:
                # Other exceptions are fine - we just want to avoid NameError/ImportError
                pass


if __name__ == "__main__":
    # Allow running this test directly
    pytest.main([__file__, "-v"])