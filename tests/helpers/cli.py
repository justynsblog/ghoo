"""CLI testing utilities for ghoo."""

import json
import yaml
from typing import Any, Dict, List, Optional
import subprocess


def parse_json_output(output: str) -> Any:
    """Parse JSON output from CLI command."""
    try:
        return json.loads(output)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Failed to parse JSON output: {e}\nOutput: {output}")


def parse_yaml_output(output: str) -> Any:
    """Parse YAML output from CLI command."""
    try:
        return yaml.safe_load(output)
    except yaml.YAMLError as e:
        raise AssertionError(f"Failed to parse YAML output: {e}\nOutput: {output}")


def assert_command_success(result: subprocess.CompletedProcess, 
                          expected_output: Optional[str] = None):
    """Assert that a CLI command succeeded.
    
    Args:
        result: The CompletedProcess from running the command
        expected_output: Optional string that should be in stdout
    """
    assert result.returncode == 0, (
        f"Command failed with exit code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    
    if expected_output:
        assert expected_output in result.stdout, (
            f"Expected output not found.\n"
            f"Expected: {expected_output}\n"
            f"Actual stdout: {result.stdout}"
        )


def assert_command_error(result: subprocess.CompletedProcess,
                        expected_error: Optional[str] = None,
                        exit_code: Optional[int] = None):
    """Assert that a CLI command failed as expected.
    
    Args:
        result: The CompletedProcess from running the command
        expected_error: Optional string that should be in stderr or stdout
        exit_code: Expected exit code (default: any non-zero)
    """
    if exit_code is not None:
        assert result.returncode == exit_code, (
            f"Expected exit code {exit_code}, got {result.returncode}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
    else:
        assert result.returncode != 0, (
            f"Expected command to fail but it succeeded\n"
            f"stdout: {result.stdout}"
        )
    
    if expected_error:
        output = result.stderr + result.stdout
        assert expected_error in output, (
            f"Expected error not found.\n"
            f"Expected: {expected_error}\n"
            f"Actual output: {output}"
        )


def create_ghoo_config(project_dir: str, config: Dict[str, Any]) -> str:
    """Create a ghoo.yaml config file in the specified directory.
    
    Args:
        project_dir: Directory to create config in
        config: Configuration dictionary
        
    Returns:
        Path to created config file
    """
    import os
    config_path = os.path.join(project_dir, 'ghoo.yaml')
    
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    
    return config_path