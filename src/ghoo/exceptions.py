"""Custom exceptions for ghoo."""


class GhooError(Exception):
    """Base exception for all ghoo errors."""
    pass


class ConfigError(GhooError):
    """Base exception for configuration-related errors."""
    pass


class ConfigNotFoundError(ConfigError):
    """Raised when ghoo.yaml is not found."""
    
    def __init__(self, config_path):
        super().__init__(
            f"Configuration file not found: {config_path}\n"
            f"Please create a ghoo.yaml file in your project root with at minimum:\n"
            f"  project_url: https://github.com/owner/repo"
        )


class ConfigValidationError(ConfigError):
    """Raised when configuration validation fails."""
    pass


class InvalidYAMLError(ConfigError):
    """Raised when YAML parsing fails."""
    
    def __init__(self, config_path, original_error):
        super().__init__(
            f"Failed to parse YAML from {config_path}\n"
            f"Error: {original_error}"
        )


class InvalidGitHubURLError(ConfigValidationError):
    """Raised when the project_url is not a valid GitHub URL."""
    
    def __init__(self, url):
        super().__init__(
            f"Invalid GitHub URL: {url}\n"
            f"Expected format:\n"
            f"  - Repository: https://github.com/owner/repo\n"
            f"  - Project: https://github.com/orgs/org-name/projects/123"
        )


class MissingRequiredFieldError(ConfigValidationError):
    """Raised when a required configuration field is missing."""
    
    def __init__(self, field_name):
        super().__init__(
            f"Required configuration field '{field_name}' is missing.\n"
            f"Please add it to your ghoo.yaml file."
        )


class InvalidFieldValueError(ConfigValidationError):
    """Raised when a configuration field has an invalid value."""
    
    def __init__(self, field_name, value, valid_options=None):
        message = f"Invalid value for '{field_name}': {value}"
        if valid_options:
            message += f"\nValid options are: {', '.join(valid_options)}"
        super().__init__(message)