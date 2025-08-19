"""Comprehensive test to ensure ALL commands have proper --repo argument coverage.

This test module automatically discovers all CLI commands and verifies that they
properly handle the --repo argument and config fallback behavior. It's designed
to catch any future commands that don't follow the required pattern.
"""

import pytest
import inspect
import importlib
from pathlib import Path
import sys
from typing import Optional, get_type_hints
import ast

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ghoo.main import app as main_app
from ghoo.commands.get_commands import get_app


class TestComprehensiveRepoeCoverage:
    """Comprehensive tests for --repo argument coverage across all commands."""
    
    def test_all_typer_commands_have_repo_parameter(self):
        """Automatically discover and test ALL Typer commands for --repo parameter."""
        
        # Get all commands from both apps
        main_commands = self._get_all_typer_commands(main_app)
        get_commands = self._get_all_typer_commands(get_app)
        
        all_commands = {**main_commands, **get_commands}
        
        # Commands that legitimately don't need --repo (very few exceptions)
        exempt_commands = {
            'version',  # Version command doesn't need repo
            'display_audit_trail_info',  # Internal helper function
            'init_gh',  # Uses config file directly, doesn't need --repo parameter
        }
        
        # Filter out exempt commands
        commands_to_test = {name: cmd for name, cmd in all_commands.items() 
                           if name not in exempt_commands}
        
        assert len(commands_to_test) > 20, f"Expected many commands, but only found {len(commands_to_test)}"
        
        failing_commands = []
        
        for cmd_name, cmd_func in commands_to_test.items():
            try:
                sig = inspect.signature(cmd_func)
                params = list(sig.parameters.items())
                
                # Every command should have 'repo' parameter
                repo_param = None
                for param_name, param in params:
                    if param_name == 'repo':
                        repo_param = param
                        break
                
                if repo_param is None:
                    failing_commands.append(f"{cmd_name}: Missing 'repo' parameter")
                    continue
                
                # repo parameter should be Optional
                if repo_param.default is inspect.Parameter.empty:
                    failing_commands.append(f"{cmd_name}: 'repo' parameter should be optional with default value")
                    continue
                    
                # Check type annotation if available
                try:
                    annotations = get_type_hints(cmd_func)
                    if 'repo' in annotations:
                        repo_type = annotations['repo']
                        # Should be Optional[str] or Union[str, None]
                        if not (hasattr(repo_type, '__origin__') and 
                               (repo_type.__origin__ is type(Optional[str]).__origin__)):
                            failing_commands.append(f"{cmd_name}: 'repo' should be Optional[str] type")
                except:
                    # Type hints might not be available, skip this check
                    pass
                    
            except Exception as e:
                failing_commands.append(f"{cmd_name}: Error inspecting signature - {e}")
        
        if failing_commands:
            failure_msg = "Commands failing --repo parameter requirements:\n" + "\n".join(failing_commands)
            pytest.fail(failure_msg)
    
    def test_all_command_files_use_resolve_repository(self):
        """Test that all command implementations use resolve_repository function."""
        
        command_files = [
            Path(__file__).parent.parent.parent / "src" / "ghoo" / "main.py",
            Path(__file__).parent.parent.parent / "src" / "ghoo" / "commands" / "get_commands.py",
        ]
        
        failing_files = []
        
        for file_path in command_files:
            if not file_path.exists():
                continue
                
            content = file_path.read_text()
            
            # Parse the AST to find function definitions
            try:
                tree = ast.parse(content)
                
                # Find all function definitions that are CLI commands
                command_functions = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Skip helper functions
                        if node.name.startswith('_') or node.name in ['main', 'display_audit_trail_info', 'version']:
                            continue
                        command_functions.append(node.name)
                
                # For each command function, check if it uses resolve_repository
                for func_name in command_functions:
                    # Look for resolve_repository call in the function
                    if f"resolve_repository(" not in content:
                        # Check if this is a command that should have it
                        if f"def {func_name}(" in content and "repo:" in content:
                            # This function has repo parameter but doesn't call resolve_repository
                            func_start = content.find(f"def {func_name}(")
                            if func_start != -1:
                                # Look for the next function or end of file
                                next_func = content.find("\ndef ", func_start + 1)
                                func_content = content[func_start:next_func] if next_func != -1 else content[func_start:]
                                
                                if "repo:" in func_content and "resolve_repository(" not in func_content:
                                    failing_files.append(f"{file_path.name}:{func_name} - Has repo parameter but doesn't call resolve_repository()")
                            
            except SyntaxError as e:
                failing_files.append(f"{file_path.name}: Syntax error - {e}")
        
        if failing_files:
            failure_msg = "Files/functions not using resolve_repository:\n" + "\n".join(failing_files)
            pytest.fail(failure_msg)
    
    def test_no_positional_repo_arguments_exist(self):
        """Ensure no command uses positional repo arguments."""
        
        command_files = [
            Path(__file__).parent.parent.parent / "src" / "ghoo" / "main.py",
            Path(__file__).parent.parent.parent / "src" / "ghoo" / "commands" / "get_commands.py",
        ]
        
        failing_patterns = []
        
        for file_path in command_files:
            if not file_path.exists():
                continue
                
            content = file_path.read_text()
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                # Look for problematic patterns
                if "repo: str = typer.Argument(" in line:
                    failing_patterns.append(f"{file_path.name}:{line_num} - Uses positional repo: {line.strip()}")
                
                # Check for old-style validation patterns
                if "if '/' not in repo or len(repo.split('/')) != 2:" in line:
                    # This should be replaced with resolve_repository call
                    context_lines = lines[max(0, line_num-5):line_num+2]
                    context = '\n'.join(context_lines)
                    if "resolve_repository(" not in context:
                        failing_patterns.append(f"{file_path.name}:{line_num} - Manual repo validation instead of resolve_repository()")
        
        if failing_patterns:
            failure_msg = "Found positional repo or manual validation patterns:\n" + "\n".join(failing_patterns)
            pytest.fail(failure_msg)
    
    def test_config_loader_pattern_consistency(self):
        """Test that all commands use consistent config loader initialization."""
        
        command_files = [
            Path(__file__).parent.parent.parent / "src" / "ghoo" / "main.py",
            Path(__file__).parent.parent.parent / "src" / "ghoo" / "commands" / "get_commands.py",
        ]
        
        failing_patterns = []
        
        for file_path in command_files:
            if not file_path.exists():
                continue
                
            content = file_path.read_text()
            lines = content.split('\n')
            
            # Look for command functions
            for line_num, line in enumerate(lines, 1):
                if line.strip().startswith("def ") and ("repo:" in line or "repo=" in line):
                    func_name = line.strip().split("def ")[1].split("(")[0]
                    
                    # Skip helper functions
                    if func_name.startswith('_') or func_name in ['main', 'display_audit_trail_info', 'version']:
                        continue
                    
                    # Look ahead to find the function body
                    func_start = line_num
                    func_end = len(lines)
                    
                    # Find the end of this function (next def or end of file)
                    for i in range(line_num, len(lines)):
                        if lines[i].strip().startswith("def ") and i != line_num - 1:
                            func_end = i
                            break
                        if lines[i].strip().startswith("@") and i > line_num + 5:  # New command decorator
                            func_end = i
                            break
                    
                    func_content = '\n'.join(lines[func_start:func_end])
                    
                    # Check for required patterns
                    required_patterns = [
                        "config_loader = ConfigLoader(",
                        "resolve_repository(repo, config_loader)",
                        "GitHubClient(config=config, config_dir=config_loader.get_config_dir())",
                    ]
                    
                    missing_patterns = []
                    for pattern in required_patterns:
                        if pattern not in func_content:
                            missing_patterns.append(pattern)
                    
                    if missing_patterns:
                        failing_patterns.append(f"{file_path.name}:{func_name} - Missing patterns: {missing_patterns}")
        
        if failing_patterns:
            failure_msg = "Commands missing required config/repo patterns:\n" + "\n".join(failing_patterns)
            pytest.fail(failure_msg)
    
    def test_documentation_consistency(self):
        """Test that documentation reflects the --repo requirements."""
        
        doc_files = [
            Path(__file__).parent.parent.parent / "CLAUDE.md",
            Path(__file__).parent.parent.parent / "SPEC.md",
        ]
        
        missing_requirements = []
        
        for doc_file in doc_files:
            if not doc_file.exists():
                continue
                
            content = doc_file.read_text()
            
            # Check for required documentation elements
            required_elements = [
                "--repo",  # Should mention --repo parameter
                "optional",  # Should mention it's optional
                "config",  # Should mention config fallback
            ]
            
            missing_in_file = []
            for element in required_elements:
                if element.lower() not in content.lower():
                    missing_in_file.append(element)
            
            if missing_in_file:
                missing_requirements.append(f"{doc_file.name}: Missing {missing_in_file}")
        
        if missing_requirements:
            failure_msg = "Documentation missing --repo requirements:\n" + "\n".join(missing_requirements)
            pytest.fail(failure_msg)
    
    def _get_all_typer_commands(self, typer_app):
        """Extract all command functions from a Typer app."""
        commands = {}
        
        # Typer stores commands in the app.registered_commands attribute
        if hasattr(typer_app, 'registered_commands'):
            for command in typer_app.registered_commands:
                if hasattr(command, 'callback') and command.callback:
                    commands[command.callback.__name__] = command.callback
        
        # Also check the commands attribute
        if hasattr(typer_app, 'commands'):
            for cmd_name, command in typer_app.commands.items():
                if hasattr(command, 'callback') and command.callback:
                    commands[command.callback.__name__] = command.callback
        
        # Fallback: inspect the app object for registered commands
        if not commands:
            # This is a more manual approach for different Typer versions
            for attr_name in dir(typer_app):
                attr = getattr(typer_app, attr_name)
                if hasattr(attr, '__iter__'):
                    try:
                        for item in attr:
                            if hasattr(item, 'callback') and callable(item.callback):
                                commands[item.callback.__name__] = item.callback
                    except (TypeError, AttributeError):
                        pass
        
        return commands


class TestSpecificCommandCoverage:
    """Test specific commands that we know should exist."""
    
    def test_known_commands_exist_and_have_repo(self):
        """Test that all known commands exist and have proper --repo parameter."""
        
        # Import all the commands we know should exist
        from ghoo.main import (
            set_body, create_todo, check_todo, create_section, update_section,
            create_condition, update_condition, complete_condition, verify_condition,
            create_epic, create_task, create_sub_task,
            start_plan, submit_plan, approve_plan,
            start_work, submit_work, approve_work,
            post_comment, get_latest_comment_timestamp, get_comments
        )
        
        from ghoo.commands.get_commands import (
            epic, task, subtask, milestone, section, todo, condition, conditions
        )
        
        all_commands = [
            # Main commands
            set_body, create_todo, check_todo, create_section, update_section,
            create_condition, update_condition, complete_condition, verify_condition,
            create_epic, create_task, create_sub_task,
            start_plan, submit_plan, approve_plan,
            start_work, submit_work, approve_work,
            post_comment, get_latest_comment_timestamp, get_comments,
            # Get commands
            epic, task, subtask, milestone, section, todo, condition, conditions
        ]
        
        failing_commands = []
        
        for cmd in all_commands:
            sig = inspect.signature(cmd)
            params = list(sig.parameters.items())
            
            # Should have repo parameter
            if not any(param_name == 'repo' for param_name, _ in params):
                failing_commands.append(f"{cmd.__name__}: Missing 'repo' parameter")
                continue
            
            # repo should be the first parameter
            if params[0][0] != 'repo':
                failing_commands.append(f"{cmd.__name__}: 'repo' should be first parameter, got '{params[0][0]}'")
                continue
            
            # repo should be optional
            repo_param = params[0][1]
            if repo_param.default is inspect.Parameter.empty:
                failing_commands.append(f"{cmd.__name__}: 'repo' parameter should be optional")
        
        if failing_commands:
            failure_msg = "Known commands failing requirements:\n" + "\n".join(failing_commands)
            pytest.fail(failure_msg)
    
    def test_command_count_sanity_check(self):
        """Sanity check that we have a reasonable number of commands."""
        
        from ghoo.main import app as main_app
        from ghoo.commands.get_commands import get_app
        
        # We should have many commands
        all_commands = self._get_all_typer_commands(main_app)
        all_commands.update(self._get_all_typer_commands(get_app))
        
        # Remove non-command functions
        exempt = {'version', 'display_audit_trail_info', 'main'}
        command_count = len([cmd for cmd in all_commands.keys() if cmd not in exempt])
        
        assert command_count >= 25, f"Expected at least 25 commands, but found {command_count}. Commands: {list(all_commands.keys())}"
    
    def _get_all_typer_commands(self, typer_app):
        """Helper method to extract commands from Typer app."""
        commands = {}
        
        # Try different ways to get commands depending on Typer version
        if hasattr(typer_app, 'registered_commands'):
            for command in typer_app.registered_commands:
                if hasattr(command, 'callback') and command.callback:
                    commands[command.callback.__name__] = command.callback
        
        if hasattr(typer_app, 'commands'):
            for cmd_name, command in typer_app.commands.items():
                if hasattr(command, 'callback') and command.callback:
                    commands[command.callback.__name__] = command.callback
        
        return commands