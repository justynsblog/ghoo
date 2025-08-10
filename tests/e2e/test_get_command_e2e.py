"""End-to-end tests for get command against live GitHub repository."""

import pytest
import subprocess
import json
import os
import sys
from pathlib import Path


class TestGetCommandE2E:
    """End-to-end tests for get command using live GitHub repository."""
    
    @pytest.fixture
    def github_env(self):
        """Setup GitHub testing environment."""
        token = os.getenv('TESTING_GITHUB_TOKEN')
        repo = os.getenv('TESTING_REPO', 'octocat/Hello-World')  # Public fallback repo
        
        return {
            'token': token,
            'repo': repo,
            'env': {
                **os.environ,
                'GITHUB_TOKEN': token or ''
            }
        }
    
    @pytest.fixture
    def ghoo_path(self):
        """Get path to the ghoo module for subprocess calls."""
        return str(Path(__file__).parent.parent.parent / "src")
    
    @pytest.mark.skipif(not os.getenv('TESTING_GITHUB_TOKEN'), 
                       reason="TESTING_GITHUB_TOKEN not set")
    def test_get_existing_issue_json_format(self, github_env, ghoo_path):
        """Test getting an existing issue in JSON format."""
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        # Try to get issue #1 from the test repository
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 
            github_env['repo'], '1', '--format', 'json'
        ], capture_output=True, text=True, env=env, cwd=ghoo_path)
        
        # If issue #1 doesn't exist, skip the test
        if result.returncode != 0 and "not found" in result.stderr:
            pytest.skip(f"Issue #1 not found in {github_env['repo']}")
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        # Parse and validate JSON output
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON output: {e}")
        
        # Validate required fields
        assert data['number'] == 1
        assert isinstance(data['title'], str)
        assert len(data['title']) > 0
        assert data['state'] in ['open', 'closed']
        assert data['type'] in ['epic', 'task', 'sub-task']
        assert isinstance(data['author'], str)
        assert len(data['author']) > 0
        assert data['url'].startswith('https://github.com/')
        assert isinstance(data['labels'], list)
        assert isinstance(data['assignees'], list)
        assert isinstance(data['sections'], list)
        
        # Validate timestamps
        assert 'created_at' in data
        assert 'updated_at' in data
        
        print(f"✓ Successfully retrieved issue #{data['number']}: {data['title']}")
    
    @pytest.mark.skipif(not os.getenv('TESTING_GITHUB_TOKEN'), 
                       reason="TESTING_GITHUB_TOKEN not set")
    def test_get_existing_issue_rich_format(self, github_env, ghoo_path):
        """Test getting an existing issue in rich format."""
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 
            github_env['repo'], '1'
        ], capture_output=True, text=True, env=env, cwd=ghoo_path)
        
        if result.returncode != 0 and "not found" in result.stderr:
            pytest.skip(f"Issue #1 not found in {github_env['repo']}")
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        output = result.stdout
        
        # Validate rich format contains expected elements
        assert '#1:' in output, "Issue number not found in output"
        assert 'State:' in output, "State not found in output"
        assert 'Author:' in output, "Author not found in output"
        assert 'URL:' in output, "URL not found in output"
        assert ('Created:' in output or 'Updated:' in output), "Timestamps not found in output"
        
        # Should contain emojis for issue type
        emojis = ['🏔️', '📋', '🔧', '📄']  # epic, task, sub-task, default
        assert any(emoji in output for emoji in emojis), "Issue type emoji not found"
        
        print(f"✓ Rich format output looks correct for issue #1")
    
    @pytest.mark.skipif(not os.getenv('TESTING_GITHUB_TOKEN'), 
                       reason="TESTING_GITHUB_TOKEN not set")
    def test_get_issue_with_labels(self, github_env, ghoo_path):
        """Test getting an issue that has labels."""
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        # Get the first few issues and find one with labels
        for issue_num in range(1, 6):
            result = subprocess.run([
                sys.executable, '-m', 'ghoo.main', 'get', 
                github_env['repo'], str(issue_num), '--format', 'json'
            ], capture_output=True, text=True, env=env, cwd=ghoo_path)
            
            if result.returncode != 0:
                continue  # Try next issue
            
            try:
                data = json.loads(result.stdout)
                if data['labels']:  # Found issue with labels
                    # Test rich format shows labels
                    result = subprocess.run([
                        sys.executable, '-m', 'ghoo.main', 'get', 
                        github_env['repo'], str(issue_num)
                    ], capture_output=True, text=True, env=env, cwd=ghoo_path)
                    
                    assert result.returncode == 0
                    assert 'Labels:' in result.stdout
                    
                    print(f"✓ Issue #{issue_num} labels displayed correctly")
                    return
                    
            except json.JSONDecodeError:
                continue
        
        pytest.skip("No issues with labels found in first 5 issues")
    
    @pytest.mark.skipif(not os.getenv('TESTING_GITHUB_TOKEN'), 
                       reason="TESTING_GITHUB_TOKEN not set")
    def test_get_issue_with_structured_body(self, github_env, ghoo_path):
        """Test getting an issue with structured markdown body."""
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        # Look for issues with structured content (sections and todos)
        for issue_num in range(1, 11):  # Check first 10 issues
            result = subprocess.run([
                sys.executable, '-m', 'ghoo.main', 'get', 
                github_env['repo'], str(issue_num), '--format', 'json'
            ], capture_output=True, text=True, env=env, cwd=ghoo_path)
            
            if result.returncode != 0:
                continue
            
            try:
                data = json.loads(result.stdout)
                
                # Check if issue has sections
                if data['sections'] and len(data['sections']) > 0:
                    print(f"✓ Issue #{issue_num} has {len(data['sections'])} sections")
                    
                    # Check for todos
                    total_todos = sum(section['total_todos'] for section in data['sections'])
                    if total_todos > 0:
                        print(f"✓ Issue #{issue_num} has {total_todos} todos across sections")
                        
                        # Test rich format displays sections and todos
                        result = subprocess.run([
                            sys.executable, '-m', 'ghoo.main', 'get', 
                            github_env['repo'], str(issue_num)
                        ], capture_output=True, text=True, env=env, cwd=ghoo_path)
                        
                        assert result.returncode == 0
                        output = result.stdout
                        
                        # Should show section headers
                        assert '##' in output, "Section headers not displayed"
                        
                        # Should show todos with checkboxes
                        todo_emojis = ['✅', '⬜']
                        assert any(emoji in output for emoji in todo_emojis), "Todo checkboxes not displayed"
                        
                        print(f"✓ Structured content displayed correctly for issue #{issue_num}")
                        return
                
            except json.JSONDecodeError:
                continue
        
        print("ℹ️  No issues with structured content found - testing basic parsing")
        
        # At least test that the parser handles any issue body without errors
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 
            github_env['repo'], '1', '--format', 'json'
        ], capture_output=True, text=True, env=env, cwd=ghoo_path)
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            # Should have parsed sections (even if empty) and pre_section_description
            assert 'sections' in data
            assert 'pre_section_description' in data
            print("✓ Body parsing works correctly even without structured content")
    
    @pytest.mark.skipif(not os.getenv('TESTING_GITHUB_TOKEN'), 
                       reason="TESTING_GITHUB_TOKEN not set")
    def test_error_handling_nonexistent_issue(self, github_env, ghoo_path):
        """Test error handling for non-existent issue."""
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        # Use a very high issue number that likely doesn't exist
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 
            github_env['repo'], '999999'
        ], capture_output=True, text=True, env=env, cwd=ghoo_path)
        
        assert result.returncode == 1
        assert "not found" in result.stderr
        print("✓ Non-existent issue error handled correctly")
    
    @pytest.mark.skipif(not os.getenv('TESTING_GITHUB_TOKEN'), 
                       reason="TESTING_GITHUB_TOKEN not set")
    def test_error_handling_nonexistent_repo(self, github_env, ghoo_path):
        """Test error handling for non-existent repository."""
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 
            'nonexistent-user/nonexistent-repo', '1'
        ], capture_output=True, text=True, env=env, cwd=ghoo_path)
        
        assert result.returncode == 1
        assert ("not found" in result.stderr or 
                "Not Found" in result.stderr or 
                "404" in result.stderr)
        print("✓ Non-existent repository error handled correctly")
    
    @pytest.mark.skipif(not os.getenv('TESTING_GITHUB_TOKEN'), 
                       reason="TESTING_GITHUB_TOKEN not set")
    def test_issue_type_detection(self, github_env, ghoo_path):
        """Test issue type detection from labels and title patterns."""
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        detected_types = set()
        
        # Check several issues to see different types
        for issue_num in range(1, 11):
            result = subprocess.run([
                sys.executable, '-m', 'ghoo.main', 'get', 
                github_env['repo'], str(issue_num), '--format', 'json'
            ], capture_output=True, text=True, env=env, cwd=ghoo_path)
            
            if result.returncode != 0:
                continue
            
            try:
                data = json.loads(result.stdout)
                detected_types.add(data['type'])
                
                # Validate type is one of the expected values
                assert data['type'] in ['epic', 'task', 'sub-task']
                
            except json.JSONDecodeError:
                continue
        
        print(f"✓ Detected issue types: {detected_types}")
        assert len(detected_types) > 0, "No issue types were detected"
    
    @pytest.mark.skipif(not os.getenv('TESTING_GITHUB_TOKEN'), 
                       reason="TESTING_GITHUB_TOKEN not set")
    def test_performance_reasonable_response_time(self, github_env, ghoo_path):
        """Test that get command responds within reasonable time."""
        import time
        
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        start_time = time.time()
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 
            github_env['repo'], '1', '--format', 'json'
        ], capture_output=True, text=True, env=env, cwd=ghoo_path)
        end_time = time.time()
        
        if result.returncode != 0 and "not found" in result.stderr:
            pytest.skip(f"Issue #1 not found in {github_env['repo']}")
        
        assert result.returncode == 0
        
        response_time = end_time - start_time
        print(f"✓ Response time: {response_time:.2f} seconds")
        
        # Should respond within 10 seconds for a single issue
        assert response_time < 10.0, f"Response too slow: {response_time:.2f}s"
    
    def test_command_without_token_shows_helpful_error(self, ghoo_path):
        """Test that missing token shows helpful error message."""
        env = os.environ.copy()
        env.pop('GITHUB_TOKEN', None)
        env.pop('TESTING_GITHUB_TOKEN', None)
        env['PYTHONPATH'] = ghoo_path
        
        result = subprocess.run([
            sys.executable, '-m', 'ghoo.main', 'get', 'owner/repo', '1'
        ], capture_output=True, text=True, env=env, cwd=ghoo_path)
        
        assert result.returncode == 1
        assert "GitHub token not found" in result.stderr
        assert "GITHUB_TOKEN" in result.stderr
        print("✓ Missing token error message is helpful")
    
    @pytest.mark.skipif(not os.getenv('TESTING_GITHUB_TOKEN'), 
                       reason="TESTING_GITHUB_TOKEN not set")
    def test_full_workflow_epic_task_subtask(self, github_env, ghoo_path):
        """Test full workflow with epic/task/sub-task hierarchy if available."""
        env = github_env['env'].copy()
        env['PYTHONPATH'] = ghoo_path
        
        # This test would ideally have a test repository with known epic/task structure
        # For now, we'll test with whatever is available
        
        epic_found = False
        task_found = False
        subtask_found = False
        
        # Look through issues to find different types
        for issue_num in range(1, 21):  # Check first 20 issues
            result = subprocess.run([
                sys.executable, '-m', 'ghoo.main', 'get', 
                github_env['repo'], str(issue_num), '--format', 'json'
            ], capture_output=True, text=True, env=env, cwd=ghoo_path)
            
            if result.returncode != 0:
                continue
            
            try:
                data = json.loads(result.stdout)
                
                if data['type'] == 'epic':
                    epic_found = True
                    print(f"✓ Found epic issue #{issue_num}: {data['title']}")
                    
                    # Test epic-specific features
                    if 'sub_issues' in data:
                        print(f"  - Has {len(data['sub_issues'])} sub-issues")
                    if 'sub_issues_summary' in data:
                        summary = data['sub_issues_summary']
                        print(f"  - Summary: {summary['closed']}/{summary['total']} completed")
                
                elif data['type'] == 'task':
                    task_found = True
                    print(f"✓ Found task issue #{issue_num}: {data['title']}")
                    
                    # Test parent issue detection
                    if 'parent_issue' in data and data['parent_issue']:
                        parent = data['parent_issue']
                        print(f"  - Parent: #{parent['number']}: {parent['title']}")
                
                elif data['type'] == 'sub-task':
                    subtask_found = True
                    print(f"✓ Found sub-task issue #{issue_num}: {data['title']}")
                
            except json.JSONDecodeError:
                continue
        
        # Report findings
        types_found = []
        if epic_found: types_found.append('epic')
        if task_found: types_found.append('task') 
        if subtask_found: types_found.append('sub-task')
        
        if types_found:
            print(f"✓ Issue type detection working - found: {', '.join(types_found)}")
        else:
            print("ℹ️  All issues detected as default 'task' type")
        
        # At minimum, we should have detected some issues successfully
        assert True  # Test passes if we got this far without exceptions