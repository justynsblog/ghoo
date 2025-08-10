"""Custom exceptions for ghoo."""


class GhooError(Exception):
    """Base exception for all ghoo errors."""
    pass


class AuthenticationError(GhooError):
    """Base exception for authentication-related errors."""
    pass


class MissingTokenError(AuthenticationError):
    """Raised when GitHub token is not found."""
    
    def __init__(self, is_testing=False):
        self.is_testing = is_testing
        token_var = "TESTING_GITHUB_TOKEN" if is_testing else "GITHUB_TOKEN"
        super().__init__(
            f"GitHub authentication token not found.\n"
            f"Please set the {token_var} environment variable with your Personal Access Token.\n"
            f"\n"
            f"To create a token:\n"
            f"1. Go to https://github.com/settings/tokens?type=beta\n"
            f"2. Click 'Generate new token'\n"
            f"3. Set expiration and add repository permissions:\n"
            f"   - Issues: Read & Write\n"
            f"   - Metadata: Read\n"
            f"4. Copy the token and set it:\n"
            f"   export {token_var}='your_token_here'"
        )


class InvalidTokenError(AuthenticationError):
    """Raised when GitHub token is invalid or expired."""
    
    def __init__(self, error_message):
        super().__init__(
            f"GitHub authentication failed: {error_message}\n"
            f"Please check that your token is valid and has not expired.\n"
            f"You may need to generate a new token at:\n"
            f"https://github.com/settings/tokens?type=beta"
        )


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


class GraphQLError(GhooError):
    """Base exception for GraphQL-related errors."""
    pass


class FeatureUnavailableError(GraphQLError):
    """Raised when a GraphQL feature is not available for the repository."""
    
    def __init__(self, feature_name, fallback_message=None):
        message = f"GraphQL feature '{feature_name}' is not available for this repository."
        if fallback_message:
            message += f" {fallback_message}"
        super().__init__(message)