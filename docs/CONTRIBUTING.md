# Contributing to autoD

**Welcome!** Thank you for considering contributing to autoD. This document provides guidelines and workflows for contributing to the project.

**Last Updated**: 2025-10-16

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Workflow](#development-workflow)
4. [Code Standards](#code-standards)
5. [Commit Message Conventions](#commit-message-conventions)
6. [Pull Request Process](#pull-request-process)
7. [Code Review Guidelines](#code-review-guidelines)
8. [Testing Requirements](#testing-requirements)
9. [Documentation Requirements](#documentation-requirements)
10. [Issue Reporting](#issue-reporting)
11. [Feature Requests](#feature-requests)
12. [Community Guidelines](#community-guidelines)

---

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors, regardless of experience level, gender, gender identity and expression, sexual orientation, disability, personal appearance, body size, race, ethnicity, age, religion, or nationality.

### Expected Behavior

- **Be respectful**: Treat all contributors with respect and consideration
- **Be collaborative**: Work together to improve the project
- **Be constructive**: Provide helpful feedback and accept criticism gracefully
- **Be inclusive**: Welcome newcomers and help them get started
- **Be professional**: Keep discussions focused on technical merits

### Unacceptable Behavior

- Harassment, discrimination, or trolling
- Personal attacks or inflammatory comments
- Publishing others' private information
- Other conduct that would be inappropriate in a professional setting

### Reporting Issues

If you experience or witness unacceptable behavior, please report it to the project maintainers at [maintainer email]. All reports will be handled confidentially.

---

## Getting Started

### Prerequisites

Before contributing, ensure you have:

- **Python 3.11+** installed
- **Git** installed and configured
- **GitHub account** with SSH keys set up
- **OpenAI API key** for testing (if contributing to API-related features)

### Initial Setup

1. **Fork the repository** on GitHub:
   - Visit https://github.com/[org]/autoD
   - Click "Fork" button in top-right
   - Clone your fork: `git clone git@github.com:[your-username]/autoD.git`

2. **Set up development environment**:
   ```bash
   cd autoD
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # Development dependencies
   ```

3. **Configure pre-commit hooks** (optional but recommended):
   ```bash
   pre-commit install
   ```

4. **Verify setup**:
   ```bash
   pytest  # Run tests
   black src/ tests/ --check  # Check formatting
   mypy src/  # Type checking
   ```

5. **Add upstream remote**:
   ```bash
   git remote add upstream git@github.com:[org]/autoD.git
   git fetch upstream
   ```

---

## Development Workflow

### Branching Strategy

We use a feature branch workflow:

```
main (production-ready code)
  ↓
  develop (integration branch)
    ↓
    feature/add-retry-logic (your feature branch)
```

### Creating a Feature Branch

1. **Sync with upstream**:
   ```bash
   git checkout develop
   git pull upstream develop
   ```

2. **Create feature branch**:
   ```bash
   git checkout -b feature/add-retry-logic
   ```

   **Branch naming conventions**:
   - `feature/description` - New features
   - `fix/description` - Bug fixes
   - `docs/description` - Documentation updates
   - `refactor/description` - Code refactoring
   - `test/description` - Test improvements

3. **Make changes**:
   - Write code following [Code Standards](#code-standards)
   - Write tests for new functionality
   - Update documentation if needed
   - Run tests locally: `pytest`

4. **Commit changes**:
   - Follow [Commit Message Conventions](#commit-message-conventions)
   - Commit frequently with clear messages
   - Example: `git commit -m "feat: add exponential backoff to API retry logic"`

5. **Push to your fork**:
   ```bash
   git push origin feature/add-retry-logic
   ```

6. **Open Pull Request**:
   - Visit your fork on GitHub
   - Click "Compare & pull request"
   - Fill out PR template (see [Pull Request Process](#pull-request-process))

### Keeping Your Branch Updated

If `develop` changes while you're working:

```bash
# Option 1: Rebase (recommended for clean history)
git fetch upstream
git rebase upstream/develop

# Option 2: Merge (if rebase is too complex)
git fetch upstream
git merge upstream/develop
```

---

## Code Standards

### Python Style Guide

We follow **PEP 8** with some project-specific conventions:

#### Formatting

- **Line length**: 100 characters (not 79)
- **Indentation**: 4 spaces (no tabs)
- **Quotes**: Double quotes for strings (`"text"`)
- **Imports**: Grouped and sorted (use `isort`)
- **Formatter**: Use `black` (run `black src/ tests/`)

#### Type Hints

**Required for all functions**:

```python
# ✅ Good
def process_document(
    file_path: Path,
    db_manager: DatabaseManager,
    skip_duplicates: bool = True,
) -> ProcessingResult:
    """Process a single PDF document."""
    ...

# ❌ Bad
def process_document(file_path, db_manager, skip_duplicates=True):
    ...
```

#### Docstrings

**Required for all public functions and classes**:

```python
def calculate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int,
    model: str,
) -> dict:
    """
    Calculate API cost from token usage.

    Args:
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        cached_tokens: Number of cached prompt tokens
        model: Model name (e.g., "gpt-5-mini")

    Returns:
        Dictionary with token counts and estimated cost:
        {
            "prompt_tokens": int,
            "cached_tokens": int,
            "completion_tokens": int,
            "total_cost": float
        }

    Example:
        >>> cost = calculate_cost(1000, 500, 900, "gpt-5-mini")
        >>> print(f"${cost['total_cost']:.4f}")
        $0.0123
    """
    ...
```

#### Error Handling

**Use specific exception types**:

```python
# ✅ Good
try:
    config = get_config()
except FileNotFoundError as e:
    logger.error(f"Config file not found: {e}")
    raise
except ValidationError as e:
    logger.error(f"Invalid config: {e}")
    raise

# ❌ Bad
try:
    config = get_config()
except Exception as e:
    print(f"Error: {e}")
```

#### Logging

**Use structured logging**:

```python
# ✅ Good
logger.info("Processing document", extra={
    "doc_id": doc.id,
    "filename": doc.original_filename,
    "duration_ms": duration
})

# ❌ Bad
print(f"Processing {doc.original_filename}")
```

### Code Quality Tools

#### black (formatter)

```bash
# Format all code
black src/ tests/

# Check formatting without changes
black src/ tests/ --check
```

#### isort (import sorting)

```bash
# Sort imports
isort src/ tests/

# Check import order
isort src/ tests/ --check-only
```

#### mypy (type checking)

```bash
# Type check all code
mypy src/

# Type check specific file
mypy src/processor.py
```

#### flake8 (linting)

```bash
# Lint all code
flake8 src/ tests/

# Configuration in .flake8
[flake8]
max-line-length = 100
exclude = .venv,__pycache__
```

### Pre-commit Checklist

Before committing, ensure:

- ✅ `black src/ tests/ --check` passes
- ✅ `isort src/ tests/ --check-only` passes
- ✅ `mypy src/` passes
- ✅ `flake8 src/ tests/` passes
- ✅ `pytest` passes
- ✅ Test coverage ≥80% (`pytest --cov=src --cov-fail-under=80`)

**Automated with pre-commit hook**:

Install once:
```bash
pre-commit install
```

Now runs automatically on `git commit`.

---

## Commit Message Conventions

We follow **Conventional Commits** specification:

### Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation changes
- **style**: Code formatting (no logic changes)
- **refactor**: Code restructuring (no behavior changes)
- **test**: Adding or updating tests
- **chore**: Build process, dependency updates

### Scope (optional)

Module or area affected:
- `config` - Configuration changes
- `processor` - Main processor module
- `api` - API client
- `db` - Database models
- `vector` - Vector store

### Examples

```bash
# New feature
git commit -m "feat(processor): add exponential backoff to API retry logic"

# Bug fix
git commit -m "fix(dedupe): handle edge case where SHA-256 is None"

# Documentation
git commit -m "docs: add API client usage examples to README"

# Refactoring
git commit -m "refactor(config): extract validation logic into separate function"

# Tests
git commit -m "test(processor): add integration test for full pipeline"

# Breaking change
git commit -m "feat(api)!: migrate to OpenAI Responses API v2

BREAKING CHANGE: Responses API v2 requires different request format.
Update all API client code to use new format."
```

### Commit Message Best Practices

**DO**:
- ✅ Use imperative mood ("add feature" not "added feature")
- ✅ Keep subject line ≤50 characters
- ✅ Capitalize subject line
- ✅ Don't end subject line with period
- ✅ Separate subject from body with blank line
- ✅ Wrap body at 72 characters
- ✅ Explain *what* and *why*, not *how*

**DON'T**:
- ❌ Use vague messages ("fix bug", "update code")
- ❌ Commit unrelated changes together
- ❌ Include TODO comments in commit messages
- ❌ Use slang or abbreviations

---

## Pull Request Process

### Before Opening a PR

1. **Ensure all tests pass**:
   ```bash
   pytest --cov=src --cov-fail-under=80
   ```

2. **Run code quality checks**:
   ```bash
   black src/ tests/ --check
   isort src/ tests/ --check-only
   mypy src/
   flake8 src/ tests/
   ```

3. **Update documentation** if needed

4. **Sync with upstream**:
   ```bash
   git fetch upstream
   git rebase upstream/develop
   ```

### PR Title and Description

**Title format**:
```
<type>: <short description>
```

**Example**:
```
feat: add retry logic with exponential backoff
```

**Description template**:
```markdown
## Summary
Brief description of changes (1-2 sentences)

## Motivation
Why is this change needed? What problem does it solve?

## Changes
- Added exponential backoff to API client
- Implemented retry predicate for transient errors
- Added integration tests for retry logic

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed
- [ ] Coverage ≥80%

## Documentation
- [ ] Code comments added
- [ ] Docstrings updated
- [ ] README/docs updated (if needed)

## Checklist
- [ ] Tests pass locally
- [ ] Code formatted with black
- [ ] Imports sorted with isort
- [ ] Type checking passes (mypy)
- [ ] No linting errors (flake8)
- [ ] Commits follow conventional commit format
```

### PR Size Guidelines

**Ideal PR size**:
- **Small**: <100 lines changed (preferred)
- **Medium**: 100-300 lines
- **Large**: 300-500 lines (requires justification)
- **Too Large**: >500 lines (split into multiple PRs)

**If your PR is large**:
1. Explain why in the description
2. Consider splitting into multiple PRs
3. Provide detailed testing notes

### Review Process

1. **Automated checks** run (CI/CD):
   - Tests
   - Code quality (black, isort, mypy, flake8)
   - Coverage threshold

2. **Code review** by maintainer:
   - Functionality
   - Code quality
   - Test coverage
   - Documentation

3. **Address feedback**:
   - Make requested changes
   - Push updates to the same branch
   - Comment on review feedback

4. **Approval and merge**:
   - Maintainer approves PR
   - CI checks pass
   - PR is merged (usually "squash and merge")

---

## Code Review Guidelines

### For Authors

**When receiving feedback**:
- Don't take feedback personally
- Ask for clarification if needed
- Explain your reasoning if you disagree
- Make changes promptly
- Thank reviewers for their time

### For Reviewers

**What to review**:
1. **Correctness**: Does the code do what it's supposed to?
2. **Testing**: Are there adequate tests? Do they cover edge cases?
3. **Readability**: Is the code easy to understand?
4. **Maintainability**: Will this be easy to change later?
5. **Performance**: Are there obvious performance issues?
6. **Security**: Are there potential security vulnerabilities?

**How to give feedback**:
- Be respectful and constructive
- Explain *why* something should change
- Suggest alternatives
- Distinguish between "must fix" and "nice to have"
- Acknowledge good work

**Feedback examples**:

❌ **Bad**: "This is wrong."

✅ **Good**: "This could cause a race condition if two processes access the database simultaneously. Consider using a transaction lock here. Example: `with db.get_session() as session: session.execute('LOCK TABLE ...')`"

❌ **Bad**: "Use a better variable name."

✅ **Good**: "The variable name `x` is not descriptive. Consider renaming to `processed_document_count` to clarify what this represents."

---

## Testing Requirements

### Coverage Requirements

- **Minimum coverage**: 80% overall
- **Critical modules**: 90%+ (processor, dedupe, config)
- **New code**: 100% coverage (no untested new code)

### Test Types Required

**For new features**:
1. ✅ Unit tests for individual functions
2. ✅ Integration tests for module interactions
3. ✅ End-to-end test for complete workflow (if applicable)

**For bug fixes**:
1. ✅ Regression test that reproduces the bug
2. ✅ Verification that fix resolves the issue

### Test Guidelines

- Write tests before fixing bugs (reproduce first)
- Use fixtures for common setup
- Mock external dependencies (APIs, databases)
- Test edge cases and error conditions
- Keep tests fast (<1s per test)
- Make tests independent (no test depends on another)

**Example test structure**:

```python
def test_feature_name():
    """Test description in imperative mood."""
    # Arrange - Set up test data
    input_data = {"key": "value"}
    expected_result = "expected"

    # Act - Execute code under test
    actual_result = function_under_test(input_data)

    # Assert - Verify result
    assert actual_result == expected_result
```

---

## Documentation Requirements

### When to Update Documentation

Update documentation when:
- Adding new features
- Changing existing functionality
- Fixing bugs that affect usage
- Adding new configuration options
- Changing API interfaces

### Documentation Types

**Code documentation** (required):
- Docstrings for all public functions/classes
- Inline comments for complex logic
- Type hints for all parameters and return values

**User documentation** (required for new features):
- README updates
- Usage examples
- Configuration instructions

**Developer documentation** (required for architectural changes):
- Architecture Decision Records (ADRs)
- Code architecture updates
- API reference updates

### Documentation Standards

**Docstring format** (Google style):

```python
def function_name(param1: str, param2: int) -> bool:
    """
    Short description (one line).

    Longer description if needed. Can span multiple lines
    and explain the function's purpose in detail.

    Args:
        param1: Description of first parameter
        param2: Description of second parameter

    Returns:
        Description of return value

    Raises:
        ValueError: When param1 is empty
        FileNotFoundError: When file doesn't exist

    Example:
        >>> result = function_name("test", 123)
        >>> print(result)
        True
    """
    ...
```

**Markdown formatting**:
- Use headings (`#`, `##`, `###`)
- Use code blocks with language hints (\`\`\`python)
- Use lists for steps or requirements
- Include examples and screenshots when helpful

---

## Issue Reporting

### Before Opening an Issue

1. **Search existing issues** to avoid duplicates
2. **Check documentation** to ensure it's not a usage question
3. **Reproduce the issue** with minimal example

### Bug Report Template

```markdown
**Description**
Clear description of the bug (1-2 sentences)

**Steps to Reproduce**
1. Step 1
2. Step 2
3. See error

**Expected Behavior**
What should happen

**Actual Behavior**
What actually happens

**Environment**
- OS: macOS 14.1
- Python: 3.11.5
- autoD version: 1.0.0

**Logs**
```
Paste relevant logs here
```

**Additional Context**
Any other relevant information
```

### Issue Labels

- `bug` - Something isn't working
- `feature` - New feature request
- `documentation` - Documentation improvements
- `good first issue` - Good for newcomers
- `help wanted` - Extra attention needed
- `question` - Further information requested
- `wontfix` - This won't be worked on

---

## Feature Requests

### Before Requesting a Feature

1. **Check existing issues** for similar requests
2. **Consider if it aligns** with project goals
3. **Think about implementation** complexity

### Feature Request Template

```markdown
**Problem**
What problem does this feature solve? (user story format preferred)
"As a [user type], I want [goal] so that [benefit]."

**Proposed Solution**
How should this feature work?

**Alternatives Considered**
What other approaches did you consider?

**Additional Context**
Any other relevant information, mockups, or examples
```

---

## Community Guidelines

### Getting Help

**Channels**:
- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and discussions
- **Documentation**: Check docs/ folder first

**When asking questions**:
- Be specific and provide context
- Include relevant code snippets
- Share error messages and logs
- Describe what you've tried

### Helping Others

- Answer questions respectfully
- Point to relevant documentation
- Provide code examples
- Share your experience

### Recognition

We appreciate all contributions! Contributors are recognized:
- In release notes
- In CONTRIBUTORS.md file
- On project website (if applicable)

---

## Quick Reference

### Common Commands

```bash
# Setup
git clone git@github.com:[your-username]/autoD.git
cd autoD
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Development
git checkout -b feature/my-feature
# ... make changes ...
pytest --cov=src --cov-fail-under=80
black src/ tests/
isort src/ tests/
mypy src/
git commit -m "feat: add my feature"
git push origin feature/my-feature

# Sync with upstream
git fetch upstream
git rebase upstream/develop

# Run quality checks
pytest --cov=src --cov-report=html
black src/ tests/ --check
isort src/ tests/ --check-only
mypy src/
flake8 src/ tests/
```

### Resources

- **Documentation**: `docs/` folder
- **Code Architecture**: `docs/CODE_ARCHITECTURE.md`
- **Testing Guide**: `docs/TESTING_GUIDE.md`
- **Troubleshooting**: `docs/TROUBLESHOOTING.md`
- **API Reference**: `docs/API_DOCS.md`

---

## Thank You!

Thank you for contributing to autoD! Your time and expertise help make this project better for everyone.

If you have questions about contributing, please open a GitHub Discussion or contact the maintainers.

---

**Last Updated**: 2025-10-16
**Maintained By**: Platform Engineering Team
**Reviewed**: Quarterly
