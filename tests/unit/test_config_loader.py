"""Unit tests for ConfigLoader."""

import pytest
from pathlib import Path
import tempfile
import yaml

from ghoo.core import ConfigLoader
from ghoo.models import Config
from ghoo.exceptions import (
    ConfigNotFoundError,
    InvalidYAMLError,
    InvalidGitHubURLError,
    MissingRequiredFieldError,
    InvalidFieldValueError,
)


class TestConfigLoader:
    """Test ConfigLoader functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_load_valid_config_repo_url(self, temp_dir):
        """Test loading a valid config with repository URL."""
        config_path = temp_dir / "ghoo.yaml"
        config_data = {
            "project_url": "https://github.com/owner/repo",
            "status_method": "labels",
            "required_sections": {
                "epic": ["Summary", "Goals"],
                "task": ["Summary"]
            }
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        loader = ConfigLoader(config_path)
        config = loader.load()
        
        assert isinstance(config, Config)
        assert config.project_url == "https://github.com/owner/repo"
        assert config.status_method == "labels"
        assert config.required_sections["epic"] == ["Summary", "Goals"]
        assert config.required_sections["task"] == ["Summary"]
    
    def test_load_valid_config_project_url(self, temp_dir):
        """Test loading a valid config with project board URL."""
        config_path = temp_dir / "ghoo.yaml"
        config_data = {
            "project_url": "https://github.com/orgs/my-org/projects/123"
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        loader = ConfigLoader(config_path)
        config = loader.load()
        
        assert config.project_url == "https://github.com/orgs/my-org/projects/123"
        # Should auto-detect status_field for project URLs
        assert config.status_method == "status_field"
    
    def test_auto_detect_status_method_repo(self, temp_dir):
        """Test status_method auto-detection for repository URLs."""
        config_path = temp_dir / "ghoo.yaml"
        config_data = {
            "project_url": "https://github.com/owner/repo"
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        loader = ConfigLoader(config_path)
        config = loader.load()
        
        assert config.status_method == "labels"
    
    def test_auto_detect_status_method_project(self, temp_dir):
        """Test status_method auto-detection for project URLs."""
        config_path = temp_dir / "ghoo.yaml"
        config_data = {
            "project_url": "https://github.com/users/username/projects/5"
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        loader = ConfigLoader(config_path)
        config = loader.load()
        
        assert config.status_method == "status_field"
    
    def test_default_required_sections(self, temp_dir):
        """Test that default required sections are applied when not specified."""
        config_path = temp_dir / "ghoo.yaml"
        config_data = {
            "project_url": "https://github.com/owner/repo"
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        loader = ConfigLoader(config_path)
        config = loader.load()
        
        # Check defaults are applied
        assert "epic" in config.required_sections
        assert "Summary" in config.required_sections["epic"]
        assert "Acceptance Criteria" in config.required_sections["epic"]
        assert "Milestone Plan" in config.required_sections["epic"]
    
    def test_missing_config_file(self, temp_dir):
        """Test error when config file doesn't exist."""
        config_path = temp_dir / "ghoo.yaml"
        loader = ConfigLoader(config_path)
        
        with pytest.raises(ConfigNotFoundError) as exc_info:
            loader.load()
        
        assert str(config_path) in str(exc_info.value)
        assert "create a ghoo.yaml" in str(exc_info.value).lower()
    
    def test_invalid_yaml_syntax(self, temp_dir):
        """Test error when YAML syntax is invalid."""
        config_path = temp_dir / "ghoo.yaml"
        
        with open(config_path, 'w') as f:
            f.write("invalid: yaml: syntax: here")
        
        loader = ConfigLoader(config_path)
        
        with pytest.raises(InvalidYAMLError) as exc_info:
            loader.load()
        
        assert str(config_path) in str(exc_info.value)
    
    def test_missing_project_url(self, temp_dir):
        """Test error when project_url is missing."""
        config_path = temp_dir / "ghoo.yaml"
        config_data = {
            "status_method": "labels"
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        loader = ConfigLoader(config_path)
        
        with pytest.raises(MissingRequiredFieldError) as exc_info:
            loader.load()
        
        assert "project_url" in str(exc_info.value)
    
    def test_invalid_github_url(self, temp_dir):
        """Test error when project_url is not a valid GitHub URL."""
        config_path = temp_dir / "ghoo.yaml"
        invalid_urls = [
            "https://gitlab.com/owner/repo",
            "https://github.com",
            "github.com/owner/repo",
            "https://github.com/owner",
            "https://github.com/orgs/org/invalid/123",
            "not-a-url"
        ]
        
        for url in invalid_urls:
            config_data = {"project_url": url}
            
            with open(config_path, 'w') as f:
                yaml.dump(config_data, f)
            
            loader = ConfigLoader(config_path)
            
            with pytest.raises(InvalidGitHubURLError) as exc_info:
                loader.load()
            
            assert url in str(exc_info.value)
    
    def test_invalid_status_method(self, temp_dir):
        """Test error when status_method has invalid value."""
        config_path = temp_dir / "ghoo.yaml"
        config_data = {
            "project_url": "https://github.com/owner/repo",
            "status_method": "invalid_method"
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        loader = ConfigLoader(config_path)
        
        with pytest.raises(InvalidFieldValueError) as exc_info:
            loader.load()
        
        assert "status_method" in str(exc_info.value)
        assert "labels" in str(exc_info.value)
        assert "status_field" in str(exc_info.value)
    
    def test_invalid_required_sections_type(self, temp_dir):
        """Test error when required_sections is not a dictionary."""
        config_path = temp_dir / "ghoo.yaml"
        config_data = {
            "project_url": "https://github.com/owner/repo",
            "required_sections": ["not", "a", "dict"]
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        loader = ConfigLoader(config_path)
        
        with pytest.raises(InvalidFieldValueError) as exc_info:
            loader.load()
        
        assert "required_sections" in str(exc_info.value)
    
    def test_invalid_required_sections_value_type(self, temp_dir):
        """Test error when required_sections values are not lists."""
        config_path = temp_dir / "ghoo.yaml"
        config_data = {
            "project_url": "https://github.com/owner/repo",
            "required_sections": {
                "epic": "not a list"
            }
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        loader = ConfigLoader(config_path)
        
        with pytest.raises(InvalidFieldValueError) as exc_info:
            loader.load()
        
        assert "required_sections.epic" in str(exc_info.value)
    
    def test_trailing_slash_in_url(self, temp_dir):
        """Test that trailing slashes in URLs are handled correctly."""
        config_path = temp_dir / "ghoo.yaml"
        urls = [
            "https://github.com/owner/repo/",
            "https://github.com/orgs/org/projects/123/"
        ]
        
        for url in urls:
            config_data = {"project_url": url}
            
            with open(config_path, 'w') as f:
                yaml.dump(config_data, f)
            
            loader = ConfigLoader(config_path)
            config = loader.load()
            
            # Should accept URLs with trailing slashes (stored as-is)
            assert config.project_url == url.strip()
    
    def test_empty_required_sections_list(self, temp_dir):
        """Test that empty lists are allowed for required_sections."""
        config_path = temp_dir / "ghoo.yaml"
        config_data = {
            "project_url": "https://github.com/owner/repo",
            "required_sections": {
                "epic": [],
                "task": ["Summary"]
            }
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        loader = ConfigLoader(config_path)
        config = loader.load()
        
        assert config.required_sections["epic"] == []
        assert config.required_sections["task"] == ["Summary"]