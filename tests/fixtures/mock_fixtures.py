"""Mock-related test fixtures."""

import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from unittest.mock import Mock, patch, MagicMock

import pytest


class MockEnvironment:
    """Mock environment for testing."""
    
    def __init__(self):
        self.env_vars: Dict[str, str] = {}
        self.file_system: Dict[str, str] = {}
        self.processes: List[Dict[str, Any]] = []
        self.network_responses: Dict[str, Any] = {}
    
    def set_env_var(self, key: str, value: str):
        """Set an environment variable."""
        self.env_vars[key] = value
    
    def create_file(self, path: str, content: str):
        """Create a mock file."""
        self.file_system[path] = content
    
    def add_process_response(self, command: List[str], returncode: int = 0, 
                           stdout: str = "", stderr: str = ""):
        """Add a mock process response."""
        self.processes.append({
            'command': command,
            'returncode': returncode,
            'stdout': stdout,
            'stderr': stderr
        })
    
    def add_network_response(self, url: str, response: Dict[str, Any]):
        """Add a mock network response."""
        self.network_responses[url] = response


class MockFileSystem:
    """Mock file system for testing."""
    
    def __init__(self, temp_dir: Optional[Path] = None):
        self.temp_dir = temp_dir or Path(tempfile.mkdtemp())
        self.files: Dict[str, str] = {}
        self.directories: List[str] = []
    
    def create_file(self, path: str, content: str = ""):
        """Create a file in the mock file system."""
        file_path = self.temp_dir / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        self.files[path] = content
        return file_path
    
    def create_directory(self, path: str):
        """Create a directory in the mock file system."""
        dir_path = self.temp_dir / path
        dir_path.mkdir(parents=True, exist_ok=True)
        self.directories.append(path)
        return dir_path
    
    def get_file_content(self, path: str) -> str:
        """Get content of a file."""
        return self.files.get(path, "")
    
    def file_exists(self, path: str) -> bool:
        """Check if a file exists."""
        return path in self.files or (self.temp_dir / path).exists()
    
    def cleanup(self):
        """Clean up temporary files."""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)


class MockSubprocess:
    """Mock subprocess for testing."""
    
    def __init__(self):
        self.call_history: List[Dict[str, Any]] = []
        self.responses: Dict[str, Dict[str, Any]] = {}
        self.default_response = {
            'returncode': 0,
            'stdout': '',
            'stderr': ''
        }
    
    def add_response(self, command_pattern: str, returncode: int = 0, 
                    stdout: str = "", stderr: str = ""):
        """Add a response for a command pattern."""
        self.responses[command_pattern] = {
            'returncode': returncode,
            'stdout': stdout,
            'stderr': stderr
        }
    
    def run(self, command, **kwargs):
        """Mock subprocess.run."""
        command_str = ' '.join(command) if isinstance(command, list) else str(command)
        
        # Record the call
        call_record = {
            'command': command,
            'command_str': command_str,
            'kwargs': kwargs
        }
        self.call_history.append(call_record)
        
        # Find matching response
        response = self.default_response.copy()
        for pattern, resp in self.responses.items():
            if pattern in command_str:
                response.update(resp)
                break
        
        # Create mock result object
        result = Mock()
        result.returncode = response['returncode']
        result.stdout = response['stdout']
        result.stderr = response['stderr']
        result.args = command
        
        return result
    
    def assert_called_with(self, expected_command: str):
        """Assert that a command was called."""
        called_commands = [call['command_str'] for call in self.call_history]
        assert any(expected_command in cmd for cmd in called_commands), (
            f"Command containing '{expected_command}' not found in {called_commands}"
        )
    
    def clear_history(self):
        """Clear call history."""
        self.call_history.clear()


class MockAPIResponses:
    """Mock API responses for testing."""
    
    def __init__(self):
        self.github_responses: Dict[str, Any] = {}
        self.http_responses: Dict[str, Any] = {}
        self.default_responses = self._get_default_responses()
    
    def _get_default_responses(self) -> Dict[str, Any]:
        """Get default API responses."""
        return {
            'github_user': {
                'login': 'testuser',
                'id': 12345,
                'name': 'Test User',
                'email': 'test@example.com'
            },
            'github_repo': {
                'id': 67890,
                'name': 'test-repo',
                'full_name': 'testuser/test-repo',
                'private': False,
                'html_url': 'https://github.com/testuser/test-repo'
            },
            'github_issue': {
                'id': 111,
                'number': 1,
                'title': 'Test Issue',
                'body': 'Test issue body',
                'state': 'open',
                'labels': []
            },
            'github_label': {
                'id': 222,
                'name': 'test-label',
                'color': '0366d6',
                'description': 'Test label'
            }
        }
    
    def set_github_response(self, endpoint: str, response: Dict[str, Any]):
        """Set a mock GitHub API response."""
        self.github_responses[endpoint] = response
    
    def get_github_response(self, endpoint: str) -> Dict[str, Any]:
        """Get a mock GitHub API response."""
        return self.github_responses.get(endpoint, self.default_responses.get(endpoint, {}))
    
    def set_http_response(self, url: str, response: Dict[str, Any]):
        """Set a mock HTTP response."""
        self.http_responses[url] = response
    
    def get_http_response(self, url: str) -> Dict[str, Any]:
        """Get a mock HTTP response."""
        return self.http_responses.get(url, {'status': 200, 'data': {}})


@pytest.fixture(scope="function")
def mock_environment():
    """Provide mock environment for testing."""
    return MockEnvironment()


@pytest.fixture(scope="function")
def mock_filesystem(tmp_path):
    """Provide mock file system for testing."""
    mock_fs = MockFileSystem(tmp_path)
    yield mock_fs
    mock_fs.cleanup()


@pytest.fixture(scope="function")
def mock_subprocess():
    """Provide mock subprocess for testing."""
    mock_sub = MockSubprocess()
    
    with patch('subprocess.run', side_effect=mock_sub.run):
        yield mock_sub


@pytest.fixture(scope="function")
def mock_api_responses():
    """Provide mock API responses for testing."""
    return MockAPIResponses()


@pytest.fixture(scope="function")
def mock_github_api(mock_api_responses):
    """Provide mock GitHub API."""
    with patch('github.Github') as mock_github:
        # Configure the mock
        mock_client = Mock()
        mock_github.return_value = mock_client
        
        # Mock repository
        mock_repo = Mock()
        mock_client.get_repo.return_value = mock_repo
        
        # Mock issue creation
        def create_issue(title, body="", labels=None):
            issue_data = mock_api_responses.get_github_response('github_issue').copy()
            issue_data.update({
                'title': title,
                'body': body,
                'labels': labels or []
            })
            mock_issue = Mock()
            for key, value in issue_data.items():
                setattr(mock_issue, key, value)
            return mock_issue
        
        mock_repo.create_issue.side_effect = create_issue
        
        # Mock label creation
        def create_label(name, color="0366d6", description=""):
            label_data = mock_api_responses.get_github_response('github_label').copy()
            label_data.update({
                'name': name,
                'color': color,
                'description': description
            })
            mock_label = Mock()
            for key, value in label_data.items():
                setattr(mock_label, key, value)
            return mock_label
        
        mock_repo.create_label.side_effect = create_label
        
        yield mock_client


@pytest.fixture(scope="function")
def isolated_env(tmp_path, monkeypatch):
    """Provide isolated environment for testing."""
    # Create temporary directory structure
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    
    # Change to test directory
    monkeypatch.chdir(test_dir)
    
    # Set temporary HOME
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    
    # Clear potentially problematic environment variables
    for var in ['GITHUB_TOKEN', 'GH_TOKEN', 'PYTHONPATH']:
        monkeypatch.delenv(var, raising=False)
    
    return {
        'project_dir': test_dir,
        'home_dir': home_dir,
        'tmp_path': tmp_path
    }


class TestDataFactory:
    """Factory for creating test data."""
    
    @staticmethod
    def create_issue_body(sections: Optional[Dict[str, str]] = None) -> str:
        """Create a test issue body with specified sections."""
        default_sections = {
            'Overview': 'This is a test issue.',
            'Acceptance Criteria': '- [ ] Test criterion 1\n- [ ] Test criterion 2',
            'Tasks': '- [ ] Test task 1\n- [ ] Test task 2'
        }
        
        if sections:
            default_sections.update(sections)
        
        body_parts = []
        for section, content in default_sections.items():
            body_parts.append(f"## {section}")
            body_parts.append(content)
            body_parts.append("")
        
        return "\n".join(body_parts)
    
    @staticmethod
    def create_ghoo_config(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a test ghoo configuration."""
        default_config = {
            'project_url': 'https://github.com/test/repo',
            'status_method': 'labels',
            'required_sections': ['Overview', 'Acceptance Criteria']
        }
        
        if overrides:
            default_config.update(overrides)
        
        return default_config


@pytest.fixture(scope="function")
def test_data_factory():
    """Provide test data factory."""
    return TestDataFactory()


# Backwards compatibility fixtures
@pytest.fixture(scope="function")
def mock_env_legacy(mock_environment):
    """Legacy mock environment fixture."""
    return mock_environment


@pytest.fixture(scope="function")
def mock_fs_legacy(mock_filesystem):
    """Legacy mock filesystem fixture.""" 
    return mock_filesystem