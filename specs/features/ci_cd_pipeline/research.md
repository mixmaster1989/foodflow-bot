# Research: CI/CD Pipeline Implementation

**Date**: 2025-11-25  
**Feature**: CI/CD Pipeline for Linting and Testing

## Tool Research

### Linting Tools Comparison

| Tool | Speed | Python Support | Configuration | Decision |
|------|-------|----------------|--------------|----------|
| **Ruff** | ⚡ Very Fast (Rust) | 3.10+ | `pyproject.toml` or `.ruff.toml` | ✅ **Selected** |
| flake8 | 🐌 Slow | 3.6+ | `.flake8` or `setup.cfg` | ❌ Rejected (slower) |
| pylint | 🐌 Very Slow | 3.6+ | `.pylintrc` | ❌ Rejected (too slow) |
| black | ⚡ Fast | 3.7+ | `pyproject.toml` | ⚠️ Formatter, not linter |

**Decision**: Ruff - fastest option, modern, compatible with flake8 rules.

### Testing Framework

| Framework | Async Support | Fixtures | Popularity | Decision |
|-----------|---------------|----------|-------------|----------|
| **pytest** | ✅ Yes | ✅ Rich | ⭐⭐⭐⭐⭐ | ✅ **Selected** |
| unittest | ⚠️ Limited | ⚠️ Basic | ⭐⭐⭐ | ❌ Less feature-rich |

**Decision**: pytest - already mentioned in roadmap, best async support for aiogram.

### GitHub Actions Setup

**Python Setup Action**: `actions/setup-python@v5`
- Supports Python 3.10, 3.11, 3.12
- Automatic caching of pip dependencies
- Cross-platform support

**Caching Strategy**:
- Use `actions/cache@v3` for pip cache
- Cache key: `${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}`
- Restore cache before `pip install`

**Workflow Triggers**:
```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
```

## Configuration Research

### Ruff Configuration

**File**: `pyproject.toml` (preferred) or `.ruff.toml`

**Recommended Settings**:
```toml
[tool.ruff]
line-length = 88
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP"]
ignore = []

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]  # Allow unused imports in __init__.py
```

**Rationale**: 
- `E`, `F`: pycodestyle and pyflakes (essential)
- `W`: pycodestyle warnings
- `I`: isort (import sorting)
- `N`: pep8-naming
- `UP`: pyupgrade (modernize Python syntax)

### GitHub Actions Workflow Structure

**Required Steps**:
1. Checkout code
2. Set up Python
3. Cache dependencies
4. Install dependencies
5. Run Ruff linting
6. Run pytest (if tests exist)

**Error Handling**:
- Ruff: Fail on any linting errors
- pytest: Skip if `tests/` directory doesn't exist (use `continue-on-error: false` but check directory first)

## Dependencies Research

**Current Dependencies** (from `requirements.txt`):
- aiogram>=3.0.0
- sqlalchemy>=2.0.0
- asyncpg
- python-dotenv
- requests
- aiohttp
- pydantic-settings
- rapidfuzz

**CI-Specific Dependencies** (to add):
- ruff (for linting)
- pytest (for testing, when tests are added)
- pytest-asyncio (for async test support)

**Installation Strategy**:
- Install from `requirements.txt` first
- Then install CI-specific tools: `pip install ruff pytest pytest-asyncio`

## Performance Considerations

**Expected CI Runtime**:
- Setup Python: ~10s
- Cache restore: ~2s (if cache hit)
- Install dependencies: ~30s (first run), ~5s (cached)
- Run Ruff: ~5-10s (depends on codebase size)
- Run pytest: ~0s (no tests yet), future ~10-30s

**Total Expected Time**: ~50-60s (first run), ~20-30s (cached runs)

**Optimization**:
- Cache pip dependencies (major time saver)
- Use Ruff (fastest linter)
- Run linting and tests in parallel (if both exist)

## Security Considerations

**GitHub Actions Security**:
- Workflow runs in isolated environment
- No secrets required for linting/testing
- Read-only access to repository

**Dependency Security**:
- Use pinned versions in `requirements.txt` (already done)
- Consider adding `pip-audit` in future for vulnerability scanning

## References

- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [GitHub Actions Python Setup](https://github.com/actions/setup-python)
- [GitHub Actions Caching](https://docs.github.com/en/actions/using-workflows/caching-dependencies-to-speed-up-workflows)
- [pytest Documentation](https://docs.pytest.org/)

