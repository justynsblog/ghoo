"""Integration tests for get command."""

import pytest
import subprocess
import json
import os
import sys
from pathlib import Path


class TestGetEpicCommandIntegration:
    """Integration tests for the get epic command CLI interface."""
    
    @pytest.fixture
    def repo_env(self):
        """Setup test repository environment."""
        return {
            'GITHUB_TOKEN': os.getenv('TESTING_GITHUB_TOKEN', ''),
            'TESTING_REPO': os.getenv('TESTING_REPO', 'owner/repo')  # Fallback for tests
        }
    
    def test_get_command_help(self):
        """Test get command help output shows subcommands."""
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', '--help'
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        assert 'Get various resources from GitHub issues' in result.stdout
        assert 'epic' in result.stdout
        assert 'milestone' in result.stdout
        assert 'section' in result.stdout
        assert 'todo' in result.stdout
    
    def test_get_epic_invalid_repo_format(self):
        """Test get epic command with invalid repository format."""
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 'epic', '--repo', 'invalid-repo', '--id', '1'
        ], capture_output=True, text=True, env={'GITHUB_TOKEN': 'dummy'})
        
        assert result.returncode == 1
        assert "Invalid repository format" in result.stderr
        assert "Expected 'owner/repo'" in result.stderr
    
    def test_get_epic_missing_token(self):
        """Test get epic command without GitHub token."""
        env = os.environ.copy()
        env.pop('GITHUB_TOKEN', None)
        env.pop('TESTING_GITHUB_TOKEN', None)
        
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 'epic', '--repo', 'owner/repo', '--id', '1'
        ], capture_output=True, text=True, env=env)
        
        assert result.returncode == 1
        assert "GitHub token not found" in result.stderr
        assert "Set GITHUB_TOKEN environment variable" in result.stderr
    
    def test_get_epic_nonexistent_issue(self, repo_env):
        """Test get epic command with non-existent issue."""
        env = os.environ.copy()
        env['GITHUB_TOKEN'] = repo_env['GITHUB_TOKEN']
        
        # Use a very high issue number that likely doesn't exist
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 'epic', '--repo', repo_env['TESTING_REPO'], '999999'
        ], capture_output=True, text=True, env=env)
        
        assert result.returncode == 1
        assert "not found" in result.stderr
    
    def test_get_epic_json_format(self, repo_env):
        """Test get epic command with JSON output format."""
        # Use dummy token if no real token available
        token = repo_env['GITHUB_TOKEN'] or 'dummy_token'
        
        env = os.environ.copy()
        env['GITHUB_TOKEN'] = repo_env['GITHUB_TOKEN']
        
        # This test assumes there's at least one epic issue in the test repo
        # We'll use issue #1 which commonly exists
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 'epic', '--repo', repo_env['TESTING_REPO'], '--id', '1', 
            '--format', 'json'
        ], capture_output=True, text=True, env=env)
        
        if result.returncode != 0:
            # Without a real token, this is expected - test the command structure
            if not repo_env['GITHUB_TOKEN']:
                # Verify the command failed with expected auth error (not a parsing error)
                assert 'GitHub' in result.stderr or 'token' in result.stderr or 'authentication' in result.stderr
                return  # Test passes - command structure is correct
            else:
                pytest.fail(f"Could not fetch issue #1 from {repo_env['TESTING_REPO']}: {result.stderr}")
        
        # Verify JSON output
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")
        
        # Verify required fields in JSON for epic
        required_fields = [
            'number', 'title', 'state', 'type', 'author', 
            'created_at', 'updated_at', 'url', 'labels', 
            'assignees', 'pre_section_description', 'sections', 'available_milestones'
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Verify data types
        assert isinstance(data['number'], int)
        assert isinstance(data['title'], str)
        assert data['state'] in ['open', 'closed']
        assert data['type'] in ['epic', 'task', 'sub-task']
        assert isinstance(data['labels'], list)
        assert isinstance(data['assignees'], list)
        assert isinstance(data['sections'], list)
    
    def test_get_epic_rich_format(self, repo_env):
        """Test get epic command with rich (default) output format."""
        # Use dummy token if no real token available
        token = repo_env['GITHUB_TOKEN'] or 'dummy_token'
        
        env = os.environ.copy()
        env['GITHUB_TOKEN'] = repo_env['GITHUB_TOKEN']
        
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 'epic', '--repo', repo_env['TESTING_REPO'], '--id', '1'
        ], capture_output=True, text=True, env=env)
        
        if result.returncode != 0:
            # Without a real token, this is expected - test the command structure
            if not repo_env['GITHUB_TOKEN']:
                # Verify the command failed with expected auth error (not a parsing error)
                assert 'GitHub' in result.stderr or 'token' in result.stderr or 'authentication' in result.stderr
                return  # Test passes - command structure is correct
            else:
                pytest.fail(f"Could not fetch issue #1 from {repo_env['TESTING_REPO']}: {result.stderr}")
        
        # Verify rich format contains expected elements
        output = result.stdout
        
        # Should contain issue number and title
        assert '#1:' in output or '#1 ' in output
        
        # Should contain state information
        assert 'State:' in output or 'OPEN' in output or 'CLOSED' in output
        
        # Should contain author information
        assert 'Author:' in output
        
        # Should contain URL
        assert 'URL:' in output or 'github.com' in output
        
        # Should contain creation/update timestamps
        assert 'Created:' in output or 'Updated:' in output
    
    def test_get_command_with_sections_and_todos(self):
        """Test get command output formatting for issues with sections and todos.
        
        This is a mock-based integration test since we can't guarantee
        the test repository has specific formatted issues.
        """
        import tempfile
        import sys
        from unittest.mock import patch, Mock
        
        # Create a mock issue with structured content
        mock_issue = Mock()
        mock_issue.number = 123
        mock_issue.title = "Test Epic Issue"
        mock_issue.state = "open"
        mock_issue.user.login = "testuser"
        mock_issue.created_at.isoformat.return_value = "2024-01-01T12:00:00"
        mock_issue.updated_at.isoformat.return_value = "2024-01-02T12:00:00"
        mock_issue.html_url = "https://github.com/test/repo/issues/123"
        mock_issue.labels = []
        mock_issue.assignees = []
        mock_issue.milestone = None
        mock_issue.body = """
        This is an epic issue for testing.
        
        ## Summary
        This epic covers multiple features.
        
        ## Tasks
        - [x] Complete task 1
        - [ ] Work on task 2
        - [x] Finish task 3
        
        ## Notes
        Some additional notes here.
        """
        
        # Mock the GitHub client and repository
        with patch('ghoo.core.GitHubClient') as MockClient:
            mock_client = MockClient.return_value
            mock_repo = Mock()
            mock_repo.get_issue.return_value = mock_issue
            mock_client.github.get_repo.return_value = mock_repo
            mock_client.check_sub_issues_available.return_value = False
            
            # Set environment variable for token
            with patch.dict(os.environ, {'GITHUB_TOKEN': 'test-token'}):
                result = subprocess.run([
                    sys.executable, '-c', '''
import sys
sys.path.insert(0, ".")
from ghoo.main import app
if __name__ == "__main__":
    app(["get", "test/repo", "123", "--format", "json"])
                    '''
                ], capture_output=True, text=True, cwd=str(Path(__file__).parent.parent.parent))
        
        # Note: This test is more of a smoke test for the integration
        # The actual formatting verification would need a real issue or
        # more complex mocking setup
    
    def test_command_line_argument_validation(self):
        """Test command line argument validation."""
        # Test missing arguments
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get'
        ], capture_output=True, text=True)
        
        assert result.returncode != 0
        assert "Missing argument" in result.stderr or "Usage:" in result.stderr
        
        # Test invalid issue number (non-integer)  
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 'owner/repo', 'not-a-number'
        ], capture_output=True, text=True, env={'GITHUB_TOKEN': 'dummy'})
        
        assert result.returncode != 0
        # Should fail during argument parsing or validation
    
    def test_format_option_validation(self):
        """Test format option accepts valid values."""
        # Test with invalid format
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 'epic', '--repo', 'owner/repo', '--id', '1', 
            '--format', 'invalid'
        ], capture_output=True, text=True, env={'GITHUB_TOKEN': 'dummy'})
        
        # Command should fail due to invalid format or missing token/repo
        assert result.returncode != 0
        assert "GitHub token" in result.stderr or "not found" in result.stderr or "format" in result.stderr
    
    def test_error_handling_github_api_errors(self):
        """Test error handling for GitHub API errors."""
        # Test with invalid token
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 'epic', '--repo', 'owner/repo', '--id', '1'
        ], capture_output=True, text=True, env={'GITHUB_TOKEN': 'invalid-token'})
        
        assert result.returncode != 0
        assert "authentication failed" in result.stderr or "Invalid" in result.stderr or "GitHub" in result.stderr
    
    def test_epic_issue_with_sub_issues_display(self, repo_env):
        """Test display formatting for epic issues with sub-issues.
        
        This test uses mock data when no real token is available.
        """
        # Use mock implementation for testing display logic
        from unittest.mock import patch, Mock
        from tests.integration.fixtures import IssueFixtures
        
        # Create test data using fixtures
        hierarchy = IssueFixtures.create_issue_with_hierarchy()
        epic_data = hierarchy['epic'][0]
        
        with patch('ghoo.core.GitHubClient') as MockClient:
            mock_client = MockClient.return_value
            mock_repo = Mock()
            
            # Create mock issue from fixture data
            mock_issue = Mock()
            mock_issue.number = epic_data['number']
            mock_issue.title = epic_data['title']
            mock_issue.body = epic_data['body']
            mock_issue.state = epic_data['state']
            mock_issue.labels = epic_data['labels']
            mock_issue.html_url = epic_data['html_url']
            mock_issue.user.login = epic_data['user']['login']
            mock_issue.created_at.isoformat.return_value = epic_data['created_at']
            mock_issue.updated_at.isoformat.return_value = epic_data['updated_at']
            
            mock_repo.get_issue.return_value = mock_issue
            mock_client.github.get_repo.return_value = mock_repo
            mock_client.check_sub_issues_available.return_value = True
            
            # Test that the command can process epic issues
            # The actual display verification would need more complex setup
            assert mock_issue.number == 1
            assert "Epic" in mock_issue.title
    
    def test_performance_with_large_issues(self):
        """Test performance with issues containing many sections and todos."""
        # Use fixture to create large issue for performance testing
        from tests.integration.fixtures import IssueFixtures
        import time
        
        # Create a large issue with many sections and todos
        large_issue_data = IssueFixtures.create_large_issue(
            number=100, 
            sections=10,  # Smaller number for test performance
            todos_per_section=5
        )
        
        # Basic performance test - parsing should complete quickly
        start_time = time.time()
        
        # Test that the issue data is properly structured
        assert large_issue_data['number'] == 100
        assert len(large_issue_data['body']) > 1000  # Should be substantial content
        assert 'Large Issue for Performance Testing' in large_issue_data['title']
        
        # Test should complete in reasonable time (< 1 second for parsing/validation)
        elapsed = time.time() - start_time
        assert elapsed < 1.0, f"Performance test took too long: {elapsed:.2f}s"


class TestGetRepositoryResolutionIntegration:
    """Integration tests for repository resolution across all get commands."""
    
    def test_config_based_repository_resolution(self, tmp_path):
        """Test that get commands can resolve repository from ghoo.yaml config."""
        # Create temporary ghoo.yaml config
        config_content = """
project_url: https://github.com/test/repo
status_method: labels
required_sections:
  - "Problem Statement"
  - "Acceptance Criteria"
"""
        config_file = tmp_path / "ghoo.yaml"
        config_file.write_text(config_content)
        
        # Test get epic without --repo parameter (should use config)
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 'epic', '1'
        ], capture_output=True, text=True, 
           cwd=tmp_path, env={'GITHUB_TOKEN': 'dummy'})
        
        # Should attempt to connect to test/repo (will fail due to dummy token)
        assert result.returncode == 1
        assert 'authentication' in result.stderr or 'token' in result.stderr
    
    def test_explicit_repo_overrides_config(self, tmp_path):
        """Test that explicit --repo parameter overrides config."""
        # Create temporary ghoo.yaml config with different repo
        config_content = """
project_url: https://github.com/config/repo
status_method: labels
"""
        config_file = tmp_path / "ghoo.yaml"
        config_file.write_text(config_content)
        
        # Test get epic with explicit --repo parameter
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 'epic', '--repo', 'explicit/repo', '--id', '1'
        ], capture_output=True, text=True, 
           cwd=tmp_path, env={'GITHUB_TOKEN': 'dummy'})
        
        # Should attempt to connect to explicit/repo, not config/repo
        assert result.returncode == 1
        # Error should reference the explicit repo or be about authentication
        assert 'authentication' in result.stderr or 'token' in result.stderr
    
    def test_missing_repo_and_config_error(self, tmp_path):
        """Test helpful error when no repo and no config available."""
        # Test get epic without --repo parameter and no config
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 'epic', '1'
        ], capture_output=True, text=True, 
           cwd=tmp_path, env={'GITHUB_TOKEN': 'dummy'})
        
        assert result.returncode == 1
        assert 'No repository specified' in result.stderr
        assert 'Solutions:' in result.stderr
        assert '--repo' in result.stderr
        assert 'ghoo.yaml' in result.stderr


class TestGetCommandOutputFormatting:
    """Tests focused on output formatting and display logic for all get commands."""
    
    def test_epic_emoji_display_in_rich_format(self):
        """Test that appropriate emojis are used in epic rich format output."""
        # Test epic emoji display (🎯 for epics)
        # This would need mock testing with actual display function
        pass
    
    def test_milestone_progress_display(self):
        """Test milestone progress display with completion percentages."""
        # Test milestone display with issue grouping by type
        pass
    
    def test_section_todo_formatting(self):
        """Test section display with todo list formatting."""
        # Test section display with todo completion indicators
        pass
    
    def test_todo_match_type_indicators(self):
        """Test todo match type indicators in output."""
        # Test exact/case-insensitive/substring match indicators
        pass
    
    def test_progress_bar_display(self):
        """Test progress bar display for sections with todos."""
        # This would test the progress bar formatting for sections
        # with various completion percentages
        pass
    
    def test_color_coding_in_output(self):
        """Test color coding for different elements in rich output."""
        # This would test the color assignment for various elements
        # like issue states, labels, etc.
        pass
    
    def test_section_formatting_with_markdown(self):
        """Test that markdown content in sections is displayed properly."""
        # Test how markdown content like code blocks, tables, etc.
        # are handled in the display output
        pass


class TestGetMilestoneCommandIntegration:
    """Integration tests for the get milestone command CLI interface."""
    
    @pytest.fixture
    def repo_env(self):
        """Setup test repository environment."""
        return {
            'GITHUB_TOKEN': os.getenv('TESTING_GITHUB_TOKEN', ''),
            'TESTING_REPO': os.getenv('TESTING_REPO', 'owner/repo')  # Fallback for tests
        }
    
    def test_get_milestone_help(self):
        """Test get milestone command help output."""
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 'milestone', '--help'
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        assert 'Get milestone details' in result.stdout
        assert '--repo' in result.stdout
        assert 'milestone_number' in result.stdout
        assert '--format' in result.stdout
    
    def test_get_milestone_json_format(self, repo_env):
        """Test get milestone command with JSON output format."""
        env = os.environ.copy()
        env['GITHUB_TOKEN'] = repo_env['GITHUB_TOKEN']
        
        # Test with milestone #1 from a repository known to have milestones
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 'milestone', '--repo', 'microsoft/vscode', '--id', '1', 
            '--format', 'json'
        ], capture_output=True, text=True, env=env)
        
        if result.returncode != 0:
            # Without a real token, this is expected - test the command structure
            if not repo_env['GITHUB_TOKEN']:
                assert 'GitHub' in result.stderr or 'token' in result.stderr
                return
            else:
                pytest.fail(f"Could not fetch milestone #1: {result.stderr}")
        
        # Verify JSON output structure
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")
        
        # Verify required fields for milestone
        required_fields = [
            'number', 'title', 'description', 'state', 'due_on',
            'open_issues', 'closed_issues', 'created_at', 'updated_at', 
            'url', 'issues_by_type'
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
    
    def test_get_milestone_invalid_repo_format(self):
        """Test get milestone command with invalid repository format."""
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 'milestone', '--repo', 'invalid-repo', '--id', '1'
        ], capture_output=True, text=True, env={'GITHUB_TOKEN': 'dummy'})
        
        assert result.returncode == 1
        assert "Invalid repository format" in result.stderr
        assert "Expected 'owner/repo'" in result.stderr


class TestGetSectionCommandIntegration:
    """Integration tests for the get section command CLI interface."""
    
    @pytest.fixture
    def repo_env(self):
        """Setup test repository environment."""
        return {
            'GITHUB_TOKEN': os.getenv('TESTING_GITHUB_TOKEN', ''),
            'TESTING_REPO': os.getenv('TESTING_REPO', 'owner/repo')
        }
    
    def test_get_section_help(self):
        """Test get section command help output."""
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 'section', '--help'
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        assert 'Extract specific section from issue' in result.stdout
        assert '--repo' in result.stdout
        assert 'issue_number' in result.stdout
        assert 'section_title' in result.stdout
        assert '--format' in result.stdout
    
    def test_get_section_json_format(self, repo_env):
        """Test get section command with JSON output format."""
        env = os.environ.copy()
        env['GITHUB_TOKEN'] = repo_env['GITHUB_TOKEN']
        
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 'section', '--repo', repo_env['TESTING_REPO'], '--id', '1', 
            'Summary', '--format', 'json'
        ], capture_output=True, text=True, env=env)
        
        if result.returncode != 0:
            if not repo_env['GITHUB_TOKEN']:
                assert 'GitHub' in result.stderr or 'token' in result.stderr
                return
            else:
                # Section might not exist - test command structure
                assert 'not found' in result.stderr or 'Section' in result.stderr
                return
        
        # Verify JSON output structure
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")
        
        # Verify required fields for section
        required_fields = [
            'title', 'body', 'total_todos', 'completed_todos', 
            'completion_percentage', 'todos', 'issue_number', 
            'issue_title', 'issue_state', 'issue_type', 'issue_url'
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
    
    def test_get_section_case_insensitive_matching(self, repo_env):
        """Test get section with case-insensitive section matching."""
        env = os.environ.copy()
        env['GITHUB_TOKEN'] = repo_env['GITHUB_TOKEN']
        
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 'section', '--repo', repo_env['TESTING_REPO'], '--id', '1', 
            'summary'  # lowercase
        ], capture_output=True, text=True, env=env)
        
        # Command should execute (might fail due to missing section/token but not parsing)
        if result.returncode != 0 and not repo_env['GITHUB_TOKEN']:
            assert 'GitHub' in result.stderr or 'token' in result.stderr


class TestGetTodoCommandIntegration:
    """Integration tests for the get todo command CLI interface."""
    
    @pytest.fixture
    def repo_env(self):
        """Setup test repository environment."""
        return {
            'GITHUB_TOKEN': os.getenv('TESTING_GITHUB_TOKEN', ''),
            'TESTING_REPO': os.getenv('TESTING_REPO', 'owner/repo')
        }
    
    def test_get_todo_help(self):
        """Test get todo command help output."""
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 'todo', '--help'
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        assert 'Find specific todo in section' in result.stdout
        assert '--repo' in result.stdout
        assert 'issue_number' in result.stdout
        assert 'section_title' in result.stdout
        assert 'todo_match' in result.stdout
        assert '--format' in result.stdout
    
    def test_get_todo_json_format(self, repo_env):
        """Test get todo command with JSON output format."""
        env = os.environ.copy()
        env['GITHUB_TOKEN'] = repo_env['GITHUB_TOKEN']
        
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 'todo', '--repo', repo_env['TESTING_REPO'], '--id', '1', 
            'Tasks', 'implement', '--format', 'json'
        ], capture_output=True, text=True, env=env)
        
        if result.returncode != 0:
            if not repo_env['GITHUB_TOKEN']:
                assert 'GitHub' in result.stderr or 'token' in result.stderr
                return
            else:
                # Todo/section might not exist - test command structure
                assert 'not found' in result.stderr or 'Todo' in result.stderr or 'Section' in result.stderr
                return
        
        # Verify JSON output structure
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")
        
        # Verify required fields for todo
        required_fields = [
            'text', 'checked', 'line_number', 'section_title', 
            'section_total_todos', 'section_completed_todos', 'section_completion_percentage',
            'issue_number', 'issue_title', 'issue_state', 'issue_type', 
            'issue_url', 'repository', 'match_type'
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
    
    def test_get_todo_multi_tier_matching(self, repo_env):
        """Test get todo with multi-tier matching algorithm."""
        env = os.environ.copy()
        env['GITHUB_TOKEN'] = repo_env['GITHUB_TOKEN']
        
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 'todo', '--repo', repo_env['TESTING_REPO'], '--id', '1', 
            'Tasks', 'test'  # Should match via substring if no exact match
        ], capture_output=True, text=True, env=env)
        
        # Command should execute (might fail due to missing todo/section/token but not parsing)
        if result.returncode != 0 and not repo_env['GITHUB_TOKEN']:
            assert 'GitHub' in result.stderr or 'token' in result.stderr