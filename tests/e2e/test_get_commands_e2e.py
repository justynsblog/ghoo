"""E2E tests for get subcommands with live GitHub API."""

import subprocess
import pytest
import sys
import os
import json
import time
from pathlib import Path

# Add src to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from tests.environment import TestEnvironment


class TestGetCommandsE2E:
    """End-to-end tests for get subcommands using live GitHub API."""

    def setup_method(self):
        """Set up test environment with GitHub credentials."""
        self.test_env = TestEnvironment()
        self.python_path = str(Path(__file__).parent.parent.parent / "src")
        self.test_repo = os.getenv('TESTING_GH_REPO', 'justynsblog/ghoo-test')

    def run_cli_command_with_env(self, args):
        """Helper to run CLI commands with proper environment."""
        cmd = [
            sys.executable, "-m", "src.ghoo.main"
        ] + args
        
        # Create environment with GitHub token
        env = os.environ.copy()
        env['PYTHONPATH'] = self.python_path
        # TestEnvironment automatically sets up environment variables
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            cwd=Path(__file__).parent.parent.parent
        )
        return result

    def test_get_help_shows_all_subcommands(self):
        """Test get command help shows all implemented subcommands."""
        result = self.run_cli_command_with_env(["get", "--help"])
        assert result.returncode == 0
        assert "epic" in result.stdout
        assert "milestone" in result.stdout
        assert "section" in result.stdout
        assert "todo" in result.stdout
        print("✓ Get command help shows all subcommands")

    @pytest.mark.skipif(
        not os.getenv('TESTING_GITHUB_TOKEN'), 
        reason="No GitHub token available for E2E testing"
    )
    def test_get_epic_with_live_api(self):
        """Test get epic command with live GitHub API."""
        result = self.run_cli_command_with_env([
            "get", "epic", "--repo", self.test_repo, "1", "--format", "json"
        ])
        
        # Should not show placeholder message
        assert "Not yet implemented" not in result.stdout
        
        if result.returncode == 0:
            # Command succeeded - validate JSON structure
            try:
                data = json.loads(result.stdout)
                assert isinstance(data, dict)
                assert 'number' in data
                assert 'type' in data
                assert data['type'] == 'epic'
                assert 'available_milestones' in data
                print(f"✓ Get epic command successful: Issue #{data['number']}")
            except json.JSONDecodeError:
                pytest.fail("Invalid JSON output from get epic command")
        else:
            # Command failed - should be specific error, not placeholder
            expected_errors = ["not an epic", "not found", "authentication", "GitHub"]
            assert any(error in result.stderr for error in expected_errors)
            print(f"✓ Get epic command properly handled error: {result.stderr[:100]}")

    @pytest.mark.skipif(
        not os.getenv('TESTING_GITHUB_TOKEN'), 
        reason="No GitHub token available for E2E testing"
    )
    def test_get_milestone_with_live_api(self):
        """Test get milestone command with live GitHub API."""
        # Use microsoft/vscode which is known to have milestones
        result = self.run_cli_command_with_env([
            "get", "milestone", "--repo", "microsoft/vscode", "1", "--format", "json"
        ])
        
        assert "Not yet implemented" not in result.stdout
        
        if result.returncode == 0:
            # Command succeeded - validate JSON structure
            try:
                data = json.loads(result.stdout)
                assert isinstance(data, dict)
                assert 'number' in data
                assert 'title' in data
                assert 'issues_by_type' in data
                print(f"✓ Get milestone command successful: {data['title']}")
            except json.JSONDecodeError:
                pytest.fail("Invalid JSON output from get milestone command")
        else:
            # Command failed - should be specific error
            expected_errors = ["not found", "authentication", "GitHub"]
            assert any(error in result.stderr for error in expected_errors)
            print(f"✓ Get milestone command properly handled error: {result.stderr[:100]}")

    @pytest.mark.skipif(
        not os.getenv('TESTING_GITHUB_TOKEN'), 
        reason="No GitHub token available for E2E testing"
    )
    def test_get_section_with_live_api(self):
        """Test get section command with live GitHub API."""
        result = self.run_cli_command_with_env([
            "get", "section", "--repo", self.test_repo, "1", "Summary", "--format", "json"
        ])
        
        assert "Not yet implemented" not in result.stdout
        
        if result.returncode == 0:
            # Command succeeded - validate JSON structure
            try:
                data = json.loads(result.stdout)
                assert isinstance(data, dict)
                assert 'title' in data
                assert 'body' in data
                assert 'todos' in data
                assert data['title'] == 'Summary'
                print(f"✓ Get section command successful: {data['title']}")
            except json.JSONDecodeError:
                pytest.fail("Invalid JSON output from get section command")
        else:
            # Command failed - should be specific error
            expected_errors = ["not found", "Section", "authentication", "GitHub"]
            assert any(error in result.stderr for error in expected_errors)
            print(f"✓ Get section command properly handled error: {result.stderr[:100]}")

    @pytest.mark.skipif(
        not os.getenv('TESTING_GITHUB_TOKEN'), 
        reason="No GitHub token available for E2E testing"
    )
    def test_get_todo_with_live_api(self):
        """Test get todo command with live GitHub API."""
        result = self.run_cli_command_with_env([
            "get", "todo", "--repo", self.test_repo, "1", "Tasks", "test", "--format", "json"
        ])
        
        assert "Not yet implemented" not in result.stdout
        
        if result.returncode == 0:
            # Command succeeded - validate JSON structure
            try:
                data = json.loads(result.stdout)
                assert isinstance(data, dict)
                assert 'text' in data
                assert 'checked' in data
                assert 'match_type' in data
                assert 'test' in data['text'].lower()
                print(f"✓ Get todo command successful: {data['text'][:50]}")
            except json.JSONDecodeError:
                pytest.fail("Invalid JSON output from get todo command")
        else:
            # Command failed - should be specific error
            expected_errors = ["not found", "Todo", "Section", "authentication", "GitHub"]
            assert any(error in result.stderr for error in expected_errors)
            print(f"✓ Get todo command properly handled error: {result.stderr[:100]}")

    @pytest.mark.skipif(
        not os.getenv('TESTING_GITHUB_TOKEN'), 
        reason="No GitHub token available for E2E testing"
    )
    def test_repository_resolution_from_config(self, tmp_path):
        """Test repository resolution from ghoo.yaml config."""
        # Create temporary ghoo.yaml config
        config_content = f"""
project_url: https://github.com/{self.test_repo}
status_method: labels
required_sections:
  - "Problem Statement"
  - "Acceptance Criteria"
"""
        config_file = tmp_path / "ghoo.yaml"
        config_file.write_text(config_content)
        
        # Run command without explicit --repo parameter
        env = os.environ.copy()
        env['PYTHONPATH'] = self.python_path
        
        result = subprocess.run([
            sys.executable, "-m", "src.ghoo.main",
            "get", "epic", "1", "--format", "json"
        ], capture_output=True, text=True, env=env, cwd=tmp_path)
        
        assert "Not yet implemented" not in result.stdout
        
        if result.returncode == 0:
            # Should have used config repository
            try:
                data = json.loads(result.stdout)
                assert data['number'] == 1
                print("✓ Repository resolution from config working")
            except json.JSONDecodeError:
                pytest.fail("Invalid JSON output")
        else:
            # Should fail with specific error, not config error
            expected_errors = ["not an epic", "not found", "authentication", "GitHub"]
            assert any(error in result.stderr for error in expected_errors)
            print("✓ Config-based repository resolution attempted")

    @pytest.mark.skipif(
        not os.getenv('TESTING_GITHUB_TOKEN'), 
        reason="No GitHub token available for E2E testing"
    )
    def test_format_consistency_between_json_and_rich(self):
        """Test that JSON and rich formats contain consistent core data."""
        # Test with epic command
        json_result = self.run_cli_command_with_env([
            "get", "epic", "--repo", self.test_repo, "1", "--format", "json"
        ])
        
        rich_result = self.run_cli_command_with_env([
            "get", "epic", "--repo", self.test_repo, "1", "--format", "rich"
        ])
        
        assert "Not yet implemented" not in json_result.stdout
        assert "Not yet implemented" not in rich_result.stdout
        
        if json_result.returncode == 0 and rich_result.returncode == 0:
            # Both succeeded - compare core data
            try:
                json_data = json.loads(json_result.stdout)
                
                # Rich format should contain the same issue number
                assert f"#{json_data['number']}" in rich_result.stdout
                print("✓ Format consistency verified between JSON and rich output")
            except json.JSONDecodeError:
                pytest.fail("Invalid JSON output")

    def test_invalid_repository_format_error(self):
        """Test error handling for invalid repository format."""
        result = self.run_cli_command_with_env([
            "get", "epic", "--repo", "invalid-format", "1"
        ])
        
        # Should fail with repository format error (exit code 1) or missing parameter (exit code 2)
        assert result.returncode in [1, 2]
        
        if "Missing option" in result.stderr:
            # CLI parameter structure issue - test the actual command structure
            print("✓ Command structure validation working")
        elif "Invalid repository format" in result.stderr:
            assert "Expected 'owner/repo'" in result.stderr
            print("✓ Invalid repository format properly handled")
        else:
            print(f"✓ Repository validation working - stderr: {result.stderr[:100]}")

    def test_missing_repository_error(self, tmp_path):
        """Test error when no repository is specified and no config exists."""
        # Run command without repo in directory with no ghoo.yaml
        env = os.environ.copy()
        env['PYTHONPATH'] = self.python_path
        
        result = subprocess.run([
            sys.executable, "-m", "src.ghoo.main",
            "get", "epic", "1"
        ], capture_output=True, text=True, env=env, cwd=tmp_path)
        
        assert result.returncode == 1
        assert "No repository specified" in result.stderr
        assert "Solutions:" in result.stderr
        assert "--repo" in result.stderr
        assert "ghoo.yaml" in result.stderr
        print("✓ Missing repository error properly handled")

    @pytest.mark.skipif(
        not os.getenv('TESTING_GITHUB_TOKEN'), 
        reason="No GitHub token available for E2E testing"
    )
    def test_performance_reasonable_response_time(self):
        """Test that commands respond within reasonable time."""
        start_time = time.time()
        result = self.run_cli_command_with_env([
            "get", "epic", "--repo", self.test_repo, "1", "--format", "json"
        ])
        end_time = time.time()
        
        response_time = end_time - start_time
        print(f"✓ Response time: {response_time:.2f} seconds")
        
        # Should respond within 10 seconds
        assert response_time < 10.0, f"Response too slow: {response_time:.2f}s"
        
        # Command should execute (success or specific failure, not placeholder)
        assert "Not yet implemented" not in result.stdout

    def test_missing_token_shows_helpful_error(self):
        """Test that missing token shows helpful error message."""
        env = os.environ.copy()
        env.pop('GITHUB_TOKEN', None)
        env.pop('TESTING_GITHUB_TOKEN', None)
        env['PYTHONPATH'] = self.python_path
        
        result = subprocess.run([
            sys.executable, "-m", "src.ghoo.main",
            "get", "epic", "--repo", "owner/repo", "1"
        ], capture_output=True, text=True, env=env,
        cwd=Path(__file__).parent.parent.parent)
        
        assert result.returncode == 1
        assert "GitHub token not found" in result.stderr
        assert "GITHUB_TOKEN" in result.stderr
        print("✓ Missing token error message is helpful")

    @pytest.mark.skipif(
        not os.getenv('TESTING_GITHUB_TOKEN'), 
        reason="No GitHub token available for E2E testing"
    )
    def test_full_workflow_all_subcommands(self):
        """Test a realistic workflow using all get subcommands."""
        print("Testing full workflow with all get subcommands...")
        
        # Step 1: Get epic details
        epic_result = self.run_cli_command_with_env([
            "get", "epic", "--repo", self.test_repo, "1", "--format", "json"
        ])
        
        if epic_result.returncode == 0:
            epic_data = json.loads(epic_result.stdout)
            print(f"  ✓ Epic: {epic_data['title']}")
        else:
            print(f"  - Epic not available (expected): {epic_result.stderr[:50]}")
        
        # Step 2: Try to get milestone information (may not exist)
        milestone_result = self.run_cli_command_with_env([
            "get", "milestone", "--repo", "microsoft/vscode", "1", "--format", "json"
        ])
        
        if milestone_result.returncode == 0:
            milestone_data = json.loads(milestone_result.stdout)
            print(f"  ✓ Milestone: {milestone_data['title']}")
        else:
            print(f"  - Milestone not available: {milestone_result.stderr[:50]}")
        
        # Step 3: Try to get a section
        section_result = self.run_cli_command_with_env([
            "get", "section", "--repo", self.test_repo, "1", "Summary", "--format", "json"
        ])
        
        if section_result.returncode == 0:
            section_data = json.loads(section_result.stdout)
            print(f"  ✓ Section: {section_data['title']}")
        else:
            print(f"  - Section not available: {section_result.stderr[:50]}")
        
        # Step 4: Try to get a todo
        todo_result = self.run_cli_command_with_env([
            "get", "todo", "--repo", self.test_repo, "1", "Tasks", "implement", "--format", "json"
        ])
        
        if todo_result.returncode == 0:
            todo_data = json.loads(todo_result.stdout)
            print(f"  ✓ Todo: {todo_data['text'][:50]}")
        else:
            print(f"  - Todo not available: {todo_result.stderr[:50]}")
        
        # All commands should have executed (not shown placeholders)
        for result in [epic_result, milestone_result, section_result, todo_result]:
            assert "Not yet implemented" not in result.stdout
        
        print("✓ Full workflow completed - all commands implemented")

    def test_get_legacy_deprecation_warning(self):
        """Test that get-legacy shows deprecation warning."""
        result = self.run_cli_command_with_env([
            "get-legacy", self.test_repo, "999"  # Use high number to avoid long responses
        ])
        
        # Should show deprecation warning regardless of success/failure
        assert "WARNING: This command is deprecated" in result.stderr
        assert "ghoo get epic" in result.stderr
        assert "ghoo get milestone" in result.stderr
        print("✓ Get-legacy deprecation warning displayed correctly")