# Quick Test Setup Reference

## 🚀 Fastest Setup (One Command)

```bash
python3 scripts/setup_test_env.py && source .venv/bin/activate
```

## 🔧 Essential Commands

| Task | Command |
|------|---------|
| **Setup environment** | `python3 scripts/setup_test_env.py` |
| **Check dependencies** | `python3 tests/dependency_manager.py` |
| **Run all tests** | `python3 scripts/run_tests.py` |
| **Run E2E tests** | `python3 scripts/run_tests.py --test-type e2e` |
| **Install missing deps** | `python3 scripts/run_tests.py --install-missing` |
| **Diagnostic check** | `python3 scripts/run_tests.py --diagnostic` |

## ⚙️ Environment Variables

**Live Mode (.env file):**
```env
TESTING_GITHUB_TOKEN=your_token_here
TESTING_GH_REPO=owner/repo
```

**Mock Mode (.env file):**
```env
FORCE_MOCK_MODE=true
```

## 🐛 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| `No module named 'ghoo'` | `export PYTHONPATH="$PWD/src:$PYTHONPATH"` |
| Missing dependencies | `python3 tests/dependency_manager.py --install` |
| Tests show SKIPPED | `set -a && source .env && set +a` |
| uv not found | Installs automatically fall back to pip |
| GitHub token errors | Add token to .env or use `FORCE_MOCK_MODE=true` |

## 📋 Pre-commit Checklist

```bash
# 1. Check dependencies
python3 tests/dependency_manager.py

# 2. Run diagnostic
python3 scripts/run_tests.py --diagnostic

# 3. Run all tests
python3 scripts/run_tests.py --check-deps

# 4. Verify clean status
git status
```

## 🔗 Need More Help?

- **Full Setup Guide**: `docs/TEST_ENVIRONMENT_SETUP.md`
- **Dependency Issues**: `python3 tests/dependency_manager.py --verbose`
- **Environment Issues**: `python3 scripts/run_tests.py --diagnostic`