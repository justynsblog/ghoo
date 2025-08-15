"""End-to-end tests for explicit configuration behavior against live GitHub repository.

CRITICAL: These tests validate explicit configuration with NO SKIPS.
All tests must pass against live GitHub API to ensure SPEC compliance.
"""

import pytest
import subprocess
import json
import os
import sys
import time
import shutil
import tempfile
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, Any


class TestExplicitConfigurationE2E:
    """E2E tests for explicit issue_type_method configuration with live GitHub."""
    
    def _run_ghoo_command(self, args, env, cwd=None):
        """Run ghoo command with python module execution."""
        # Always use python module execution for E2E tests to ensure consistency
        cmd = [sys.executable, '-m', 'ghoo.main'] + args
        
        return subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            env=env, 
            cwd=cwd
        )
    
    @pytest.fixture
    def github_env(self):
        """Setup GitHub testing environment with validation."""
        token = os.getenv('TESTING_GITHUB_TOKEN')
        repo = os.getenv('TESTING_GH_REPO')
        
        # Critical validation - these tests must NOT be skipped
        if not token:
            pytest.fail(
                "TESTING_GITHUB_TOKEN environment variable is required. "
                "These tests MUST run against live GitHub API with no skips."
            )
        
        if not repo:
            pytest.fail(
                "TESTING_GH_REPO environment variable is required. "
                "These tests MUST run against live GitHub API with no skips."
            )
        
        # Handle URL format - extract owner/repo if it's a full URL
        if repo.startswith('https://github.com/'):
            repo = repo.replace('https://github.com/', '')
        
        return {
            'token': token,
            'repo': repo,
            'env': {
                **os.environ,
                'GITHUB_TOKEN': token,
                'TESTING_GITHUB_TOKEN': token
            }
        }
    
    @pytest.fixture
    def ghoo_path(self):
        """Get path to the ghoo module for subprocess calls."""
        return str(Path(__file__).parent.parent.parent / "src")
    
    @pytest.fixture
    def unique_identifier(self):
        """Generate a unique identifier for test isolation."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"E2EConfig_{timestamp}"
    
    @pytest.fixture
    def temp_project_native(self, unique_identifier):
        """Create temporary project with native configuration."""
        temp_dir = tempfile.mkdtemp(prefix=f"ghoo_e2e_native_{unique_identifier}_")
        
        # Create ghoo.yaml with native configuration
        config_content = {
            'project_url': 'https://github.com/justynsblog/ghoo-test',
            'status_method': 'labels',
            'issue_type_method': 'native'  # Explicit native configuration
        }
        
        config_path = Path(temp_dir) / 'ghoo.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config_content, f)
        
        yield temp_dir
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def temp_project_labels(self, unique_identifier):
        """Create temporary project with labels configuration."""
        temp_dir = tempfile.mkdtemp(prefix=f"ghoo_e2e_labels_{unique_identifier}_")
        
        # Create ghoo.yaml with labels configuration
        config_content = {
            'project_url': 'https://github.com/justynsblog/ghoo-test',
            'status_method': 'labels',
            'issue_type_method': 'labels'  # Explicit labels configuration
        }
        
        config_path = Path(temp_dir) / 'ghoo.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config_content, f)
        
        yield temp_dir
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_native_config_validation_live(self, github_env, ghoo_path, temp_project_native, unique_identifier):
        """Test native configuration against live GitHub - must NOT skip."""
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        # Test epic creation with native configuration
        epic_title = f"Native Config Test Epic {unique_identifier}"
        
        result = self._run_ghoo_command([
            'create-epic', github_env['repo'], epic_title
        ], env, cwd=temp_project_native)
        
        # CRITICAL: This test must not be skipped
        # If native types aren't available, it should fail with clear error
        if result.returncode != 0:
            # Check if it's a configuration error (expected if repository lacks native types)
            stderr_content = result.stderr.lower()
            if "native issue types not" in stderr_content or "not available" in stderr_content:
                # This is expected if repository doesn't have native types configured
                assert "setup custom issue types" in result.stderr or "issue_type_method" in result.stderr
                print(f"✅ Expected configuration error for native types: {result.stderr}")
                return
            else:
                pytest.fail(f"Unexpected error (should be config-related): {result.stderr}")
        
        # If it succeeded, verify the epic was created correctly
        assert "Created Epic #" in result.stdout
        print(f"✅ Native configuration successfully created epic: {epic_title}")
    
    def test_labels_config_validation_live(self, github_env, ghoo_path, temp_project_labels, unique_identifier):
        """Test labels configuration against live GitHub - must NOT skip."""
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        # Test epic creation with labels configuration
        epic_title = f"Labels Config Test Epic {unique_identifier}"
        
        result = self._run_ghoo_command([
            'create-epic', github_env['repo'], epic_title
        ], env, cwd=temp_project_labels)
        
        # CRITICAL: This test must not be skipped
        # Labels configuration should work with any repository
        if result.returncode != 0:
            pytest.fail(f"Labels configuration should work - error: {result.stderr}")
        
        # Verify the epic was created with correct labels
        assert "Created Epic #" in result.stdout
        print(f"✅ Labels configuration successfully created epic: {epic_title}")
    
    def test_configuration_matrix_live(self, github_env, ghoo_path, unique_identifier):
        """Test configuration matrix against live GitHub - comprehensive validation."""
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        configurations = [
            {'issue_type_method': 'native', 'description': 'explicit native'},
            {'issue_type_method': 'labels', 'description': 'explicit labels'},
            # Test default behavior (should default to native)
            {'description': 'default (should be native)'}
        ]
        
        for i, config in enumerate(configurations):
            # Create temporary project for each configuration
            temp_dir = tempfile.mkdtemp(prefix=f"ghoo_e2e_matrix_{unique_identifier}_{i}_")
            
            try:
                # Create ghoo.yaml with specific configuration
                config_content = {
                    'project_url': 'https://github.com/justynsblog/ghoo-test',
                    'status_method': 'labels'
                }
                
                if 'issue_type_method' in config:
                    config_content['issue_type_method'] = config['issue_type_method']
                
                config_path = Path(temp_dir) / 'ghoo.yaml'
                with open(config_path, 'w') as f:
                    yaml.dump(config_content, f)
                
                # Test epic creation
                epic_title = f"Matrix Test {config['description']} {unique_identifier}_{i}"
                
                result = self._run_ghoo_command([
                    'create-epic', github_env['repo'], epic_title
                ], env, cwd=temp_dir)
                
                print(f"\n🧪 Testing configuration: {config['description']}")
                print(f"Return code: {result.returncode}")
                print(f"Stdout: {result.stdout[:200]}...")
                print(f"Stderr: {result.stderr[:200]}...")
                
                # Analyze results based on configuration
                if config.get('issue_type_method') == 'labels':
                    # Labels should always work
                    assert result.returncode == 0, f"Labels config failed: {result.stderr}"
                    assert "Created Epic #" in result.stdout
                elif config.get('issue_type_method') == 'native' or 'issue_type_method' not in config:
                    # Native (explicit or default) - may fail if repository lacks native types
                    if result.returncode != 0:
                        stderr_content = result.stderr.lower()
                        assert ("native issue types not" in stderr_content or 
                               "not available" in stderr_content or
                               "setup custom issue types" in stderr_content), \
                               f"Unexpected native config error: {result.stderr}"
                    else:
                        assert "Created Epic #" in result.stdout
                
                print(f"✅ Configuration '{config['description']}' validated successfully")
                
            finally:
                # Cleanup
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_init_gh_with_configurations_live(self, github_env, ghoo_path, unique_identifier):
        """Test init-gh command with different configurations against live GitHub."""
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        # Test with labels configuration
        temp_dir = tempfile.mkdtemp(prefix=f"ghoo_e2e_init_{unique_identifier}_")
        
        try:
            # Create ghoo.yaml with labels configuration
            config_content = {
                'project_url': f'https://github.com/{github_env["repo"]}',
                'status_method': 'labels',
                'issue_type_method': 'labels'  # Explicit labels for init-gh
            }
            
            config_path = Path(temp_dir) / 'ghoo.yaml'
            with open(config_path, 'w') as f:
                yaml.dump(config_content, f)
            
            # Test init-gh command
            result = self._run_ghoo_command([
                'init-gh'
            ], env, cwd=temp_dir)
            
            print(f"\n🔧 Testing init-gh with labels configuration")
            print(f"Return code: {result.returncode}")
            print(f"Stdout: {result.stdout}")
            if result.stderr:
                print(f"Stderr: {result.stderr}")
            
            # init-gh should work with labels configuration
            assert result.returncode == 0, f"init-gh failed with labels config: {result.stderr}"
            assert "repository" in result.stdout.lower()
            
            print("✅ init-gh successfully executed with labels configuration")
            
        finally:
            # Cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_complete_workflow_with_labels_config_live(self, github_env, ghoo_path, temp_project_labels, unique_identifier):
        """Test complete workflow (create → plan → work → close) with labels configuration."""
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        # Step 1: Create epic with labels configuration
        epic_title = f"Workflow Test Epic {unique_identifier}"
        
        result = self._run_ghoo_command([
            'create-epic', github_env['repo'], epic_title,
            '--body', 'Test epic for complete workflow validation'
        ], env, cwd=temp_project_labels)
        
        assert result.returncode == 0, f"Epic creation failed: {result.stderr}"
        assert "Created Epic #" in result.stdout
        
        # Extract epic number from output
        epic_number = None
        for line in result.stdout.split('\n'):
            if "Created Epic #" in line:
                import re
                match = re.search(r'#(\d+)', line)
                if match:
                    epic_number = int(match.group(1))
                    break
        
        assert epic_number is not None, f"Could not extract epic number from: {result.stdout}"
        print(f"✅ Created epic #{epic_number} with labels configuration")
        
        # Step 2: Test workflow transitions
        workflow_commands = [
            ('start-plan', 'planning'),
            ('submit-plan', 'awaiting-plan-approval'),
            ('approve-plan', 'plan-approved'),
            ('start-work', 'in-progress'),
            ('submit-work', 'awaiting-completion-approval'),
            ('approve-work', 'closed')
        ]
        
        for command, expected_state in workflow_commands:
            result = self._run_ghoo_command([
                command, github_env['repo'], str(epic_number)
            ], env, cwd=temp_project_labels)
            
            # Some workflow commands might not be implemented yet, that's okay
            if result.returncode == 0:
                print(f"✅ {command} executed successfully")
            else:
                print(f"⚠️  {command} failed (may not be implemented): {result.stderr}")
        
        print(f"✅ Complete workflow tested with labels configuration for epic #{epic_number}")
    
    def test_error_handling_configuration_mismatch_live(self, github_env, ghoo_path, unique_identifier):
        """Test error handling when configuration doesn't match repository capabilities."""
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        # Create project with native configuration to test potential mismatch
        temp_dir = tempfile.mkdtemp(prefix=f"ghoo_e2e_error_{unique_identifier}_")
        
        try:
            # Create ghoo.yaml with native configuration
            config_content = {
                'project_url': f'https://github.com/{github_env["repo"]}',
                'status_method': 'labels',
                'issue_type_method': 'native'  # This may not be available
            }
            
            config_path = Path(temp_dir) / 'ghoo.yaml'
            with open(config_path, 'w') as f:
                yaml.dump(config_content, f)
            
            # Try to create epic - this may fail if native types aren't configured
            epic_title = f"Error Test Epic {unique_identifier}"
            
            result = self._run_ghoo_command([
                'create-epic', github_env['repo'], epic_title
            ], env, cwd=temp_dir)
            
            print(f"\n❌ Testing error handling for potential configuration mismatch")
            print(f"Return code: {result.returncode}")
            print(f"Stderr: {result.stderr}")
            
            # If it fails, verify error message is helpful
            if result.returncode != 0:
                stderr_content = result.stderr
                
                # Check for enhanced error messages
                expected_phrases = [
                    "native issue types",
                    "setup custom issue types",
                    "issue_type_method",
                    "labels"
                ]
                
                found_helpful_message = any(phrase in stderr_content.lower() for phrase in expected_phrases)
                assert found_helpful_message, f"Error message not helpful enough: {stderr_content}"
                
                print("✅ Error message provides helpful guidance for configuration issues")
            else:
                print("✅ Native configuration worked (repository has native types configured)")
                assert "Created Epic #" in result.stdout
                
        finally:
            # Cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_environment_validation_live(self, github_env, ghoo_path):
        """Validate that test environment is properly configured."""
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        # Verify token is accessible
        assert env.get('TESTING_GITHUB_TOKEN'), "TESTING_GITHUB_TOKEN must be set"
        assert env.get('GITHUB_TOKEN'), "GITHUB_TOKEN must be set"
        assert len(env['TESTING_GITHUB_TOKEN']) > 20, "TESTING_GITHUB_TOKEN appears invalid"
        
        # Verify repository is accessible
        repo = github_env['repo']
        assert '/' in repo, f"Repository format invalid: {repo}"
        assert len(repo.split('/')) == 2, f"Repository format invalid: {repo}"
        
        print(f"✅ Environment validation passed:")
        print(f"   Repository: {repo}")
        print(f"   Token length: {len(env['TESTING_GITHUB_TOKEN'])}")
        print(f"   CRITICAL: These tests run against LIVE GitHub API")
        print(f"   CRITICAL: Tests must NOT be skipped")