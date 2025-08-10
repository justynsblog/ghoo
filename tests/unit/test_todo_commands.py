"""Unit tests for todo command classes."""

import pytest
from unittest.mock import Mock, MagicMock
from github import GithubException

from ghoo.core import TodoCommand, CreateTodoCommand, CheckTodoCommand, GitHubClient, SetBodyCommand
from ghoo.models import Section, Todo


class TestTodoCommand:
    """Unit tests for the TodoCommand base class."""
    
    @pytest.fixture
    def mock_github_client(self):
        """Mock GitHub client for testing."""
        mock_client = Mock(spec=GitHubClient)
        mock_github = Mock()
        mock_client.github = mock_github
        return mock_client
    
    @pytest.fixture
    def todo_command(self, mock_github_client):
        """Create TodoCommand instance for testing."""
        return TodoCommand(mock_github_client)
    
    @pytest.fixture
    def mock_issue(self):
        """Mock GitHub issue for testing."""
        mock_issue = Mock()
        mock_issue.number = 456
        mock_issue.title = "Test Issue"
        mock_issue.body = """## Summary
This is a test issue.

## Tasks
- [ ] Task 1
- [x] Task 2
- [ ] Task 3
"""
        return mock_issue
    
    @pytest.fixture
    def sample_parsed_body(self):
        """Sample parsed body data for testing."""
        return {
            'pre_section_description': 'This is a test issue.',
            'sections': [
                Section(
                    title='Tasks',
                    body='- [ ] Task 1\n- [x] Task 2\n- [ ] Task 3',
                    todos=[
                        Todo(text='Task 1', checked=False, line_number=4),
                        Todo(text='Task 2', checked=True, line_number=5),
                        Todo(text='Task 3', checked=False, line_number=6),
                    ]
                )
            ]
        }
    
    def test_init(self, mock_github_client):
        """Test TodoCommand initialization."""
        command = TodoCommand(mock_github_client)
        assert command.github == mock_github_client
        assert isinstance(command.set_body_command, SetBodyCommand)
    
    def test_get_issue_and_parsed_body_success(self, todo_command, mock_github_client, mock_issue):
        """Test successful issue retrieval and body parsing."""
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_github_client.github.get_repo.return_value = mock_repo
        
        result = todo_command._get_issue_and_parsed_body("owner/repo", 456)
        
        mock_github_client.github.get_repo.assert_called_once_with("owner/repo")
        mock_repo.get_issue.assert_called_once_with(456)
        assert result['issue'] == mock_issue
        assert 'parsed_body' in result
        assert 'sections' in result['parsed_body']
    
    def test_get_issue_invalid_repo_format(self, todo_command):
        """Test error with invalid repository format."""
        invalid_repos = ["invalid", "owner", "owner/repo/extra", ""]
        
        for invalid_repo in invalid_repos:
            with pytest.raises(ValueError, match="Invalid repository format"):
                todo_command._get_issue_and_parsed_body(invalid_repo, 456)
    
    def test_find_section_success(self, todo_command, sample_parsed_body):
        """Test finding a section by name."""
        section = todo_command._find_section(sample_parsed_body, "Tasks")
        assert section is not None
        assert section.title == "Tasks"
        assert len(section.todos) == 3
    
    def test_find_section_case_insensitive(self, todo_command, sample_parsed_body):
        """Test finding a section with case insensitive matching."""
        section = todo_command._find_section(sample_parsed_body, "tasks")
        assert section is not None
        assert section.title == "Tasks"
        
        section = todo_command._find_section(sample_parsed_body, "TASKS")
        assert section is not None
        assert section.title == "Tasks"
    
    def test_find_section_not_found(self, todo_command, sample_parsed_body):
        """Test finding non-existent section."""
        section = todo_command._find_section(sample_parsed_body, "Nonexistent")
        assert section is None
    
    def test_reconstruct_body_with_todos(self, todo_command, sample_parsed_body):
        """Test body reconstruction with existing todos."""
        reconstructed = todo_command._reconstruct_body(sample_parsed_body)
        expected_lines = [
            "This is a test issue.",
            "",
            "## Tasks",
            "- [ ] Task 1",
            "- [x] Task 2", 
            "- [ ] Task 3"
        ]
        assert reconstructed == '\n'.join(expected_lines)
    
    def test_reconstruct_body_with_updated_todos(self, todo_command, sample_parsed_body):
        """Test body reconstruction with updated todo states."""
        # Update todo states
        sample_parsed_body['sections'][0].todos[0].checked = True  # Task 1 checked
        sample_parsed_body['sections'][0].todos[1].checked = False  # Task 2 unchecked
        
        reconstructed = todo_command._reconstruct_body(sample_parsed_body)
        expected_lines = [
            "This is a test issue.",
            "",
            "## Tasks",
            "- [x] Task 1",
            "- [ ] Task 2", 
            "- [ ] Task 3"
        ]
        assert reconstructed == '\n'.join(expected_lines)
    
    def test_reconstruct_body_with_new_todos(self, todo_command, sample_parsed_body):
        """Test body reconstruction with new todos added."""
        # Add a new todo without line number
        new_todo = Todo(text='New Task', checked=False, line_number=None)
        sample_parsed_body['sections'][0].todos.append(new_todo)
        
        reconstructed = todo_command._reconstruct_body(sample_parsed_body)
        expected_lines = [
            "This is a test issue.",
            "",
            "## Tasks",
            "- [ ] Task 1",
            "- [x] Task 2", 
            "- [ ] Task 3",
            "- [ ] New Task"
        ]
        assert reconstructed == '\n'.join(expected_lines)


class TestCreateTodoCommand:
    """Unit tests for the CreateTodoCommand class."""
    
    @pytest.fixture
    def mock_github_client(self):
        """Mock GitHub client for testing."""
        mock_client = Mock(spec=GitHubClient)
        mock_github = Mock()
        mock_client.github = mock_github
        return mock_client
    
    @pytest.fixture
    def create_todo_command(self, mock_github_client):
        """Create CreateTodoCommand instance for testing."""
        command = CreateTodoCommand(mock_github_client)
        command.set_body_command = Mock(spec=SetBodyCommand)
        return command
    
    @pytest.fixture
    def mock_issue_with_sections(self):
        """Mock issue with existing sections."""
        mock_issue = Mock()
        mock_issue.number = 123
        mock_issue.title = "Test Issue"
        mock_issue.html_url = "https://github.com/owner/repo/issues/123"
        mock_issue.body = """## Tasks
- [ ] Existing task
        
## Notes
Some notes here.
"""
        return mock_issue
    
    def test_execute_success_existing_section(self, create_todo_command, mock_github_client, mock_issue_with_sections):
        """Test creating todo in existing section."""
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue_with_sections
        mock_github_client.github.get_repo.return_value = mock_repo
        
        create_todo_command.set_body_command.execute.return_value = {"success": True}
        
        result = create_todo_command.execute("owner/repo", 123, "Tasks", "New task")
        
        assert result['issue_number'] == 123
        assert result['issue_title'] == "Test Issue"
        assert result['section_name'] == "Tasks"
        assert result['todo_text'] == "New task"
        assert result['section_created'] is False
        assert result['total_todos_in_section'] == 2  # 1 existing + 1 new
        
        create_todo_command.set_body_command.execute.assert_called_once()
    
    def test_execute_create_new_section(self, create_todo_command, mock_github_client, mock_issue_with_sections):
        """Test creating todo in new section."""
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue_with_sections
        mock_github_client.github.get_repo.return_value = mock_repo
        
        create_todo_command.set_body_command.execute.return_value = {"success": True}
        
        result = create_todo_command.execute("owner/repo", 123, "New Section", "New task", create_section=True)
        
        assert result['section_name'] == "New Section"
        assert result['todo_text'] == "New task"
        assert result['total_todos_in_section'] == 1
        
        create_todo_command.set_body_command.execute.assert_called_once()
    
    def test_execute_section_not_found_no_create(self, create_todo_command, mock_github_client, mock_issue_with_sections):
        """Test error when section doesn't exist and create_section=False."""
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue_with_sections
        mock_github_client.github.get_repo.return_value = mock_repo
        
        with pytest.raises(ValueError, match='Section "Nonexistent" not found'):
            create_todo_command.execute("owner/repo", 123, "Nonexistent", "New task")
    
    def test_execute_duplicate_todo(self, create_todo_command, mock_github_client, mock_issue_with_sections):
        """Test error when trying to add duplicate todo."""
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue_with_sections
        mock_github_client.github.get_repo.return_value = mock_repo
        
        with pytest.raises(ValueError, match='Todo "Existing task" already exists'):
            create_todo_command.execute("owner/repo", 123, "Tasks", "Existing task")
    
    def test_execute_empty_todo_text(self, create_todo_command):
        """Test error with empty todo text."""
        with pytest.raises(ValueError, match="Todo text cannot be empty"):
            create_todo_command.execute("owner/repo", 123, "Tasks", "")
        
        with pytest.raises(ValueError, match="Todo text cannot be empty"):
            create_todo_command.execute("owner/repo", 123, "Tasks", "   ")


class TestCheckTodoCommand:
    """Unit tests for the CheckTodoCommand class."""
    
    @pytest.fixture
    def mock_github_client(self):
        """Mock GitHub client for testing."""
        mock_client = Mock(spec=GitHubClient)
        mock_github = Mock()
        mock_client.github = mock_github
        return mock_client
    
    @pytest.fixture
    def check_todo_command(self, mock_github_client):
        """Create CheckTodoCommand instance for testing."""
        command = CheckTodoCommand(mock_github_client)
        command.set_body_command = Mock(spec=SetBodyCommand)
        return command
    
    @pytest.fixture
    def mock_issue_with_todos(self):
        """Mock issue with todos."""
        mock_issue = Mock()
        mock_issue.number = 456
        mock_issue.title = "Test Issue with Todos"
        mock_issue.html_url = "https://github.com/owner/repo/issues/456"
        mock_issue.body = """## Tasks
- [ ] First task
- [x] Second task  
- [ ] Third task
- [ ] Fourth task with special characters 🚀
"""
        return mock_issue
    
    def test_execute_success_check_todo(self, check_todo_command, mock_github_client, mock_issue_with_todos):
        """Test checking an unchecked todo."""
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue_with_todos
        mock_github_client.github.get_repo.return_value = mock_repo
        
        check_todo_command.set_body_command.execute.return_value = {"success": True}
        
        result = check_todo_command.execute("owner/repo", 456, "Tasks", "First task")
        
        assert result['issue_number'] == 456
        assert result['todo_text'] == "First task"
        assert result['old_state'] is False
        assert result['new_state'] is True
        assert result['action'] == "checked"
        
        check_todo_command.set_body_command.execute.assert_called_once()
    
    def test_execute_success_uncheck_todo(self, check_todo_command, mock_github_client, mock_issue_with_todos):
        """Test unchecking a checked todo."""
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue_with_todos
        mock_github_client.github.get_repo.return_value = mock_repo
        
        check_todo_command.set_body_command.execute.return_value = {"success": True}
        
        result = check_todo_command.execute("owner/repo", 456, "Tasks", "Second task")
        
        assert result['todo_text'] == "Second task"
        assert result['old_state'] is True
        assert result['new_state'] is False
        assert result['action'] == "unchecked"
    
    def test_execute_partial_match(self, check_todo_command, mock_github_client, mock_issue_with_todos):
        """Test partial text matching."""
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue_with_todos
        mock_github_client.github.get_repo.return_value = mock_repo
        
        check_todo_command.set_body_command.execute.return_value = {"success": True}
        
        result = check_todo_command.execute("owner/repo", 456, "Tasks", "special")
        
        assert result['todo_text'] == "Fourth task with special characters 🚀"
        assert result['old_state'] is False
        assert result['new_state'] is True
    
    def test_execute_section_not_found(self, check_todo_command, mock_github_client, mock_issue_with_todos):
        """Test error when section doesn't exist."""
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue_with_todos
        mock_github_client.github.get_repo.return_value = mock_repo
        
        with pytest.raises(ValueError, match='Section "Nonexistent" not found'):
            check_todo_command.execute("owner/repo", 456, "Nonexistent", "task")
    
    def test_execute_no_matching_todos(self, check_todo_command, mock_github_client, mock_issue_with_todos):
        """Test error when no todos match."""
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue_with_todos
        mock_github_client.github.get_repo.return_value = mock_repo
        
        with pytest.raises(ValueError, match='No todos matching "nonexistent" found'):
            check_todo_command.execute("owner/repo", 456, "Tasks", "nonexistent")
    
    def test_execute_ambiguous_match(self, check_todo_command, mock_github_client, mock_issue_with_todos):
        """Test error when multiple todos match."""
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue_with_todos
        mock_github_client.github.get_repo.return_value = mock_repo
        
        with pytest.raises(ValueError, match='Multiple todos match "task"'):
            check_todo_command.execute("owner/repo", 456, "Tasks", "task")
    
    def test_execute_empty_match_text(self, check_todo_command):
        """Test error with empty match text."""
        with pytest.raises(ValueError, match="Match text cannot be empty"):
            check_todo_command.execute("owner/repo", 456, "Tasks", "")
        
        with pytest.raises(ValueError, match="Match text cannot be empty"):
            check_todo_command.execute("owner/repo", 456, "Tasks", "   ")
    
    def test_execute_no_todos_in_section(self, check_todo_command, mock_github_client):
        """Test error when section has no todos."""
        mock_issue = Mock()
        mock_issue.number = 789
        mock_issue.title = "Empty Section Issue"
        mock_issue.body = """## Empty Tasks
Nothing here yet.
"""
        
        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue
        mock_github_client.github.get_repo.return_value = mock_repo
        
        with pytest.raises(ValueError, match='No todos found in section "Empty Tasks"'):
            check_todo_command.execute("owner/repo", 789, "Empty Tasks", "anything")