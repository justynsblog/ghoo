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
        
        # Skip if no testing token available
        if not os.getenv("TESTING_GITHUB_TOKEN"):
            pytest.skip("TESTING_GITHUB_TOKEN not set - cannot run E2E tests")
        
        testing_repo = os.getenv("TESTING_GH_REPO")
        if not testing_repo:
            pytest.skip("TESTING_GH_REPO not set - cannot run E2E tests")
        
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
            
            # Check for required status labels
            expected_status_labels = [
                'status:backlog',
                'status:planning', 
                'status:in-progress',
                'status:review',
                'status:done',
                'status:blocked'
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
            
            # Verify label colors are correct (spot check a few)
            assert labels['status:backlog'].color == 'ededed'
            assert labels['status:done'].color == '0e8a16'
            assert labels['type:epic'].color == '7057ff'
            
        except Exception as e:
            pytest.fail(f"Failed to verify labels in repository {repo_name}: {str(e)}")
    
    def test_init_gh_command_idempotent(self, cli_runner, temp_project_dir):
        """Test that running init-gh multiple times is safe (idempotent)."""
        import os
        import yaml
        from pathlib import Path
        
        # Skip if no testing credentials
        if not os.getenv("TESTING_GITHUB_TOKEN") or not os.getenv("TESTING_GH_REPO"):
            pytest.skip("Testing credentials not available")
        
        testing_repo = os.getenv("TESTING_GH_REPO")
        
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
            
            # Should not show any failures
            assert 'Failed:' not in output2
            
        finally:
            os.chdir(original_cwd)
    
    def test_init_gh_command_with_custom_config_path(self, cli_runner, temp_project_dir):
        """Test init-gh command with custom config file path."""
        import os
        import yaml
        
        # Skip if no testing credentials
        if not os.getenv("TESTING_GITHUB_TOKEN") or not os.getenv("TESTING_GH_REPO"):
            pytest.skip("Testing credentials not available")
        
        testing_repo = os.getenv("TESTING_GH_REPO")
        
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
        pytest.skip("Epic creation commands not yet implemented")
    
    def test_task_hierarchy(self, cli_runner, test_repo):
        """Test epic -> task -> sub-task hierarchy (placeholder)."""
        pytest.skip("Issue hierarchy commands not yet implemented")
    
    def test_workflow_validation(self, cli_runner, test_repo):
        """Test workflow state validation (placeholder)."""
        pytest.skip("Workflow validation not yet implemented")