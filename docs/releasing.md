# Releasing to PyPI

This document explains how to release new versions of `gmail-ai-unsub` to PyPI.

## Prerequisites

### GitHub Secrets

The release workflow requires the following secrets to be configured in GitHub:

1. **`BUILD_GMAIL_CLIENT_ID`**: Google OAuth client ID for embedding in PyPI wheels
2. **`BUILD_GMAIL_CLIENT_SECRET`**: Google OAuth client secret for embedding in PyPI wheels
3. **`PYPI_API_TOKEN`** (optional): PyPI API token for manual releases via workflow_dispatch
   - Only needed if not using PyPI Trusted Publishing
   - Get from https://pypi.org/manage/account/token/

### PyPI Trusted Publishing (Recommended)

For automatic releases via GitHub releases, set up PyPI Trusted Publishing:

1. Go to your PyPI project settings: https://pypi.org/manage/project/gmail-ai-unsub/settings/
2. Navigate to "Publishing" → "Add a new pending publisher"
3. Configure:
   - **PyPI project name**: `gmail-ai-unsub`
   - **Owner**: Your GitHub username/organization
   - **Repository name**: `gmail-ai-unsub`
   - **Workflow filename**: `.github/workflows/release.yml`
4. Click "Add"
5. Approve the pending publisher

This allows the workflow to publish without storing API tokens.

## Release Process

### Option 1: GitHub Release (Recommended)

1. **Update version in `pyproject.toml`**:
   ```toml
   version = "0.1.0"
   ```

2. **Commit and push**:
   ```bash
   git add pyproject.toml
   git commit -m "Bump version to 0.1.0"
   git push
   ```

3. **Create a GitHub Release**:
   - Go to https://github.com/yourusername/gmail-ai-unsub/releases/new
   - Create a new tag (e.g., `v0.1.0`)
   - Fill in release notes
   - Click "Publish release"

4. **The workflow will automatically**:
   - Extract version from the tag
   - Inject OAuth credentials
   - Build the wheel
   - Publish to PyPI using Trusted Publishing

### Option 2: Manual Workflow Dispatch

1. **Update version in `pyproject.toml`** (same as above)

2. **Trigger workflow manually**:
   - Go to Actions → "Release to PyPI"
   - Click "Run workflow"
   - Enter the version (e.g., `0.1.0`)
   - Click "Run workflow"

3. **The workflow will**:
   - Use the provided version
   - Inject OAuth credentials
   - Build the wheel
   - Publish to PyPI using API token

## What Gets Built

The release workflow:

1. **Injects OAuth credentials** from GitHub secrets into `src/gmail_ai_unsub/gmail/auth.py`
2. **Builds the wheel** using `uv build`
3. **Publishes to PyPI** (either via Trusted Publishing or API token)
4. **Reverts credential changes** (so they're not committed)

The built wheel contains:
- All source code with OAuth credentials embedded
- All dependencies (as specified in `pyproject.toml`)
- Ready to install via `pip install gmail-ai-unsub`

## Versioning

Follow [Semantic Versioning](https://semver.org/):
- **MAJOR.MINOR.PATCH** (e.g., `1.0.0`)
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

Tag format: `v0.1.0` (with `v` prefix) - the workflow automatically strips it.

## Testing the Build

Before releasing, you can test the build process:

1. **Locally**:
   ```bash
   BUILD_GMAIL_CLIENT_ID=your-id BUILD_GMAIL_CLIENT_SECRET=your-secret ./scripts/build-with-credentials.sh
   ```

2. **Via GitHub Actions**:
   - The `build-test.yml` workflow runs on pull requests
   - It builds the wheel without publishing
   - Useful for verifying the build process works

## Troubleshooting

### "BUILD_GMAIL_CLIENT_ID not set"

- Make sure the secrets are configured in GitHub Settings → Secrets and variables → Actions
- Secrets are only available to workflows, not to forks

### "Failed to publish to PyPI"

- Check that PyPI Trusted Publishing is configured correctly
- Verify the workflow filename matches exactly
- For API token method, ensure `PYPI_API_TOKEN` secret is set

### "Version already exists on PyPI"

- PyPI doesn't allow re-uploading the same version
- Either bump the version or delete the existing release (if it's a test release)

### Credentials not in wheel

- Check that the inject-credentials script ran successfully
- Verify the secrets are set correctly
- Check the workflow logs for any errors

## Post-Release

After a successful release:

1. **Verify on PyPI**: https://pypi.org/project/gmail-ai-unsub/
2. **Test installation**:
   ```bash
   pip install --upgrade gmail-ai-unsub
   ```
3. **Update documentation** if needed
4. **Announce the release** (GitHub release notes, etc.)
