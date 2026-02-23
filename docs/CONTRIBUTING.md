# Contributing to dfo (DevFinOps)

> **Thank you for your interest in contributing to dfo!**
>
> This guide will help you get started with contributing code, documentation, bug reports, and feature requests.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Setup](#development-setup)
4. [How to Contribute](#how-to-contribute)
5. [Coding Standards](#coding-standards)
6. [Testing Requirements](#testing-requirements)
7. [Submitting Changes](#submitting-changes)
8. [Code Review Process](#code-review-process)
9. [Documentation](#documentation)
10. [Community](#community)

---

## Code of Conduct

This project adheres to a code of conduct. By participating, you are expected to:

- **Be respectful** - Treat everyone with respect and consideration
- **Be collaborative** - Work together constructively
- **Be inclusive** - Welcome and support people of all backgrounds
- **Be professional** - Focus on what is best for the project and community

---

## Getting Started

### Prerequisites

- **Python 3.11+** (dfo uses modern Python features)
- **Conda** (recommended) or virtualenv
- **Git** for version control
- **Azure subscription** (optional, for testing Azure features)

### Quick Start

```bash
# 1. Fork the repository on GitHub
# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/dfo.git
cd dfo

# 3. Create conda environment
conda env create -f environment.yml
conda activate dfo

# 4. Install in editable mode
pip install -e .

# 5. Verify installation
./dfo version
pytest src/dfo/tests/

# 6. Create a feature branch
git checkout -b feature/my-new-feature
```

---

## Development Setup

### Environment Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings (optional for development)
# Most tests use mocked Azure SDK calls and don't require real credentials
```

### Development Tools

**Required:**
- `pytest` - Testing framework
- `pytest-cov` - Coverage reporting
- `typer` - CLI framework
- `rich` - Terminal output formatting

**Recommended:**
- `black` - Code formatting (future)
- `ruff` - Linting (future)
- `mypy` - Type checking (future)

### Database Setup

```bash
# Initialize test database
./dfo db init

# Verify database
./dfo db info
```

---

## How to Contribute

### Ways to Contribute

1. **Report bugs** - Found something broken? Let us know!
2. **Suggest features** - Have an idea? Open an issue for discussion
3. **Fix bugs** - Pick an issue labeled `bug` or `good-first-issue`
4. **Add features** - Implement new analyzers, reports, or cloud providers
5. **Improve documentation** - Help others understand the project
6. **Write tests** - Increase coverage, add edge case tests
7. **Review PRs** - Help review and test pull requests

### Finding Work

**Good first issues:**
- Look for issues labeled `good-first-issue` or `help-wanted`
- Check [TODO.md](/TODO.md) for pending work
- Review [TEST_COVERAGE_ANALYSIS.md](/docs/TEST_COVERAGE_ANALYSIS.md) for gaps

**Priority areas:**
1. Test coverage improvements (see TODO.md)
2. Storage analysis implementation (Phase 2)
3. CLI enhancements (progress bars, better errors)
4. Documentation improvements

---

## Coding Standards

### Code Style

**dfo follows strict code standards defined in [CODE_STYLE.md](/docs/CODE_STYLE.md).**

#### Key Principles

1. **Explicit > Implicit** - No magic or hidden side effects
2. **Small modules** - ≤ 250 lines per file
3. **Small functions** - ≤ 40 lines per function
4. **Strong typing** - All functions have type hints
5. **Rule of One** - One responsibility per module/class/function

#### Naming Conventions

```python
# Files/Modules (snake_case)
idle_vms.py
plan_manager.py

# Classes (CamelCase)
class VMInventory:
    ...

class PlanManager:
    ...

# Functions (snake_case, verbs)
def analyze_idle_vms(...) -> List[VMAnalysis]:
    ...

def create_plan(...) -> ExecutionPlan:
    ...

# Constants (UPPER_CASE)
DEFAULT_CPU_THRESHOLD = 5.0
MAX_RETRY_ATTEMPTS = 3
```

#### Import Order

```python
# 1. Standard library
import os
from pathlib import Path
from typing import List, Optional

# 2. Third-party
import typer
from pydantic import BaseModel
from rich.console import Console

# 3. Internal (dfo modules)
from dfo.core.config import get_settings
from dfo.db.duck import DuckDBManager
```

### Architecture Guidelines

**Follow the layered architecture:**

```
core → providers → discover → analyze → report → execute → cli
```

**Layer responsibilities:**

| Layer | Responsibilities | Forbidden |
|-------|------------------|-----------|
| `core` | Config, auth, models | Provider calls, DB writes |
| `providers` | Cloud SDK calls only | Analysis, DB writes |
| `discover` | Collect raw data → DB | Analysis logic |
| `analyze` | Pure FinOps logic | Cloud calls, direct DB writes |
| `report` | Render outputs | Analysis, cloud calls |
| `execute` | Apply actions → DB | Discovery |
| `cli` | Orchestrate commands | Business logic |

**No circular imports:**
- Each layer can only import from layers to its left
- Use dependency injection for cross-layer communication

### Type Hints

**All functions must have type hints:**

```python
# ✅ Good
def analyze_idle_vms(
    db: DuckDBManager,
    cpu_threshold: float = 5.0,
    idle_days: int = 14
) -> List[VMAnalysis]:
    """Analyze VMs for idle CPU usage."""
    ...

# ❌ Bad (no type hints)
def analyze_idle_vms(db, cpu_threshold=5.0, idle_days=14):
    ...
```

### Error Handling

**Fail fast with actionable messages:**

```python
# ✅ Good
if not db_path.exists():
    raise FileNotFoundError(
        f"Database not found at {db_path}. "
        "Run 'dfo db init' to create it."
    )

# ❌ Bad (vague)
if not db_path.exists():
    raise Exception("Database error")
```

### Documentation

**Every public function needs a docstring:**

```python
def analyze_idle_vms(
    db: DuckDBManager,
    cpu_threshold: float = 5.0,
    idle_days: int = 14
) -> List[VMAnalysis]:
    """
    Analyze VMs for idle CPU usage.

    Identifies VMs with average CPU utilization below the threshold
    for the specified number of days.

    Args:
        db: DuckDB database manager instance
        cpu_threshold: Maximum average CPU % to consider idle (default: 5.0)
        idle_days: Minimum consecutive days below threshold (default: 14)

    Returns:
        List of VMAnalysis objects with idle VMs and recommendations

    Raises:
        ValueError: If cpu_threshold is not between 0 and 100
        DatabaseError: If database query fails
    """
    ...
```

---

## Testing Requirements

### Test Coverage Targets

**All new code must include tests:**

| Code Type | Coverage Required |
|-----------|-------------------|
| New features | 80%+ |
| Bug fixes | Must add regression test |
| Execution system | 90%+ |
| Report formatters | 90%+ |
| Analysis modules | 80%+ |

### Writing Tests

**See [TESTING_GUIDE.md](/docs/TESTING_GUIDE.md) for comprehensive testing documentation.**

**Quick test template:**

```python
"""Tests for <module>."""
import pytest
from dfo.<module> import <function>

def test_function_success(test_db):
    """Test successful execution with valid input."""
    # Arrange
    db = test_db
    input_data = ...

    # Act
    result = function(db, input_data)

    # Assert
    assert result == expected_output

def test_function_error_handling():
    """Test function raises error for invalid input."""
    with pytest.raises(ValueError, match="Invalid input"):
        function(invalid_input)
```

### Running Tests

```bash
# Run all tests
pytest src/dfo/tests/ tests/

# Run with coverage
pytest --cov=src/dfo --cov-report=term-missing

# Run specific test file
pytest src/dfo/tests/test_my_module.py -v
```

**All tests must pass before submitting a PR.**

---

## Submitting Changes

### Branch Naming

**Use descriptive branch names:**

```
feature/storage-analysis    # New feature
fix/cpu-metrics-parsing     # Bug fix
docs/testing-guide          # Documentation
refactor/plan-manager       # Code refactoring
test/execution-coverage     # Test improvements
```

### Commit Messages

**Follow conventional commit format:**

```
<type>: <short summary>

<optional detailed description>

<optional footer>
```

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test additions or modifications
- `refactor:` - Code refactoring (no behavior change)
- `perf:` - Performance improvements
- `chore:` - Maintenance tasks

**Examples:**

```
feat: Add stopped VMs analysis

Implements detection of VMs stopped for 30+ days with
estimated savings calculation.

Closes #42
```

```
fix: Handle missing CPU metrics in analysis

Previously crashed when VM had no CPU data. Now skips
VM with warning message.

Fixes #38
```

```
test: Add execution system tests (92% coverage)

- test_execute_plan_manager.py (60 tests)
- test_execute_validators.py (30 tests)
- test_execute_approvals.py (12 tests)
```

### Pull Request Process

**1. Before submitting:**

```bash
# Ensure all tests pass
pytest src/dfo/tests/ tests/

# Check coverage (should not decrease)
pytest --cov=src/dfo --cov-report=term

# Run type checking (future)
# mypy src/dfo/

# Format code (future)
# black src/dfo/
```

**2. Create pull request:**

- **Title:** Clear, descriptive (e.g., "Add storage tiering analysis")
- **Description:** What, why, how
  - What problem does this solve?
  - What changes were made?
  - How to test?
  - Screenshots (for UI changes)
  - Related issues
- **Labels:** Add appropriate labels (`bug`, `feature`, `documentation`)
- **Reviewers:** Request review from maintainers

**3. PR template:**

```markdown
## Summary
Brief description of changes

## Motivation
Why is this change needed?

## Changes
- Change 1
- Change 2
- Change 3

## Testing
- [ ] All existing tests pass
- [ ] New tests added (if applicable)
- [ ] Manual testing performed

## Checklist
- [ ] Code follows CODE_STYLE.md
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (for user-facing changes)
- [ ] No decrease in test coverage

## Related Issues
Closes #123
```

**4. Respond to feedback:**
- Address review comments promptly
- Push new commits to the same branch
- Mark conversations as resolved when addressed

**5. Merge:**
- Squash commits before merging (maintainers will handle)
- Delete branch after merge

---

## Code Review Process

### For Contributors

**When your PR is under review:**
- Respond to comments within 48 hours
- Ask questions if feedback is unclear
- Make requested changes in new commits (don't force-push)
- Be open to feedback and alternative approaches

### For Reviewers

**When reviewing PRs:**
1. **Functionality** - Does it work as intended?
2. **Tests** - Are there tests? Do they pass?
3. **Code quality** - Follows CODE_STYLE.md?
4. **Architecture** - Respects layer boundaries?
5. **Documentation** - Docstrings and user docs updated?

**Review checklist:**
- [ ] Code is clear and maintainable
- [ ] No obvious bugs or edge cases missed
- [ ] Tests cover new functionality
- [ ] No decrease in test coverage
- [ ] Documentation is updated
- [ ] No breaking changes (or clearly documented)
- [ ] Follows project architecture

---

## Documentation

### Types of Documentation

**1. Code Documentation**
- Docstrings for all public functions/classes
- Type hints on all functions
- Comments for complex logic only

**2. User Documentation**
- README.md - Project overview
- docs/ - Detailed guides
- CHANGELOG.md - Version history

**3. Developer Documentation**
- ARCHITECTURE.md - System design
- CODE_STYLE.md - Coding standards
- TESTING_GUIDE.md - Testing practices
- This file (CONTRIBUTING.md)

### Documentation Standards

**Update documentation when:**
- Adding new features (user-facing)
- Changing CLI commands
- Modifying architecture
- Fixing bugs that affect usage

**Documentation checklist:**
- [ ] README.md updated (if user-visible change)
- [ ] Relevant docs/*.md files updated
- [ ] Docstrings added/updated
- [ ] CHANGELOG.md entry added (for releases)

---

## Community

### Communication Channels

**GitHub Issues:**
- Bug reports
- Feature requests
- Questions

**Pull Requests:**
- Code contributions
- Documentation improvements

**Discussions (future):**
- General questions
- Design discussions
- Showcasing use cases

### Getting Help

**If you need help:**
1. Check existing documentation
2. Search GitHub issues
3. Open a new issue with `question` label

### Reporting Bugs

**Use this template:**

```markdown
## Bug Description
Clear description of the bug

## Steps to Reproduce
1. Step 1
2. Step 2
3. Step 3

## Expected Behavior
What you expected to happen

## Actual Behavior
What actually happened

## Environment
- OS: [e.g., macOS 14.0]
- Python version: [e.g., 3.11.5]
- dfo version: [e.g., v0.2.0]
- Installation method: [conda/pip]

## Logs/Screenshots
```
Paste relevant logs or attach screenshots
```

## Additional Context
Any other relevant information
```

### Suggesting Features

**Use this template:**

```markdown
## Feature Description
Clear description of the proposed feature

## Use Case
Why is this feature needed? Who would use it?

## Proposed Solution
How should this work?

## Alternatives Considered
What other approaches did you consider?

## Additional Context
Mockups, examples, references
```

---

## Release Process

### Versioning

**dfo follows semantic versioning (SemVer):**
- **MAJOR** (1.x.x) - Breaking changes
- **MINOR** (x.1.x) - New features, backward compatible
- **PATCH** (x.x.1) - Bug fixes, backward compatible

**Current version:** v0.2.0 (Phase 1 MVP complete)

### Release Checklist (Maintainers)

- [ ] All tests pass
- [ ] Coverage meets targets (80%+)
- [ ] CHANGELOG.md updated
- [ ] Version bumped in `pyproject.toml`
- [ ] Documentation updated
- [ ] Tag created (`git tag v0.x.x`)
- [ ] GitHub release created
- [ ] Announcement posted

---

## Project Roadmap

### Current Phase: Phase 1 (MVP) ✅ Complete

**Completed:**
- ✅ Azure idle VM detection
- ✅ DuckDB backend
- ✅ Multi-format reporting
- ✅ Plan-based execution with validation, approval, rollback
- ✅ Comprehensive testing (589 tests, 70%+ coverage)

### Next Phases

**Phase 2: Enhanced Azure** (Planned)
- Storage optimization (tiering, lifecycle)
- Azure Advisor integration
- Resource Graph queries

**Phase 3: Multi-Cloud** (Planned)
- AWS support (EC2, S3)
- Unified analyzers

**Phase 4: Automation** (Planned)
- YAML pipelines
- Scheduling
- Notifications

**Phase 5: Platform** (Planned)
- Web dashboard
- REST API
- LLM assistant

See [ROADMAP.md](/docs/ROADMAP.md) for details.

---

## Recognition

### Contributors

Thank you to all contributors! Your contributions are greatly appreciated.

### License Agreement

By submitting a pull request, you agree to license your contribution under the [LGPL-3.0-or-later](../LICENSE) license.

### Attribution

When you contribute to dfo:
- You retain copyright to your contributions
- Your contributions are licensed under the LGPL-3.0-or-later license
- You will be added to CONTRIBUTORS.md (future)
- Significant contributions will be highlighted in release notes

---

## Questions?

**Have questions about contributing?**
- Check [docs/DEVELOPER_ONBOARDING.md](/docs/DEVELOPER_ONBOARDING.md)
- Review [docs/ARCHITECTURE.md](/docs/ARCHITECTURE.md)
- See [docs/TESTING_GUIDE.md](/docs/TESTING_GUIDE.md)
- Open an issue with the `question` label

---

**Thank you for contributing to dfo!** 🎉

We're excited to work with you to build a better FinOps toolkit for multi-cloud cost optimization.

---

**Last Updated:** 2025-01-26
**Maintained By:** DFO Development Team
