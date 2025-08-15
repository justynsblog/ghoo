"""Unified test utilities and helpers for ghoo test suite.

This module consolidates test utilities from various sources into a single,
well-organized collection of helper functions and classes. It provides
common assertions, verifications, test data generators, and utility
functions used across all test types.

Features:
- Common test assertions and verifications
- GitHub API test utilities
- CLI testing helpers  
- Test data factories and generators
- File system utilities for tests
- Mock response builders
- Test environment utilities
"""

import json
import yaml
import time
import tempfile
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable
from unittest.mock import Mock, MagicMock
import subprocess

import pytest
from github import Github, Repository, Issue, Label
from github.GithubException import GithubException


class GitHubTestUtils:
    """GitHub API testing utilities."""
    
    @staticmethod
    def create_test_issue(repo: Repository, 
                         title: str,
                         body: str = "",
                         labels: Optional[List[str]] = None) -> Issue:
        """Create a test issue in the repository."""
        try:
            issue = repo.create_issue(title=title, body=body, labels=labels or [])
            return issue
        except GithubException as e:
            raise AssertionError(f"Failed to create test issue: {e}")
    
    @staticmethod
    def verify_issue_exists(repo: Repository, issue_number: int) -> Issue:
        """Verify that an issue exists and return it."""
        try:
            return repo.get_issue(issue_number)
        except GithubException:
            raise AssertionError(f"Issue #{issue_number} not found in {repo.full_name}")
    
    @staticmethod
    def verify_issue_has_label(issue: Issue, label_name: str):
        """Verify that an issue has a specific label."""
        label_names = [label.name for label in issue.labels]
        assert label_name in label_names, (
            f"Label '{label_name}' not found on issue #{issue.number}. "
            f"Found labels: {label_names}"
        )
    
    @staticmethod
    def verify_issue_body_contains(issue: Issue, expected_text: str):
        """Verify that an issue body contains expected text."""
        assert expected_text in (issue.body or ""), (
            f"Expected text not found in issue body.\n"
            f"Expected: {expected_text}\n"
            f"Actual body: {issue.body}"
        )
    
    @staticmethod
    def verify_issue_body_section(issue: Issue, section_name: str, 
                                 expected_content: Optional[str] = None):
        """Verify that an issue body contains a specific section."""
        body = issue.body or ""
        section_header = f"## {section_name}"
        
        assert section_header in body, (
            f"Section '{section_name}' not found in issue #{issue.number} body"
        )
        
        if expected_content:
            assert expected_content in body, (
                f"Expected content '{expected_content}' not found in section '{section_name}' "
                f"of issue #{issue.number}"
            )
    
    @staticmethod
    def create_or_get_label(repo: Repository, name: str, color: str = "0366d6") -> Label:
        """Create a label or return it if it already exists."""
        try:
            return repo.get_label(name)
        except GithubException:
            try:
                return repo.create_label(name=name, color=color)
            except GithubException as e:
                raise AssertionError(f"Failed to create label '{name}': {e}")
    
    @staticmethod
    def cleanup_test_issues(repo: Repository, title_prefix: str = "TEST:"):
        """Close all issues with a specific title prefix."""
        for issue in repo.get_issues(state='open'):
            if issue.title.startswith(title_prefix):
                try:
                    issue.edit(state='closed')
                except Exception:
                    pass  # Best effort cleanup
    
    @staticmethod
    def wait_for_issue_state(repo: Repository, issue_number: int, 
                            expected_state: str, timeout: int = 10):
        """Wait for an issue to reach a specific state."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                issue = repo.get_issue(issue_number)
                if issue.state == expected_state:
                    return
            except GithubException:
                pass
            time.sleep(1)
        
        raise AssertionError(
            f"Issue #{issue_number} did not reach state '{expected_state}' "
            f"within {timeout} seconds"
        )
    
    @staticmethod
    def run_graphql_query(github_client: Github, query: str, 
                         variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run a GraphQL query against GitHub API."""
        import requests
        
        headers = {
            "Authorization": f"Bearer {github_client._Github__requester._Requester__authorizationHeader.split()[1]}",
            "Content-Type": "application/json"
        }
        
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        response = requests.post(
            "https://api.github.com/graphql",
            json=payload,
            headers=headers
        )
        
        if response.status_code != 200:
            raise AssertionError(f"GraphQL query failed: {response.text}")
        
        data = response.json()
        if "errors" in data:
            raise AssertionError(f"GraphQL query errors: {data['errors']}")
        
        return data["data"]


class CliTestUtils:
    """CLI testing utilities."""
    
    @staticmethod
    def parse_json_output(output: str) -> Any:
        """Parse JSON output from CLI command."""
        try:
            return json.loads(output)
        except json.JSONDecodeError as e:
            raise AssertionError(f"Failed to parse JSON output: {e}\nOutput: {output}")
    
    @staticmethod
    def parse_yaml_output(output: str) -> Any:
        """Parse YAML output from CLI command."""
        try:
            return yaml.safe_load(output)
        except yaml.YAMLError as e:
            raise AssertionError(f"Failed to parse YAML output: {e}\nOutput: {output}")
    
    @staticmethod
    def assert_command_success(result, expected_output: Optional[str] = None):
        """Assert that a CLI command succeeded."""
        # Handle both subprocess.CompletedProcess and CliExecutionResult
        exit_code = getattr(result, 'exit_code', getattr(result, 'returncode', None))
        stdout = getattr(result, 'stdout', getattr(result, 'output', ''))
        stderr = getattr(result, 'stderr', '')
        
        assert exit_code == 0, (
            f"Command failed with exit code {exit_code}\n"
            f"stdout: {stdout}\n"
            f"stderr: {stderr}"
        )
        
        if expected_output:
            assert expected_output in stdout, (
                f"Expected output not found.\n"
                f"Expected: {expected_output}\n"
                f"Actual stdout: {stdout}"
            )
    
    @staticmethod
    def assert_command_error(result, expected_error: Optional[str] = None,
                           exit_code: Optional[int] = None):
        """Assert that a CLI command failed as expected."""
        # Handle both subprocess.CompletedProcess and CliExecutionResult
        actual_exit_code = getattr(result, 'exit_code', getattr(result, 'returncode', None))
        stdout = getattr(result, 'stdout', getattr(result, 'output', ''))
        stderr = getattr(result, 'stderr', '')
        
        if exit_code is not None:
            assert actual_exit_code == exit_code, (
                f"Expected exit code {exit_code}, got {actual_exit_code}\n"
                f"stdout: {stdout}\n"
                f"stderr: {stderr}"
            )
        else:
            assert actual_exit_code != 0, (
                f"Expected command to fail but it succeeded\n"
                f"stdout: {stdout}"
            )
        
        if expected_error:
            output = stderr + stdout
            assert expected_error in output, (
                f"Expected error not found.\n"
                f"Expected: {expected_error}\n"
                f"Actual output: {output}"
            )
    
    @staticmethod
    def assert_output_contains(result, expected_text: str):
        """Assert that command output contains expected text."""
        stdout = getattr(result, 'stdout', getattr(result, 'output', ''))
        stderr = getattr(result, 'stderr', '')
        output = stdout + stderr
        
        assert expected_text in output, (
            f"Expected text '{expected_text}' not found in command output\n"
            f"stdout: {stdout}\n"
            f"stderr: {stderr}"
        )
    
    @staticmethod
    def assert_output_matches_pattern(result, pattern: str):
        """Assert that command output matches a regex pattern."""
        import re
        
        stdout = getattr(result, 'stdout', getattr(result, 'output', ''))
        stderr = getattr(result, 'stderr', '')
        output = stdout + stderr
        
        assert re.search(pattern, output), (
            f"Pattern '{pattern}' not found in command output\n"
            f"stdout: {stdout}\n" 
            f"stderr: {stderr}"
        )
    
    @staticmethod
    def create_ghoo_config(project_dir: Union[str, Path], 
                          config: Dict[str, Any]) -> str:
        """Create a ghoo.yaml config file in the specified directory."""
        config_path = Path(project_dir) / 'ghoo.yaml'
        
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return str(config_path)


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
    def create_epic_body(title: str = "Test Epic") -> str:
        """Create a test epic body."""
        return TestDataFactory.create_issue_body({
            'Overview': f'This is a test epic: {title}',
            'Acceptance Criteria': '- [ ] Epic criterion 1\n- [ ] Epic criterion 2',
            'Tasks': '- [ ] Task 1\n- [ ] Task 2'
        })
    
    @staticmethod
    def create_task_body(title: str = "Test Task", parent_epic: Optional[int] = None) -> str:
        """Create a test task body."""
        sections = {
            'Overview': f'This is a test task: {title}',
            'Acceptance Criteria': '- [ ] Task criterion 1\n- [ ] Task criterion 2',
            'Sub-tasks': '- [ ] Sub-task 1\n- [ ] Sub-task 2'
        }
        
        if parent_epic:
            sections['Parent Epic'] = f'Relates to #{parent_epic}'
        
        return TestDataFactory.create_issue_body(sections)
    
    @staticmethod
    def create_subtask_body(title: str = "Test Sub-task", parent_task: Optional[int] = None) -> str:
        """Create a test sub-task body."""
        sections = {
            'Overview': f'This is a test sub-task: {title}',
            'Acceptance Criteria': '- [ ] Sub-task criterion 1\n- [ ] Sub-task criterion 2'
        }
        
        if parent_task:
            sections['Parent Task'] = f'Relates to #{parent_task}'
        
        return TestDataFactory.create_issue_body(sections)
    
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
    
    @staticmethod
    def create_sample_labels() -> List[Dict[str, str]]:
        """Create sample GitHub labels for testing."""
        return [
            {'name': 'type:epic', 'color': '0052CC', 'description': 'Epic issue type'},
            {'name': 'type:task', 'color': '0052CC', 'description': 'Task issue type'},
            {'name': 'type:subtask', 'color': '0052CC', 'description': 'Sub-task issue type'},
            {'name': 'status:backlog', 'color': 'FBCA04', 'description': 'Backlog status'},
            {'name': 'status:planning', 'color': 'FBCA04', 'description': 'Planning status'},
            {'name': 'status:in-progress', 'color': '0E8A16', 'description': 'In progress status'},
            {'name': 'status:closed', 'color': '5319E7', 'description': 'Closed status'}
        ]


class FileSystemTestUtils:
    """File system utilities for tests."""
    
    @staticmethod
    def create_temp_directory(prefix: str = "ghoo_test_") -> Path:
        """Create a temporary directory for testing."""
        temp_dir = Path(tempfile.mkdtemp(prefix=prefix))
        return temp_dir
    
    @staticmethod
    def create_project_structure(base_dir: Path, 
                                include_ghoo_config: bool = True) -> Dict[str, Path]:
        """Create a basic project directory structure."""
        # Create directories
        src_dir = base_dir / "src"
        tests_dir = base_dir / "tests"
        ghoo_dir = src_dir / "ghoo"
        
        for directory in [src_dir, tests_dir, ghoo_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Create basic files
        (ghoo_dir / "__init__.py").touch()
        (ghoo_dir / "main.py").write_text("# Placeholder main.py")
        (tests_dir / "__init__.py").touch()
        
        # Create pyproject.toml
        pyproject_content = """
[project]
name = "test-project"
version = "0.1.0"
dependencies = []
"""
        (base_dir / "pyproject.toml").write_text(pyproject_content.strip())
        
        # Create ghoo.yaml if requested
        if include_ghoo_config:
            config = TestDataFactory.create_ghoo_config()
            CliTestUtils.create_ghoo_config(base_dir, config)
        
        return {
            'base': base_dir,
            'src': src_dir,
            'tests': tests_dir,
            'ghoo': ghoo_dir
        }
    
    @staticmethod
    def cleanup_temp_directory(temp_dir: Path):
        """Clean up a temporary directory."""
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass  # Best effort cleanup


class MockResponseBuilder:
    """Builder for creating mock API responses."""
    
    @staticmethod
    def github_issue_response(issue_number: int = 1, 
                             title: str = "Test Issue",
                             body: str = "",
                             state: str = "open",
                             labels: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create a mock GitHub issue response."""
        return {
            'id': 100 + issue_number,
            'number': issue_number,
            'title': title,
            'body': body,
            'state': state,
            'labels': [{'name': label} for label in (labels or [])],
            'html_url': f'https://github.com/test/repo/issues/{issue_number}',
            'created_at': '2023-01-01T00:00:00Z',
            'updated_at': '2023-01-01T00:00:00Z'
        }
    
    @staticmethod
    def github_repository_response(full_name: str = "test/repo") -> Dict[str, Any]:
        """Create a mock GitHub repository response."""
        owner, name = full_name.split('/')
        return {
            'id': 12345,
            'name': name,
            'full_name': full_name,
            'owner': {'login': owner},
            'html_url': f'https://github.com/{full_name}',
            'private': False,
            'description': 'Test repository'
        }
    
    @staticmethod
    def github_label_response(name: str, color: str = "0366d6", 
                             description: str = "") -> Dict[str, Any]:
        """Create a mock GitHub label response."""
        return {
            'id': hash(name) % 10000,
            'name': name,
            'color': color,
            'description': description
        }


class TestValidationUtils:
    """Utilities for test validation and assertions."""
    
    @staticmethod
    def validate_issue_structure(issue_body: str, 
                                required_sections: List[str]) -> List[str]:
        """Validate that issue body contains required sections."""
        issues = []
        
        for section in required_sections:
            section_header = f"## {section}"
            if section_header not in issue_body:
                issues.append(f"Missing required section: {section}")
        
        return issues
    
    @staticmethod
    def validate_todo_format(todo_line: str) -> bool:
        """Validate that a line is a properly formatted todo."""
        import re
        # Match patterns like "- [ ] Todo item" or "- [x] Completed item"
        pattern = r'^\s*-\s*\[[x\s]\]\s+.+$'
        return bool(re.match(pattern, todo_line))
    
    @staticmethod
    def count_todos(issue_body: str) -> Dict[str, int]:
        """Count todos in issue body."""
        lines = issue_body.split('\n')
        total = 0
        completed = 0
        
        for line in lines:
            if TestValidationUtils.validate_todo_format(line):
                total += 1
                if '[x]' in line.lower():
                    completed += 1
        
        return {
            'total': total,
            'completed': completed,
            'remaining': total - completed
        }
    
    @staticmethod
    def validate_ghoo_config(config: Dict[str, Any]) -> List[str]:
        """Validate ghoo configuration."""
        issues = []
        
        required_fields = ['project_url', 'status_method']
        for field in required_fields:
            if field not in config:
                issues.append(f"Missing required field: {field}")
        
        if 'project_url' in config:
            url = config['project_url']
            if not isinstance(url, str) or not url.startswith('https://github.com/'):
                issues.append("project_url must be a valid GitHub repository URL")
        
        if 'status_method' in config:
            method = config['status_method']
            if method not in ['labels', 'milestones', 'projects']:
                issues.append(f"Invalid status_method: {method}")
        
        return issues


# Context managers for test utilities

class TemporaryProjectContext:
    """Context manager for temporary project setup."""
    
    def __init__(self, include_ghoo_config: bool = True):
        self.include_ghoo_config = include_ghoo_config
        self.temp_dir = None
        self.project_structure = None
    
    def __enter__(self) -> Dict[str, Path]:
        self.temp_dir = FileSystemTestUtils.create_temp_directory()
        self.project_structure = FileSystemTestUtils.create_project_structure(
            self.temp_dir, 
            self.include_ghoo_config
        )
        return self.project_structure
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.temp_dir:
            FileSystemTestUtils.cleanup_temp_directory(self.temp_dir)


class MockGitHubContext:
    """Context manager for mock GitHub API setup."""
    
    def __init__(self):
        self.mock_responses = {}
    
    def add_issue_response(self, issue_number: int, **kwargs):
        """Add a mock issue response."""
        response = MockResponseBuilder.github_issue_response(issue_number, **kwargs)
        self.mock_responses[f'issue_{issue_number}'] = response
    
    def add_repo_response(self, full_name: str):
        """Add a mock repository response."""
        response = MockResponseBuilder.github_repository_response(full_name)
        self.mock_responses['repository'] = response
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


# Convenience functions that combine multiple utilities

def create_test_epic(repo: Repository, title: str = "TEST: Sample Epic") -> Issue:
    """Create a complete test epic with proper structure."""
    body = TestDataFactory.create_epic_body(title)
    return GitHubTestUtils.create_test_issue(
        repo, title, body, ['type:epic', 'status:backlog']
    )


def create_test_task(repo: Repository, parent_epic_number: int, 
                    title: str = "TEST: Sample Task") -> Issue:
    """Create a complete test task with proper structure."""
    body = TestDataFactory.create_task_body(title, parent_epic_number)
    return GitHubTestUtils.create_test_issue(
        repo, title, body, ['type:task', 'status:backlog']
    )


def create_test_subtask(repo: Repository, parent_task_number: int,
                       title: str = "TEST: Sample Sub-task") -> Issue:
    """Create a complete test sub-task with proper structure."""
    body = TestDataFactory.create_subtask_body(title, parent_task_number)
    return GitHubTestUtils.create_test_issue(
        repo, title, body, ['type:subtask', 'status:backlog']
    )


def run_ghoo_command_and_verify(cli_runner, command: Union[str, List[str]], 
                               expect_success: bool = True,
                               expected_output: Optional[str] = None) -> Any:
    """Run a ghoo command and verify the result."""
    if isinstance(command, str):
        command = command.split()
    
    result = cli_runner.run(command)
    
    if expect_success:
        CliTestUtils.assert_command_success(result, expected_output)
    else:
        CliTestUtils.assert_command_error(result)
    
    return result


# Export commonly used utilities as module-level functions
parse_json_output = CliTestUtils.parse_json_output
parse_yaml_output = CliTestUtils.parse_yaml_output
assert_command_success = CliTestUtils.assert_command_success
assert_command_error = CliTestUtils.assert_command_error
assert_output_contains = CliTestUtils.assert_output_contains

create_issue_body = TestDataFactory.create_issue_body
create_ghoo_config = TestDataFactory.create_ghoo_config

verify_issue_exists = GitHubTestUtils.verify_issue_exists
verify_issue_has_label = GitHubTestUtils.verify_issue_has_label
verify_issue_body_contains = GitHubTestUtils.verify_issue_body_contains


# Legacy compatibility - import common patterns from existing helpers
try:
    from .helpers.github import *
except ImportError:
    pass  # Helpers may not exist yet

try:
    from .helpers.cli import *
except ImportError:
    pass  # Helpers may not exist yet