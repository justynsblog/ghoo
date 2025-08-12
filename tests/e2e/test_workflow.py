"""End-to-end workflow tests for ghoo CLI (placeholder for future tests)."""

import pytest
from tests.helpers.cli import assert_command_success, assert_command_error
from tests.helpers.github import create_test_issue, verify_issue_exists


@pytest.mark.e2e
class TestE2EWorkflow:
    """End-to-end tests for complete ghoo workflows."""
    
    def test_init_gh_command(self, cli_runner, temp_project_dir):
        """Test init-gh command against real GitHub repository."""
        import os
        import yaml
        from pathlib import Path
        
        # Use dual-mode approach: real GitHub API or mocks
        testing_token = os.getenv("TESTING_GITHUB_TOKEN")
        testing_repo = os.getenv("TESTING_GH_REPO")
        
        if not testing_token or not testing_repo:
            # Fall back to mock mode
            from tests.e2e.e2e_test_utils import MockE2EEnvironment
            mock_env = MockE2EEnvironment()
            testing_repo = "mock/repo"
        
        # Create ghoo.yaml config file in temp directory
        config_content = {
            'project_url': f'https://github.com/{testing_repo}',
            'status_method': 'labels',
            'required_sections': {
                'epic': ['Summary', 'Acceptance Criteria'],
                'task': ['Summary']
            }
        }
        
        config_path = temp_project_dir / "ghoo.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config_content, f)
        
        # Change to temp directory so ghoo finds the config
        original_cwd = Path.cwd()
        os.chdir(temp_project_dir)
        
        try:
            # Run init-gh command
            result = cli_runner.invoke(['init-gh'])
            
            # Verify command succeeded
            assert_command_success(result)
            
            # Verify output contains expected content
            output = result.output
            assert 'Initializing repository' in output
            assert testing_repo in output
            
            # Should have either created items or shown they already exist
            # (depends on repository state)
            has_created = 'Created:' in output
            has_existed = 'Already existed:' in output
            assert has_created or has_existed, f"Expected creation or existence output, got: {output}"
            
            # Should show success or already initialized message
            success_indicators = [
                'Successfully initialized',
                'already initialized',
                'completed with'
            ]
            assert any(indicator in output for indicator in success_indicators), \
                f"Expected success indicator in output: {output}"
            
            # Verify labels were created in the repository using GitHub API
            self._verify_labels_exist(testing_repo)
            
        finally:
            # Restore original working directory
            os.chdir(original_cwd)
    
    def _verify_labels_exist(self, repo_name: str):
        """Verify that required labels exist in the GitHub repository.
        
        Args:
            repo_name: Repository name in format 'owner/repo'
        """
        import os
        from github import Github
        from github.Auth import Token
        
        # Get testing token and create GitHub client
        token = os.getenv("TESTING_GITHUB_TOKEN")
        auth = Token(token)
        github = Github(auth=auth)
        
        try:
            # Get the repository
            repo = github.get_repo(repo_name)
            
            # Get all labels
            labels = {label.name: label for label in repo.get_labels()}
            
            # Check for required status labels (based on actual STATUS_LABELS in core.py)
            expected_status_labels = [
                'status:backlog',
                'status:planning', 
                'status:awaiting-plan-approval',
                'status:plan-approved',
                'status:in-progress',
                'status:awaiting-completion-approval',
                'status:closed'
            ]
            
            for label_name in expected_status_labels:
                assert label_name in labels, f"Status label '{label_name}' not found in repository"
            
            # Check for required type labels (fallback labels)
            expected_type_labels = [
                'type:epic',
                'type:task',
                'type:sub-task'
            ]
            
            for label_name in expected_type_labels:
                assert label_name in labels, f"Type label '{label_name}' not found in repository"
            
            # Verify label colors exist (colors may vary if labels were manually created)
            # Just check that the labels have colors set
            assert labels['status:backlog'].color is not None
            assert labels['status:closed'].color is not None  
            assert labels['type:epic'].color is not None
            
        except Exception as e:
            pytest.fail(f"Failed to verify labels in repository {repo_name}: {str(e)}")
    
    def test_init_gh_command_idempotent(self, cli_runner, temp_project_dir):
        """Test that running init-gh multiple times is safe (idempotent)."""
        import os
        import yaml
        from pathlib import Path
        
        # Use dual-mode approach
        testing_token = os.getenv("TESTING_GITHUB_TOKEN")
        testing_repo = os.getenv("TESTING_GH_REPO")
        
        if not testing_token or not testing_repo:
            from tests.e2e.e2e_test_utils import MockE2EEnvironment
            mock_env = MockE2EEnvironment()
            testing_repo = "mock/repo"
        else:
            testing_repo = testing_repo
        
        # Create config file
        config_content = {
            'project_url': f'https://github.com/{testing_repo}',
            'status_method': 'labels'
        }
        
        config_path = temp_project_dir / "ghoo.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config_content, f)
        
        # Change to temp directory
        original_cwd = Path.cwd()
        os.chdir(temp_project_dir)
        
        try:
            # Run init-gh command first time
            result1 = cli_runner.invoke(['init-gh'])
            assert_command_success(result1)
            
            # Run init-gh command second time
            result2 = cli_runner.invoke(['init-gh'])
            assert_command_success(result2)
            
            # Second run should show items already exist
            output2 = result2.output
            assert ('Already existed:' in output2 or 'already initialized' in output2), \
                f"Expected items to already exist on second run: {output2}"
            
            # Should not show any real failures (GraphQL fallback is expected behavior)
            # Check for real errors but not GraphQL feature unavailability
            if 'Failed:' in output2:
                lines = output2.split('\n')
                in_failed_section = False
                real_failures = []
                
                for line in lines:
                    if '❌ Failed:' in line:
                        in_failed_section = True
                        continue
                    elif line.startswith('⚠️') or line.startswith('✅'):
                        in_failed_section = False
                        continue
                    
                    if in_failed_section and line.strip().startswith('•'):
                        # This is a failure item, check if it's a real failure
                        if 'GraphQL feature' not in line or 'not available' not in line:
                            real_failures.append(line.strip())
                
                # If there are real failures besides GraphQL unavailability, that's an error
                assert len(real_failures) == 0, f"Unexpected real failures on second run: {real_failures}"
            
        finally:
            os.chdir(original_cwd)
    
    def test_init_gh_command_with_custom_config_path(self, cli_runner, temp_project_dir):
        """Test init-gh command with custom config file path."""
        import os
        import yaml
        
        # Use dual-mode approach
        testing_token = os.getenv("TESTING_GITHUB_TOKEN")
        testing_repo = os.getenv("TESTING_GH_REPO")
        
        if not testing_token or not testing_repo:
            from tests.e2e.e2e_test_utils import MockE2EEnvironment
            mock_env = MockE2EEnvironment()
            testing_repo = "mock/repo"
        else:
            testing_repo = testing_repo
        
        # Create config file in subdirectory with custom name
        config_dir = temp_project_dir / "config"
        config_dir.mkdir()
        config_path = config_dir / "my-ghoo-config.yaml"
        
        config_content = {
            'project_url': f'https://github.com/{testing_repo}',
            'status_method': 'labels'
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(config_content, f)
        
        # Run init-gh command with custom config path
        result = cli_runner.invoke(['init-gh', '--config', str(config_path)])
        
        # Verify command succeeded
        assert_command_success(result)
        
        # Verify it used the custom config
        output = result.output
        assert 'Initializing repository' in output
        assert testing_repo in output
    
    def test_epic_lifecycle(self, cli_runner, test_repo):
        """Test creating and managing an epic (placeholder)."""
        # TODO: Implement epic creation commands
        pass
    
    def test_task_hierarchy(self, cli_runner, test_repo):
        """Test epic -> task -> sub-task hierarchy (placeholder)."""
        # TODO: Implement issue hierarchy commands
        pass
    
    def test_workflow_validation(self, cli_runner, test_repo):
        """Test workflow state validation (placeholder)."""
        # TODO: Implement workflow validation
        pass