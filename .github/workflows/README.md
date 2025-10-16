# GitHub Actions Workflows

This directory contains CI/CD workflows for the autoD project.

## Workflows

### `ci.yml` - Continuous Integration
**Triggers:** Push/PR to main, develop, integration/*

**Jobs:**
- **test**: Runs tests across Python 3.9, 3.10, 3.11
  - Linting with black
  - Full test suite with coverage
  - Coverage upload to Codecov
  - Week 1 modules coverage threshold (75%+)

- **quality-gates**: Additional quality checks
  - Deployment validation tests
  - Security scanning with safety
  - Type checking with mypy

- **build**: Package building
  - Creates distribution packages
  - Uploads build artifacts

**Coverage Targets:**
- Week 1 modules (cost_calculator, retry_logic, pipeline, stages): 75%+
- Overall project: 37%+ (will increase as more modules are implemented)

### `pre-commit.yml` - Pre-commit Hooks
**Triggers:** Push/PR to main, develop, integration/*

Runs pre-commit hooks defined in `.pre-commit-config.yaml`:
- Code formatting checks
- Trailing whitespace removal
- End-of-file fixes
- YAML validation

### `nightly.yml` - Nightly Tests
**Triggers:** Scheduled (2 AM UTC), manual dispatch

**Jobs:**
- Comprehensive test suite with detailed coverage reports
- Dependency vulnerability scanning with pip-audit
- Performance benchmarks
- Creates GitHub issues on failure

**Artifacts:**
- HTML coverage reports (30-day retention)

### `release.yml` - Release Management
**Triggers:** Git tags (v*.*.*), manual dispatch

**Jobs:**
- **validate-release**: Pre-release validation
  - Full test suite
  - Deployment smoke tests
  - Version consistency checks

- **build-and-publish**: Package building and publishing
  - PyPI publication
  - GitHub Release creation

- **deploy-to-staging**: Staging deployment
  - Deploys to staging environment
  - Runs smoke tests

- **deploy-to-production**: Production deployment
  - Requires staging approval
  - Deploys to production
  - Runs production smoke tests

## Required Secrets

Configure these in GitHub repository settings:

### API Keys (per environment)
- `OPENAI_API_KEY_TEST` - Testing environment (mock/test API)
- `OPENAI_API_KEY_STAGING` - Staging environment
- `OPENAI_API_KEY_PROD` - Production environment

### Publishing
- `PYPI_API_TOKEN` - PyPI publishing token (if publishing to PyPI)

### Deployment (if using)
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` - AWS credentials
- `GCP_SA_KEY` - GCP service account key
- Or configure OIDC for keyless authentication

## Environment Protection Rules

Set up environment protection rules in GitHub:

### Staging
- No approval required
- Auto-deploy on successful build

### Production
- **Required reviewers**: 1-2 reviewers
- **Wait timer**: Optional 5-minute delay
- **Deployment branches**: Only `main` branch

## Local Testing

Test GitHub Actions workflows locally using `act`:

```bash
# Install act
brew install act

# Test CI workflow
act -j test

# Test with secrets
act -j test --secret-file .secrets

# Test specific event
act pull_request -j test
```

## Monitoring

### Workflow Status
- View workflow runs: https://github.com/krisstudio/autoD/actions
- Set up notifications for workflow failures

### Coverage Trends
- View coverage reports on Codecov: https://codecov.io/gh/krisstudio/autoD
- Monitor coverage changes over time

### Dependency Updates
- Dependabot PRs appear weekly on Mondays
- Review and merge dependency updates promptly

## Debugging Workflows

### Enable debug logging
Add these secrets to repository:
- `ACTIONS_STEP_DEBUG` = `true`
- `ACTIONS_RUNNER_DEBUG` = `true`

### Re-run failed jobs
Click "Re-run failed jobs" in the Actions UI

### Download artifacts
Access build artifacts and coverage reports from workflow run page

## Best Practices

1. **Always run tests locally before pushing**
   ```bash
   pytest --cov=src -v
   black --check src/ tests/
   pre-commit run --all-files
   ```

2. **Use feature branches with PRs**
   - Create feature branch from `develop`
   - Open PR to `develop` for review
   - Merge to `main` for releases

3. **Tag releases properly**
   ```bash
   git tag -a v1.0.0 -m "Release version 1.0.0"
   git push origin v1.0.0
   ```

4. **Monitor nightly test failures**
   - Review nightly test results daily
   - Address failures promptly

5. **Keep dependencies updated**
   - Review Dependabot PRs weekly
   - Test dependency updates in CI before merging

## Workflow Evolution

As the project grows, consider adding:
- Integration tests with real API calls (separate workflow)
- Performance regression testing
- Load testing workflows
- Docker image building and publishing
- Kubernetes deployment workflows
- Multi-region deployment support
