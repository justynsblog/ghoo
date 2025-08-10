# ghoo

A CLI tool for structured GitHub issue management using a strict workflow (Epic ’ Task ’ Sub-task).

## Features

- **Hierarchical Issue Management**: Organize work with Epics, Tasks, and Sub-tasks
- **GitHub Integration**: Native support for GitHub's custom issue types and Projects V2
- **Workflow Automation**: Enforce consistent development processes
- **Flexible Configuration**: Adapt to your team's needs with customizable settings
- **Rich CLI Experience**: Beautiful terminal output with progress tracking

## Installation

```bash
# Install with pip
pip install ghoo

# Or with uv (recommended)
uv pip install ghoo
```

## Quick Start

1. Set up your GitHub token:
```bash
export GITHUB_TOKEN=ghp_your_token_here
```

2. Initialize your repository:
```bash
ghoo init-gh
```

3. Create your first Epic:
```bash
ghoo create-epic owner/repo "Build User Authentication"
```

## Available Commands

### Issue Creation
- `ghoo create-epic` - Create new Epic issues
- `ghoo create-task` - Create Tasks linked to Epics
- `ghoo create-sub-task` - Create Sub-tasks linked to Tasks

### Issue Management
- `ghoo get` - Display detailed issue information
- `ghoo set-body` - Update issue body content

### Repository Setup
- `ghoo init-gh` - Initialize repository with required configuration

More commands coming in future releases. See [full documentation](docs/user-guide/commands.md).

## Documentation

- [Getting Started Guide](docs/user-guide/getting-started.md)
- [Command Reference](docs/user-guide/commands.md)
- [Workflow Guide](docs/user-guide/workflow.md)
- [Configuration](docs/user-guide/configuration.md)
- [API Reference](docs/development/api-reference.md)

## Development

See [CLAUDE.md](CLAUDE.md) for development instructions and current project status.

## License

MIT