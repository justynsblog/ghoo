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
        self.config_path = config_path
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
        self.config_path = config_path
        self.yaml_error = original_error
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


class IssueTypeMethodMismatchError(ConfigValidationError):
    """Raised when issue_type_method config doesn't match repository capabilities."""
    
    def __init__(self, configured_method, repo, solution_guidance):
        super().__init__(
            f"❌ Issue Type Configuration Error\n"
            f"\n"
            f"Problem: Repository '{repo}' capabilities don't match configured method\n"
            f"Configuration: issue_type_method: \"{configured_method}\"\n"
            f"\n"
            f"Solutions:\n"
            f"{solution_guidance}\n"
            f"\n"
            f"For help: https://github.com/justynbrt/ghoo/docs/issue-types-setup.md"
        )


class NativeTypesNotConfiguredError(ConfigValidationError):
    """Raised when native issue types are required but not configured in repository."""
    
    def __init__(self, repo, issue_type):
        super().__init__(
            f"❌ Native Issue Types Not Configured\n"
            f"\n"
            f"Problem: Repository '{repo}' doesn't have native issue type '{issue_type}' configured\n"
            f"Configuration: issue_type_method: \"native\" (default)\n"
            f"\n"
            f"Solutions:\n"
            f"1. Setup native issue types (recommended):\n"
            f"   - Go to repository Settings > General > Features > Issues\n"
            f"   - Enable custom issue types\n"
            f"   - Create Epic, Task, and Subtask types\n"
            f"   - See: https://docs.github.com/en/issues/planning-and-tracking-with-projects/managing-items-in-your-project/adding-items-to-your-project\n"
            f"\n"
            f"2. Use label-based approach:\n"
            f"   - Add to ghoo.yaml: issue_type_method: \"labels\"\n"
            f"   - Run: ghoo init-gh to create required labels\n"
            f"\n"
            f"For help: https://github.com/justynbrt/ghoo/docs/issue-types-setup.md"
        )


class GraphQLError(GhooError):
    """Base exception for GraphQL-related errors."""
    pass


class FeatureUnavailableError(GraphQLError):
    """Raised when a GraphQL feature is not available for the repository."""
    
    def __init__(self, message=None, feature_name=None, fallback_message=None):
        if message:
            # Use custom message directly
            super().__init__(message)
        elif feature_name:
            # Legacy behavior for backward compatibility
            error_message = f"GraphQL feature '{feature_name}' is not available for this repository."
            if fallback_message:
                error_message += f" {fallback_message}"
            super().__init__(error_message)
        else:
            super().__init__("Required feature is not available for this repository.")