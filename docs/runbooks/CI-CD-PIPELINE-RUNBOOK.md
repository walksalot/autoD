# CI/CD Pipeline Runbook

**Last Updated:** 2025-10-16
**Maintainer:** DevOps Team
**Related:** ADR-023 (Technical Debt Reduction)

---

## Overview

This runbook provides operational procedures for the GitHub Actions CI/CD pipeline implemented as part of the technical debt reduction program (ADR-023, Phase 1).

**Pipeline Components:**
- `.github/workflows/ci.yml` - Main CI pipeline (tests, linting, coverage)
- `.github/workflows/pre-commit.yml` - Pre-commit hook validation
- `.github/workflows/nightly.yml` - Extended nightly builds
- `.github/workflows/release.yml` - Automated release workflow

---

## Running Tests Locally

### Prerequisites

```bash
# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Verify pytest installation
pytest --version
# Expected: pytest 7.4.0 or newer
```

### Basic Test Execution

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_dedupe.py

# Run specific test function
pytest tests/test_retry_logic.py::test_rate_limit_is_retryable

# Run tests matching pattern
pytest -k "test_api"
```

### Test Coverage

```bash
# Run tests with coverage report
pytest --cov=src --cov-report=term-missing

# Generate HTML coverage report
pytest --cov=src --cov-report=html

# View HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux

# Generate JSON report for CI
pytest --cov=src --cov-report=json

# Fail if coverage below threshold
pytest --cov=src --cov-fail-under=70
```

### Example Output

```bash
$ pytest --cov=src --cov-report=term-missing

================================== test session starts ==================================
platform darwin -- Python 3.11.5, pytest-7.4.0, pluggy-1.3.0
rootdir: /Users/krisstudio/Developer/Projects/autoD
plugins: cov-4.1.0, mock-3.12.0, hypothesis-6.92.0
collected 70 items

tests/test_config.py ........................                                     [ 34%]
tests/test_dedupe.py ......................                                       [ 65%]
tests/test_processor.py ..........                                                [100%]

---------- coverage: platform darwin, python 3.11.5-final-0 ----------
Name                          Stmts   Miss  Cover   Missing
-----------------------------------------------------------
src/__init__.py                   1      0   100%
src/config.py                   124      8    94%   67-71, 145-148
src/database.py                  87      5    94%   123-127
src/dedupe.py                    95      4    96%   78-81
src/models.py                   142      0   100%
src/processor.py                 156     22    86%   189-195, 234-241
src/prompts.py                  128      6    95%   234-239
src/retry_logic.py               67      3    96%   45-47
src/vector_store.py             102     12    88%   145-156
-----------------------------------------------------------
TOTAL                           902     60    93%

================================== 70 passed in 3.24s ===================================
```

---

## Interpreting Coverage Reports

### Coverage Metrics

**Overall Coverage:** Percentage of lines executed during tests
- **Excellent:** >90%
- **Good:** 80-90%
- **Acceptable:** 70-80%
- **Needs Attention:** <70%

**Statement Coverage:** Lines of code executed
**Branch Coverage:** Conditional paths (if/else) taken
**Function Coverage:** Functions called during tests

### Reading HTML Reports

```bash
# Open coverage report
open htmlcov/index.html

# Navigate to specific file (e.g., src/processor.py)
# Click filename in index

# Color coding:
# Green: Covered lines
# Red: Uncovered lines
# Yellow: Partial branch coverage
```

### Identifying Gaps

**Example report analysis:**

```
Name                Coverage    Missing Lines
--------------------------------------------
src/processor.py    86%         189-195, 234-241
```

**Interpretation:**
- Lines 189-195: Error handling path (7 lines)
- Lines 234-241: Vector store upload failure (8 lines)

**Action:** Write integration test for vector store failure scenario

### Coverage Thresholds

**CI Pipeline Enforcement:**
```yaml
# .github/workflows/ci.yml
- name: Test Coverage
  run: pytest --cov=src --cov-fail-under=70
```

**Threshold Values:**
- **Global minimum:** 70% (enforced in CI)
- **New code:** 80% (enforced in PR reviews)
- **Critical paths:** 100% (payment processing, security)

---

## Handling Failing CI Checks

### Workflow: CI Check Failed

1. **View failure details**
   ```bash
   # In GitHub PR, click "Details" next to failing check
   # Or view locally:
   git push origin feature-branch
   # Watch Actions tab in GitHub repo
   ```

2. **Reproduce failure locally**
   ```bash
   # Run same commands as CI
   pytest --cov=src --cov-fail-under=70
   black --check src/ tests/
   ruff check src/ tests/
   mypy src/
   ```

3. **Fix issues**
   ```bash
   # Auto-fix formatting
   black src/ tests/

   # Auto-fix linting
   ruff check --fix src/ tests/

   # Fix type errors (manual)
   # mypy will show error locations
   mypy src/
   ```

4. **Verify fixes**
   ```bash
   # Run full CI suite locally
   pytest --cov=src --cov-fail-under=70 && \
   black --check src/ tests/ && \
   ruff check src/ tests/ && \
   mypy src/
   ```

5. **Push fixes**
   ```bash
   git add -A
   git commit -m "fix: resolve CI failures (formatting, linting, type errors)"
   git push origin feature-branch
   ```

### Common CI Failures

#### 1. Test Failures

**Symptom:**
```
FAILED tests/test_processor.py::test_process_document - AssertionError
```

**Diagnosis:**
```bash
# Run failing test with verbose output
pytest tests/test_processor.py::test_process_document -vv

# Run with debug output
pytest tests/test_processor.py::test_process_document -vv --log-cli-level=DEBUG
```

**Resolution:**
- Check test assertions vs. actual output
- Verify test fixtures are correct
- Update test if behavior intentionally changed
- Fix code if test correctly identifies bug

#### 2. Code Formatting Failures

**Symptom:**
```
would reformat src/processor.py
Oh no! 💥 💔 💥
1 file would be reformatted.
```

**Diagnosis:**
```bash
# Show what would be reformatted
black --check --diff src/
```

**Resolution:**
```bash
# Auto-fix formatting
black src/ tests/

# Verify
black --check src/ tests/

# Commit
git add -A
git commit -m "style: apply black formatting"
```

#### 3. Linting Failures

**Symptom:**
```
src/processor.py:45:1: F401 [*] `typing.List` imported but unused
```

**Diagnosis:**
```bash
# View all linting errors
ruff check src/
```

**Resolution:**
```bash
# Auto-fix safe issues
ruff check --fix src/

# Manually fix remaining issues
# (F401 = remove unused import)

# Verify
ruff check src/
```

#### 4. Type Checking Failures

**Symptom:**
```
src/processor.py:67: error: Argument 1 to "process" has incompatible type "str"; expected "Path"
```

**Diagnosis:**
```bash
# Run mypy with detailed output
mypy --show-error-codes src/
```

**Resolution:**
```python
# Fix type mismatch
from pathlib import Path

# Before (incorrect)
def process_document(pdf_path: str) -> ProcessingResult:
    result = pipeline.process(pdf_path)  # Type error

# After (correct)
def process_document(pdf_path: Path) -> ProcessingResult:
    result = pipeline.process(pdf_path)  # Type safe
```

#### 5. Coverage Failures

**Symptom:**
```
FAIL Required test coverage of 70% not reached. Total coverage: 68.42%
```

**Diagnosis:**
```bash
# Generate HTML coverage report
pytest --cov=src --cov-report=html
open htmlcov/index.html

# Identify uncovered lines
pytest --cov=src --cov-report=term-missing
```

**Resolution:**
```python
# Add tests for uncovered lines
# Example: tests/test_processor.py

def test_vector_store_upload_failure(mock_vector_store, db_session):
    """Test graceful handling of vector store upload failures."""
    # Simulate upload failure
    mock_vector_store.add_file.side_effect = Exception("Upload failed")

    # Process should continue (best-effort pattern)
    result = process_document(sample_pdf, db_session)

    # Document saved to DB even if vector store fails
    assert result.status == "completed"
    assert result.vector_store_file_id is None  # Upload failed, ID not set
```

---

## Updating Quality Thresholds

### When to Adjust Thresholds

**Increase thresholds when:**
- Coverage consistently exceeds current threshold by 10%+
- Team agrees on stricter quality standards
- Post-incident analysis reveals gaps

**Decrease thresholds when:**
- Legacy codebase with <50% coverage (gradual improvement plan)
- Threshold blocking critical hotfixes
- Temporary regression acceptable (requires approval)

### How to Update Thresholds

#### 1. Coverage Threshold

**File:** `.github/workflows/ci.yml`

```yaml
# Before
- name: Test Coverage
  run: pytest --cov=src --cov-fail-under=70

# After (increase to 75%)
- name: Test Coverage
  run: pytest --cov=src --cov-fail-under=75
```

#### 2. Complexity Threshold

**File:** `.github/workflows/ci.yml`

```yaml
# Add complexity check
- name: Complexity Check
  run: radon cc src/ --min B  # B = complexity ≤10

# Stricter threshold
- name: Complexity Check
  run: radon cc src/ --min A  # A = complexity ≤5
```

#### 3. Type Checking Strictness

**File:** `.pre-commit-config.yaml`

```yaml
# Before (lenient)
- repo: https://github.com/pre-commit/mirrors-mypy
  hooks:
    - id: mypy
      args: [--ignore-missing-imports]

# After (strict)
- repo: https://github.com/pre-commit/mirrors-mypy
  hooks:
    - id: mypy
      args: [--strict, --warn-unused-ignores]
```

#### 4. Linting Rules

**File:** `pyproject.toml`

```toml
[tool.ruff]
select = [
    "E",   # pycodestyle errors
    "F",   # pyflakes
    "I",   # isort
    "N",   # pep8-naming
    "UP",  # pyupgrade
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
]

# Add stricter rules
select = [
    "E", "F", "I", "N", "UP", "B", "C4",
    "S",   # flake8-bandit (security)
    "T20", # flake8-print (no print statements)
]
```

### Communication Protocol

**Before updating thresholds:**
1. Announce change in team meeting
2. Document rationale in ADR
3. Provide 1-week grace period
4. Update CI/CD configuration
5. Monitor first 3 PRs for issues

**Example ADR:**
```markdown
# ADR-030: Increase Coverage Threshold to 75%

## Context
Current coverage: 78% (consistently 8% above 70% threshold)
Team velocity stable, debt score improving

## Decision
Increase coverage threshold from 70% to 75% effective 2025-11-01

## Consequences
- Higher quality bar for new code
- Existing code grandfathered (no immediate action required)
- PR authors must add tests to meet new threshold
```

---

## Troubleshooting Guide

### Issue: CI Pipeline Slow (>10 minutes)

**Diagnosis:**
```bash
# Check workflow run times
# GitHub Actions → View workflow run → Timing breakdown
```

**Common Causes:**
1. **Large test suite** - Consider test parallelization
2. **Slow tests** - Identify with `pytest --durations=10`
3. **Matrix builds** - Running 4 Python versions (3.9-3.12)

**Resolution:**
```yaml
# Parallelize tests
- name: Run Tests
  run: pytest -n auto  # Uses pytest-xdist

# Cache dependencies
- uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements*.txt') }}
```

### Issue: Flaky Tests (Intermittent Failures)

**Diagnosis:**
```bash
# Run test 10 times
pytest tests/test_api_client.py::test_retry_logic --count=10

# Identify flaky tests
pytest --lf  # Rerun last failures
```

**Common Causes:**
1. **Race conditions** - Use proper mocking for async code
2. **Time-dependent tests** - Use freezegun for datetime mocking
3. **External dependencies** - Mock API calls, file system

**Resolution:**
```python
# Before (flaky)
import time

def test_timeout():
    start = time.time()
    process_with_timeout()
    assert time.time() - start < 5.0  # Fails on slow CI runners

# After (stable)
from unittest.mock import patch

def test_timeout(mocker):
    mock_sleep = mocker.patch('time.sleep')
    process_with_timeout()
    mock_sleep.assert_called_once_with(5)  # Verify timeout set correctly
```

### Issue: Pre-commit Hooks Failing Locally

**Diagnosis:**
```bash
# Run pre-commit manually
pre-commit run --all-files

# Update hooks to latest versions
pre-commit autoupdate
```

**Resolution:**
```bash
# Reinstall hooks
pre-commit uninstall
pre-commit install

# Clear cache
pre-commit clean

# Run again
pre-commit run --all-files
```

### Issue: Coverage Report Not Uploading to Codecov

**Diagnosis:**
```bash
# Check CI logs for Codecov upload errors
# GitHub Actions → View workflow → Coverage Upload step
```

**Resolution:**
```yaml
# Ensure CODECOV_TOKEN secret is set
# GitHub repo → Settings → Secrets → Actions → CODECOV_TOKEN

# Workflow configuration
- name: Upload Coverage
  uses: codecov/codecov-action@v3
  with:
    token: ${{ secrets.CODECOV_TOKEN }}
    files: ./coverage.json
    fail_ci_if_error: true  # Fail if upload fails
```

---

## Emergency Procedures

### Bypass CI for Hotfix

**When to use:** Critical production issue requiring immediate fix

**Procedure:**
```bash
# 1. Create hotfix branch from main
git checkout main
git pull origin main
git checkout -b hotfix/critical-auth-fix

# 2. Make minimal fix
# Edit files...

# 3. Commit with [skip ci] tag
git commit -m "hotfix: fix critical auth bypass [skip ci]"

# 4. Push directly to main (requires admin rights)
git push origin hotfix/critical-auth-fix

# 5. Create PR for review (post-facto)
# Merge with "Create merge commit" to preserve [skip ci]

# 6. Document incident
# Create post-mortem in docs/incidents/YYYY-MM-DD-auth-bypass.md
```

**Follow-up actions (within 24 hours):**
1. Run tests manually: `pytest --cov=src`
2. Create tracking issue for CI improvement
3. Add regression test to prevent recurrence
4. Update runbook with lessons learned

### Rollback Failed Deployment

**Scenario:** CI passed but production deployment failed

**Procedure:**
```bash
# 1. Identify last known good commit
git log --oneline -10

# 2. Revert to last good commit
git revert <bad-commit-sha>

# 3. Push revert
git push origin main

# 4. CI will run on revert commit
# 5. Deploy reverted version to production

# 6. Debug original issue in separate branch
git checkout -b fix/investigate-deployment-failure
```

---

## Maintenance

### Weekly Tasks

- [ ] Review CI pipeline success rate (target: >95%)
- [ ] Check for outdated dependencies (Dependabot PRs)
- [ ] Monitor coverage trend (should increase over time)
- [ ] Review flaky test reports

### Monthly Tasks

- [ ] Update pre-commit hook versions (`pre-commit autoupdate`)
- [ ] Review and adjust quality thresholds if needed
- [ ] Archive old workflow runs (keep last 90 days)
- [ ] Update this runbook with new learnings

### Quarterly Tasks

- [ ] Audit CI/CD costs (GitHub Actions minutes)
- [ ] Review security scan findings (Dependabot, Snyk)
- [ ] Update CI/CD roadmap based on team feedback
- [ ] Benchmark pipeline performance (compare to industry standards)

---

## Metrics & Monitoring

### Key Performance Indicators

**CI Pipeline Health:**
- Success rate: >95%
- Average duration: <5 minutes
- Flaky test rate: <1%

**Code Quality:**
- Test coverage: >70% (trending toward 80%)
- Complexity: <10 average cyclomatic
- Linting violations: 0

**Developer Experience:**
- PR merge time: <24 hours
- Build failures due to environment: <5%
- Pre-commit hook failures: <10%

### Dashboard

**View in GitHub:**
1. Actions tab → CI workflow
2. Insights → Dependency graph → Dependabot
3. Settings → Branches → Branch protection rules

**Local monitoring:**
```bash
# Generate coverage badge
coverage-badge -o coverage.svg

# View test trends
pytest --cov=src --cov-report=json
# Parse coverage.json for historical tracking
```

---

## References

**Internal:**
- ADR-023: Technical Debt Reduction Investment
- `/Users/krisstudio/Developer/Projects/autoD/docs/TECHNICAL_DEBT_ANALYSIS.md`
- `/Users/krisstudio/Developer/Projects/autoD/.github/workflows/ci.yml`

**External:**
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [pytest Documentation](https://docs.pytest.org/)
- [pre-commit Framework](https://pre-commit.com/)
- [Codecov Documentation](https://docs.codecov.com/)

---

**Contact:** DevOps Team
**On-Call:** Check #devops-oncall Slack channel
**Escalation:** Page DevOps lead via PagerDuty
