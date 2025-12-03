# OAuth Credentials Management

This document explains how OAuth credentials are managed for open-source distribution.

## Overview

For open-source native/desktop apps, Google OAuth treats them as "public clients" where the client_secret cannot be kept truly secret. Security comes from PKCE and user consent, not from hiding the secret.

This app supports multiple ways to provide credentials:

1. **Environment variables** (development/CI) - `GMAIL_CLIENT_ID` and `GMAIL_CLIENT_SECRET`
2. **Embedded credentials** (PyPI wheels) - Injected at build time
3. **Custom credentials.json** - Users can provide their own OAuth app

## For Development

### Using .env file (recommended)

1. Create a `.env` file in the project root:
   ```bash
   GMAIL_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GMAIL_CLIENT_SECRET=your-client-secret
   ```

2. Load it in your shell:
   ```bash
   # Using python-dotenv (optional)
   pip install python-dotenv
   export $(cat .env | xargs)

   # Or manually
   source .env  # if your shell supports it
   ```

3. The `.env` file is gitignored and won't be committed.

### Using environment variables directly

```bash
export GMAIL_CLIENT_ID=your-client-id.apps.googleusercontent.com
export GMAIL_CLIENT_SECRET=your-client-secret
```

## For PyPI Builds

When building wheels for PyPI, credentials are injected into the source code at build time:

```bash
BUILD_GMAIL_CLIENT_ID=your-id BUILD_GMAIL_CLIENT_SECRET=your-secret ./scripts/build-with-credentials.sh
```

This:
1. Injects credentials into `src/gmail_ai_unsub/gmail/auth.py`
2. Builds the wheel with credentials embedded
3. Packages the wheel for distribution

**Important**: After building, the source code will contain the credentials. Consider reverting the changes before committing:

```bash
git checkout src/gmail_ai_unsub/gmail/auth.py
```

## For GitHub CI

Use GitHub Secrets to set credentials for CI builds:

1. Go to Settings → Secrets and variables → Actions
2. Add secrets:
   - `GMAIL_CLIENT_ID`
   - `GMAIL_CLIENT_SECRET`
3. In your workflow, use them:
   ```yaml
   env:
     GMAIL_CLIENT_ID: ${{ secrets.GMAIL_CLIENT_ID }}
     GMAIL_CLIENT_SECRET: ${{ secrets.GMAIL_CLIENT_SECRET }}
   ```

## For End Users

### Option 1: Use embedded credentials (default)

The PyPI wheels include embedded credentials. Users can install and use the tool directly:

```bash
pipx install gmail-ai-unsub
gmail-unsub setup
```

They will see the "unverified app" warning, which is expected for unverified OAuth apps.

### Option 2: Provide custom credentials

Users can create their own Google Cloud project and OAuth credentials:

1. Create a project at https://console.cloud.google.com
2. Enable Gmail API
3. Create OAuth 2.0 Desktop client credentials
4. Download `credentials.json`
5. Place it in the config directory or specify path in `config.toml`

This avoids the unverified app warning but requires more setup.

## Security Notes

- The client_secret in native apps is **not secret** - it's public metadata
- Security comes from:
  - PKCE (Proof Key for Code Exchange)
  - User consent (OAuth flow)
  - Minimal scopes requested
- Committing credentials to GitHub doesn't meaningfully reduce security for native apps
- For production, consider having users create their own OAuth apps

## References

- [Google OAuth for Native Apps](https://developers.google.com/identity/protocols/oauth2/native-app)
- [OAuth 2.0 for Mobile & Desktop Apps](https://oauth.net/2/native-apps/)
- [PKCE RFC 7636](https://tools.ietf.org/html/rfc7636)
