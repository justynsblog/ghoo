"""Integration tests for todo commands with mocked GitHub API."""

import pytest
from unittest.mock import Mock, patch
from github import Github, GithubException

from ghoo.core import CreateTodoCommand, CheckTodoCommand, GitHubClient


class TestTodoCommandsIntegration:
    """Integration tests for todo commands with mocked GitHub API responses."""
    
    @pytest.fixture
    def mock_github_api(self):
        """Mock the GitHub API at the requests level."""
        with patch('ghoo.core.Github') as mock_github_class:
            # Create mock GitHub instance
            mock_github = Mock(spec=Github)
            mock_github_class.return_value = mock_github
            
            # Create mock repository
            mock_repo = Mock()
            mock_github.get_repo.return_value = mock_repo
            
            # Create mock issue with tasks
            mock_issue = Mock()
            mock_issue.number = 789
            mock_issue.title = "Integration Test Issue"
            mock_issue.html_url = "https://github.com/test/repo/issues/789"
            mock_issue.body = """## Summary
This is an integration test issue.

## Tasks
- [ ] Task 1
- [x] Task 2
- [ ] Task 3

## Notes
Some additional notes here.
"""
            mock_issue.edit = Mock()
            mock_repo.get_issue.return_value = mock_issue
            
            yield {
                'github': mock_github,
                'repo': mock_repo,
                'issue': mock_issue
            }
    
    def test_create_todo_full_workflow(self, mock_github_api):
        """Test complete workflow from GitHub client initialization to todo creation."""
        # Initialize GitHub client (will use mocked GitHub)
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        # Create and execute create-todo command
        command = CreateTodoCommand(github_client)
        result = command.execute("test/repo", 789, "Tasks", "New integration task")
        
        # Verify API calls were made correctly (called twice: once by TodoCommand, once by SetBodyCommand)
        assert mock_github_api['github'].get_repo.call_count == 2
        mock_github_api['github'].get_repo.assert_called_with("test/repo")
        assert mock_github_api['repo'].get_issue.call_count == 2
        mock_github_api['repo'].get_issue.assert_called_with(789)
        
        # Verify the issue body was updated
        mock_github_api['issue'].edit.assert_called_once()
        updated_body = mock_github_api['issue'].edit.call_args[1]['body']
        assert "New integration task" in updated_body
        assert "- [ ] New integration task" in updated_body
        
        # Verify result structure
        assert result['issue_number'] == 789
        assert result['issue_title'] == "Integration Test Issue"
        assert result['section_name'] == "Tasks"
        assert result['todo_text'] == "New integration task"
        assert result['section_created'] is False
        assert result['total_todos_in_section'] == 4  # 3 existing + 1 new
    
    def test_create_todo_new_section(self, mock_github_api):
        """Test creating todo in new section."""
        # Initialize GitHub client
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        # Create and execute create-todo command with new section
        command = CreateTodoCommand(github_client)
        result = command.execute("test/repo", 789, "New Section", "Todo in new section", create_section=True)
        
        # Verify the issue body was updated with new section
        mock_github_api['issue'].edit.assert_called_once()
        updated_body = mock_github_api['issue'].edit.call_args[1]['body']
        assert "## New Section" in updated_body
        assert "- [ ] Todo in new section" in updated_body
        
        # Verify result indicates section was created
        assert result['section_name'] == "New Section"
        assert result['total_todos_in_section'] == 1
    
    def test_check_todo_full_workflow(self, mock_github_api):
        """Test complete workflow for checking/unchecking todos."""
        # Initialize GitHub client
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        # Create and execute check-todo command
        command = CheckTodoCommand(github_client)
        result = command.execute("test/repo", 789, "Tasks", "Task 1")
        
        # Verify API calls (called twice: once by TodoCommand, once by SetBodyCommand)
        assert mock_github_api['github'].get_repo.call_count == 2
        mock_github_api['github'].get_repo.assert_called_with("test/repo")
        assert mock_github_api['repo'].get_issue.call_count == 2
        mock_github_api['repo'].get_issue.assert_called_with(789)
        
        # Verify the issue body was updated with checked todo
        mock_github_api['issue'].edit.assert_called_once()
        updated_body = mock_github_api['issue'].edit.call_args[1]['body']
        assert "- [x] Task 1" in updated_body
        assert "- [ ] Task 3" in updated_body  # Other todos unchanged
        
        # Verify result
        assert result['issue_number'] == 789
        assert result['todo_text'] == "Task 1"
        assert result['old_state'] is False
        assert result['new_state'] is True
        assert result['action'] == "checked"
    
    def test_check_todo_uncheck_existing(self, mock_github_api):
        """Test unchecking an already checked todo."""
        # Initialize GitHub client
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        # Create and execute check-todo command on checked item
        command = CheckTodoCommand(github_client)
        result = command.execute("test/repo", 789, "Tasks", "Task 2")
        
        # Verify the todo was unchecked
        updated_body = mock_github_api['issue'].edit.call_args[1]['body']
        assert "- [ ] Task 2" in updated_body
        
        # Verify result shows unchecking
        assert result['todo_text'] == "Task 2"
        assert result['old_state'] is True
        assert result['new_state'] is False
        assert result['action'] == "unchecked"
    
    def test_create_todo_duplicate_error(self, mock_github_api):
        """Test error when creating duplicate todo."""
        # Initialize GitHub client
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        # Try to create duplicate todo
        command = CreateTodoCommand(github_client)
        with pytest.raises(ValueError, match='Todo "Task 1" already exists'):
            command.execute("test/repo", 789, "Tasks", "Task 1")
        
        # Verify no API call to update was made
        mock_github_api['issue'].edit.assert_not_called()
    
    def test_check_todo_not_found_error(self, mock_github_api):
        """Test error when checking non-existent todo."""
        # Initialize GitHub client
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        # Try to check non-existent todo
        command = CheckTodoCommand(github_client)
        with pytest.raises(ValueError, match='No todos matching "nonexistent"'):
            command.execute("test/repo", 789, "Tasks", "nonexistent")
        
        # Verify no API call to update was made
        mock_github_api['issue'].edit.assert_not_called()
    
    def test_create_todo_section_not_found_error(self, mock_github_api):
        """Test error when section doesn't exist and create_section=False."""
        # Initialize GitHub client
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        # Try to create todo in non-existent section
        command = CreateTodoCommand(github_client)
        with pytest.raises(ValueError, match='Section "Nonexistent" not found'):
            command.execute("test/repo", 789, "Nonexistent", "New task")
        
        # Verify no API call to update was made
        mock_github_api['issue'].edit.assert_not_called()
    
    def test_issue_not_found_error(self, mock_github_api):
        """Test handling when issue is not found."""
        # Setup issue not found error
        github_exception = GithubException(404, "Not Found", {})
        mock_github_api['repo'].get_issue.side_effect = github_exception
        
        # Initialize and execute command
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
            command = CreateTodoCommand(github_client)
            
            # Should propagate GitHub exception
            with pytest.raises(GithubException):
                command.execute("test/repo", 99999, "Tasks", "New task")
    
    def test_permission_denied_error(self, mock_github_api):
        """Test handling when user lacks write permissions."""
        # Setup permission denied error
        github_exception = GithubException(403, "Forbidden", {})
        mock_github_api['repo'].get_issue.side_effect = github_exception
        
        # Initialize and execute command
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
            command = CheckTodoCommand(github_client)
            
            # Should propagate permission error
            with pytest.raises(GithubException):
                command.execute("test/repo", 789, "Tasks", "Task 1")
    
    def test_body_preservation_integration(self, mock_github_api):
        """Test that body structure is preserved during todo operations."""
        # Initialize GitHub client
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        # Add new todo
        create_command = CreateTodoCommand(github_client)
        create_command.execute("test/repo", 789, "Tasks", "New task")
        
        # Get the updated body
        updated_body = mock_github_api['issue'].edit.call_args[1]['body']
        
        # Verify structure is preserved
        assert "## Summary" in updated_body
        assert "This is an integration test issue." in updated_body
        assert "## Tasks" in updated_body
        assert "## Notes" in updated_body
        assert "Some additional notes here." in updated_body
        
        # Verify new todo was added
        assert "- [ ] New task" in updated_body
        
        # Verify existing todos are preserved
        assert "- [ ] Task 1" in updated_body
        assert "- [x] Task 2" in updated_body
        assert "- [ ] Task 3" in updated_body
    
    def test_special_characters_and_unicode(self, mock_github_api):
        """Test handling of special characters and Unicode in todos."""
        # Update mock issue with Unicode todos
        mock_github_api['issue'].body = """## Tasks
- [ ] Task with émojis 🚀
- [x] Task with 中文 characters
- [ ] Task with "quotes" and 'apostrophes'
"""
        
        # Initialize GitHub client
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        # Check todo with Unicode (this test focuses on checking rather than creating)
        check_command = CheckTodoCommand(github_client)
        result = check_command.execute("test/repo", 789, "Tasks", "émojis")
        
        # Verify Unicode handling in the result
        assert result['todo_text'] == "Task with émojis 🚀"
        assert result['old_state'] is False
        assert result['new_state'] is True
        
        # Verify Unicode is preserved in updated body
        updated_body = mock_github_api['issue'].edit.call_args[1]['body']
        assert "- [x] Task with émojis 🚀" in updated_body
        assert "- [x] Task with 中文 characters" in updated_body  # Other todos preserved
    
    def test_empty_section_handling(self, mock_github_api):
        """Test handling of sections with no existing todos."""
        # Update mock issue with empty section
        mock_github_api['issue'].body = """## Summary  
This is a test.

## Empty Section
This section has no todos yet.

## More Notes
Additional content.
"""
        
        # Initialize GitHub client
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'}):
            github_client = GitHubClient()
        
        # Add todo to empty section
        command = CreateTodoCommand(github_client)
        result = command.execute("test/repo", 789, "Empty Section", "First todo in empty section")
        
        # Verify todo was added correctly
        updated_body = mock_github_api['issue'].edit.call_args[1]['body']
        assert "## Empty Section" in updated_body
        assert "- [ ] First todo in empty section" in updated_body
        
        # Verify result
        assert result['total_todos_in_section'] == 1