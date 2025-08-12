# Test Environment Setup Guide

This guide provides comprehensive instructions for setting up and managing the ghoo test environment across different scenarios and platforms.

## Quick Start

### Option 1: Automated Setup (Recommended)
```bash
# Create virtual environment and install all dependencies
python3 scripts/setup_test_env.py

# Activate the environment
source .venv/bin/activate

# Verify installation
python3 tests/dependency_manager.py
```

### Option 2: Enhanced Test Runner
```bash
# Check dependencies and install missing ones
python3 scripts/run_tests.py --install-missing

# Run tests with dependency checking
python3 scripts/run_tests.py --check-deps
```

## Environment Overview

The ghoo test environment supports two modes:

- **LIVE Mode**: Uses real GitHub API with your credentials for full end-to-end testing
- **MOCK Mode**: Uses mock data for offline testing and CI/CD environments

### Mode Selection

The system automatically selects the appropriate mode based on available credentials:

| Credentials Available | Mode | Description |
|----------------------|------|-------------|
| `TESTING_GITHUB_TOKEN` + `TESTING_GH_REPO` | LIVE | Full API testing |
| Missing credentials | MOCK | Offline testing with mocks |
| `FORCE_MOCK_MODE=true` | MOCK | Forced mock mode |
| `FORCE_LIVE_MODE=true` | LIVE | Forced live mode (will fail without credentials) |

## Detailed Setup Instructions

### 1. Prerequisites

**Required:**
- Python 3.10+ 
- Git
- Internet connection (for dependency installation)

**Optional but Recommended:**
- uv (fast Python package manager)
- GitHub token for live API testing

### 2. Clone and Navigate
```bash
git clone <repository-url>
cd ghoo
```

### 3. Environment Configuration

#### Create .env File
```bash
cp .env.example .env  # If available, or create manually:
```

**For Live Testing (.env file):**
```env
TESTING_GITHUB_TOKEN=your_github_token_here
TESTING_GH_REPO=your-username/your-test-repo
```

**For Mock Testing (.env file):**
```env
FORCE_MOCK_MODE=true
TESTING_GH_REPO=mock/test-repo
```

#### GitHub Token Setup
1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Generate a new token with these permissions:
   - `repo` (Full control of private repositories)
   - `read:org` (Read org and team membership)
3. Copy the token to your `.env` file

### 4. Dependency Installation

#### Method 1: Virtual Environment Setup Script (Recommended)
```bash
python3 scripts/setup_test_env.py
```

This script will:
- Create a Python virtual environment in `.venv/`
- Install all required and optional dependencies
- Verify the installation
- Provide activation instructions

#### Method 2: Manual uv Installation
```bash
# Install uv if not available
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

#### Method 3: Manual pip Installation
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install project with dev dependencies
pip install -e ".[dev]"
```

#### Method 4: System Installation (Not Recommended)
```bash
# Install directly to system Python (may cause conflicts)
pip install -e ".[dev]"
```

### 5. Verification

After installation, verify everything works:

```bash
# Activate virtual environment (if using one)
source .venv/bin/activate

# Check all dependencies
python3 tests/dependency_manager.py --verbose

# Run diagnostic checks
python3 scripts/run_tests.py --diagnostic

# Test ghoo CLI
python3 -m ghoo.main --version
```

## Running Tests

### Using the Enhanced Test Runner (Recommended)

```bash
# Run all tests with dependency checking
python3 scripts/run_tests.py --check-deps

# Install missing dependencies and run tests  
python3 scripts/run_tests.py --install-missing

# Run specific test types
python3 scripts/run_tests.py --test-type unit
python3 scripts/run_tests.py --test-type integration  
python3 scripts/run_tests.py --test-type e2e

# Pass additional pytest arguments
python3 scripts/run_tests.py -k test_create_epic --verbose
```

### Direct pytest Usage

```bash
# Ensure environment is set up
source .venv/bin/activate
export PYTHONPATH="$PWD/src:$PYTHONPATH"
set -a && source .env && set +a

# Run tests
python3 -m pytest tests/ -v
python3 -m pytest tests/unit/ -v
python3 -m pytest tests/integration/ -v  
python3 -m pytest tests/e2e/ -v
```

### CI/CD Usage

The test environment is designed to work seamlessly in CI/CD:

```bash
# GitHub Actions workflow example
- name: Set up test environment
  run: |
    python3 scripts/setup_test_env.py --quiet
    source .venv/bin/activate
    python3 tests/dependency_manager.py

- name: Run tests
  run: |
    source .venv/bin/activate
    python3 scripts/run_tests.py --check-deps
```

## Dependency Management

### Understanding Dependencies

The system uses a comprehensive dependency management system:

**Required Dependencies:**
- `pytest` - Testing framework
- `pytest-httpx` - HTTP mocking
- `pydantic` - Data validation  
- `httpx` - Async HTTP client
- `PyGithub` - GitHub API client
- `typer` - CLI framework
- `Jinja2` - Template engine
- `requests` - HTTP library

**Optional Dependencies:**
- `python-dotenv` - .env file loading (manual fallback available)
- `uv` - Fast package installer (pip fallback available)

### Checking Dependencies

```bash
# Check all dependencies
python3 tests/dependency_manager.py

# Verbose report with installation instructions
python3 tests/dependency_manager.py --verbose

# JSON format for automation
python3 tests/dependency_manager.py --format json

# Install missing dependencies
python3 tests/dependency_manager.py --install
```

### Installing Missing Dependencies

```bash
# Automatic installation
python3 tests/dependency_manager.py --install

# Include optional dependencies
python3 tests/dependency_manager.py --install --install-optional

# Manual installation using reported commands
pip install pytest-httpx>=0.35.0 pydantic httpx
```

## Environment Variables

### Core Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `TESTING_GITHUB_TOKEN` | Live mode | GitHub API token | `ghp_xxxxxxxxxxxx` |
| `TESTING_GH_REPO` | Live mode | Test repository | `owner/repo` |
| `PYTHONPATH` | Auto-set | Python module path | `/path/to/ghoo/src` |

### Mode Control Variables

| Variable | Description | Values |
|----------|-------------|--------|
| `FORCE_MOCK_MODE` | Force mock mode | `true`, `false` |
| `FORCE_LIVE_MODE` | Force live mode | `true`, `false` |
| `REQUIRE_CREDENTIALS` | Require valid credentials | `true`, `false` |

### Test Control Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VALIDATE_TOKEN` | Validate token format | `true` |
| `TESTING_GH_PROJECT` | Project URL override | Auto-detected |

## Troubleshooting

### Common Issues and Solutions

#### 1. "No module named 'ghoo'" Error
```bash
# Solution: Set PYTHONPATH
export PYTHONPATH="$PWD/src:$PYTHONPATH"

# Or use the test runner which sets this automatically
python3 scripts/run_tests.py
```

#### 2. "Missing required dependencies" Error
```bash
# Check what's missing
python3 tests/dependency_manager.py --verbose

# Install missing dependencies
python3 tests/dependency_manager.py --install

# Or use the virtual environment setup script
python3 scripts/setup_test_env.py
```

#### 3. "GitHub token not found" Error
```bash
# Check .env file exists and contains token
cat .env

# Create .env file if missing
echo "TESTING_GITHUB_TOKEN=your_token_here" > .env
echo "TESTING_GH_REPO=owner/repo" >> .env

# Or force mock mode
echo "FORCE_MOCK_MODE=true" > .env
```

#### 4. "uv command not found" Error
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or use pip fallback (automatic)
python3 scripts/setup_test_env.py
```

#### 5. Tests Show "SKIPPED" Status
```bash
# This means tests aren't running - check environment
python3 scripts/run_tests.py --diagnostic

# Ensure dependencies are installed
python3 tests/dependency_manager.py --install

# Check environment variables
set -a && source .env && set +a
python3 -c "import os; print('Token length:', len(os.getenv('TESTING_GITHUB_TOKEN', '')))"
```

#### 6. Virtual Environment Issues
```bash
# Remove and recreate virtual environment
rm -rf .venv
python3 scripts/setup_test_env.py --force

# Or create manually
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

#### 7. Permission Errors
```bash
# Use virtual environment instead of system installation
python3 scripts/setup_test_env.py

# Or install with --user flag
pip install --user -e ".[dev]"
```

### Environment Diagnostics

Use the diagnostic tools to identify issues:

```bash
# Comprehensive diagnostic report
python3 scripts/run_tests.py --diagnostic

# Dependency status
python3 tests/dependency_manager.py --verbose

# Test environment status
python3 -c "from tests.environment import get_test_environment; get_test_environment().log_environment_status()"
```

## Advanced Configuration

### Custom Test Repository

To use your own test repository:

1. Create a GitHub repository for testing
2. Set up the repository with issue types and labels:
   ```bash
   ghoo init-gh your-username/your-test-repo
   ```
3. Update `.env` file:
   ```env
   TESTING_GH_REPO=your-username/your-test-repo
   ```

### Docker Environment

While not currently implemented, the system is designed to support Docker:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -e ".[dev]"
ENV PYTHONPATH="/app/src"
ENV FORCE_MOCK_MODE=true
CMD ["python", "-m", "pytest", "tests/"]
```

### Multiple Python Versions

Test with multiple Python versions using pyenv or similar:

```bash
# Install different Python versions
pyenv install 3.10.12 3.11.9 3.12.3

# Test each version
for version in 3.10.12 3.11.9 3.12.3; do
    pyenv shell $version
    python3 scripts/setup_test_env.py --force
    source .venv/bin/activate
    python3 scripts/run_tests.py
done
```

## Best Practices

### For Developers

1. **Always use virtual environments** to avoid dependency conflicts
2. **Run dependency checks** before committing changes
3. **Test in both LIVE and MOCK modes** when possible
4. **Use the enhanced test runner** for comprehensive testing
5. **Check diagnostics** when encountering issues

### For CI/CD

1. **Use the setup script** for consistent environments
2. **Cache virtual environments** to speed up builds
3. **Run dependency audits** regularly
4. **Use mock mode** for security and reliability
5. **Generate diagnostic reports** for debugging

### For Contributors

1. **Document new dependencies** in the dependency manager
2. **Test installation methods** on different platforms  
3. **Update documentation** when changing requirements
4. **Verify backwards compatibility** with older Python versions
5. **Test offline capabilities** in mock mode

## Platform-Specific Notes

### Linux (Ubuntu/Debian)
```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install python3-venv python3-pip git curl

# The rest follows standard instructions
```

### macOS
```bash
# Install dependencies via Homebrew
brew install python git

# Or use system Python
# The rest follows standard instructions
```

### Windows
```powershell
# Install Python from python.org or Microsoft Store
# Use PowerShell or Command Prompt
# Replace 'source .venv/bin/activate' with '.venv\Scripts\activate'

python scripts/setup_test_env.py
.venv\Scripts\activate
python tests/dependency_manager.py
```

## Getting Help

If you encounter issues not covered in this guide:

1. **Run diagnostics**: `python3 scripts/run_tests.py --diagnostic`
2. **Check dependencies**: `python3 tests/dependency_manager.py --verbose`
3. **Review logs**: Look for error messages in test output
4. **Check GitHub Issues**: Search for similar problems
5. **Create an issue**: Provide diagnostic output and error details

## Changelog

### Recent Improvements
- ✅ Centralized environment management
- ✅ Manual .env parsing fallback
- ✅ Comprehensive dependency checking
- ✅ Virtual environment setup script
- ✅ Enhanced test runner with dependency management
- ✅ CI/CD workflow configurations
- ✅ Diagnostic tools and reporting

### Future Enhancements
- Docker containerization support
- Conda environment support
- Additional CI/CD platform configurations
- Dependency caching and optimization
- Automated security scanning