# Setup Guide

This guide walks you through setting up Gmail AI Unsubscribe Tool from scratch.

## Prerequisites

- Python 3.12 or higher
- A Gmail account
- An API key for your chosen LLM provider (Gemini, Anthropic, or OpenAI)

## Step 1: Install the Tool

### Using uv (Recommended)

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/yourusername/gmail-ai-unsub.git
cd gmail-ai-unsub
uv pip install -e .
```

### Using pip

```bash
pip install gmail-ai-unsub
```

## Step 2: Run the Setup Wizard

The easiest way to get started is to run the interactive setup wizard:

```bash
gmail-unsub setup
```

This will:
1. Create a configuration file with your LLM settings
2. Authenticate with Gmail (opens a browser window)
3. Set up the necessary directories

**OAuth Credentials**: The tool includes embedded OAuth credentials for easy setup, so you don't need to create your own Google Cloud project for basic usage. However, you will see an "unverified app" warning during authentication.

For production use or to avoid the warning, see [Advanced: Using Your Own OAuth Credentials](#advanced-using-your-own-oauth-credentials) below to create your own OAuth app.

## Step 3: Set Your LLM API Key

Set the API key for your chosen LLM provider:

```bash
# For Google Gemini
export GOOGLE_API_KEY=your_api_key_here

# For Anthropic Claude
export ANTHROPIC_API_KEY=your_api_key_here

# For OpenAI
export OPENAI_API_KEY=your_api_key_here
```

That's it! You're ready to start scanning emails:

```bash
gmail-unsub scan --days 30
```

---

## Advanced: Using Your Own OAuth Credentials

If you prefer to use your own Google Cloud OAuth app (recommended for production use or to avoid the "unverified app" warning), follow these detailed steps:

> **Quick Reference**: See the [Developer Setup section in README](../README.md#developer-setup) for step-by-step instructions with screenshots guidance.

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Enter a project name (e.g., "Gmail Unsubscribe Tool")
4. Click "Create"

### Step 2: Enable Gmail API

1. In your project, go to **APIs & Services** → **Library**
2. Search for "Gmail API"
3. Click on "Gmail API" and click **Enable**

### Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Choose **External** (unless you have a Google Workspace account)
3. Fill in the required information:
   - **App name**: Gmail AI Unsubscribe Tool (or your choice)
   - **User support email**: Your email
   - **Developer contact information**: Your email
4. Click **Save and Continue**
5. **Scopes**: Click "Add or Remove Scopes" and add:
   - `https://www.googleapis.com/auth/gmail.readonly` - Read emails and metadata
   - `https://www.googleapis.com/auth/gmail.modify` - Manage labels
   - `https://www.googleapis.com/auth/gmail.send` - Send unsubscribe emails
6. Click **Save and Continue**
7. **Test users**: Add your Google account email(s) as test users
   - This allows you to use the app while it's in "Testing" mode
   - Click **Add Users** and enter your email
   - You can add multiple test users
8. Click **Save and Continue**
9. Review and click **Back to Dashboard**

### Step 4: Create OAuth 2.0 Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. If prompted, configure the consent screen (you should have done this in Step 3)
4. Choose **Application type**: **Desktop app**
5. Enter a name (e.g., "Gmail Unsubscribe Desktop Client")
6. Click **Create**
7. **Important**: Copy the **Client ID** and **Client Secret** (you'll need these)
8. Click **OK**

### Step 5: Download Credentials File

1. In the Credentials page, find your OAuth 2.0 Client ID
2. Click the download icon (⬇️) to download `client_secret_*.json`
3. Rename it to `credentials.json`

### Step 6: Use Credentials with the Tool

**Option A: Use with setup wizard**

1. Place `credentials.json` in your config directory:
   ```bash
   # Default locations:
   # Linux:   ~/.config/gmail-ai-unsub/
   # macOS:   ~/Library/Application Support/gmail-ai-unsub/
   # Windows: %LOCALAPPDATA%\gmail-ai-unsub\gmail-ai-unsub\
   ```
2. Run `gmail-unsub setup` and specify the path when prompted

**Option B: Specify in config.toml**

```toml
[gmail]
credentials_file = "/path/to/credentials.json"
```

**Option C: Use environment variables (for development)**

Create a `.env` file in the project root:
```bash
GMAIL_CLIENT_ID=your-client-id.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=your-client-secret
```

### Important Notes

- **Testing Mode**: Your app starts in "Testing" mode. Only test users you added can use it.
- **Unverified App Warning**: Users will see "This app isn't verified" - this is normal for unverified apps.
- **Production Use**: To remove the warning, you need to complete app verification (requires domain, privacy policy, etc.). For Gmail scopes, this may require a CASA security assessment. See [docs/oauth-credentials.md](oauth-credentials.md) for details.
- **Rate Limits**: Testing mode has lower rate limits. For production, consider app verification.

For more details on OAuth credential management, see [docs/oauth-credentials.md](oauth-credentials.md).

### Install Playwright Browsers

The browser automation requires Playwright:

```bash
playwright install chromium
```

Or if using uv:

```bash
uv pip install playwright
playwright install chromium
```

---

## Gmail API Scopes

The tool requests the following Gmail API scopes:

| Scope | Purpose |
|-------|---------|
| `gmail.readonly` | Read your email messages to classify them |
| `gmail.modify` | Add/remove labels on emails |
| `gmail.send` | Send unsubscribe emails (for `mailto:` links) |

Your credentials are stored locally and never sent to any external server.

For more details, see [Google's OAuth 2.0 documentation](https://developers.google.com/identity/protocols/oauth2).

---

## Getting LLM API Keys

The setup wizard (`gmail-unsub setup`) will guide you through getting API keys, but here's how to get them manually:

### Option A: Google Gemini (Recommended)

1. Go to [Google AI Studio](https://aistudio.google.com/api-keys)
2. Click **Create API Key**
3. Copy the API key
4. Use in setup wizard or set environment variable:

```bash
export GOOGLE_API_KEY=your_api_key_here
```

### Option B: Anthropic Claude

1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Navigate to **API Keys**
3. Create an API key
4. Use in setup wizard or set environment variable:

```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

### Option C: OpenAI

1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create an API key
3. Use in setup wizard or set environment variable:

```bash
export OPENAI_API_KEY=your_api_key_here
```

**Note**: The setup wizard can detect these environment variables and pre-fill them for you.

## Step 4: Create Configuration File

1. Copy the example config:

```bash
cp config.example.toml config.toml
```

2. Edit `config.toml`:

```toml
[gmail]
# credentials_file is optional - if not set, uses embedded credentials
# credentials_file = "/path/to/credentials.json"  # Use your own OAuth app
# token_file is auto-generated in platform-specific location

[llm]
provider = "google"                    # or "anthropic" or "openai"
model = "gemini-2.5-flash"            # Fast model (recommended)
api_key = "your-api-key-here"         # Or use api_key_env
# api_key_env = "GOOGLE_API_KEY"       # Alternative: use env var

[labels]
marketing = "Unsubscribe"             # Label for emails to unsubscribe
unsubscribed = "Unsubscribed"          # Applied after successful unsubscribe
failed = "Unsubscribe-Failed"         # Applied if unsubscribe fails

[prompts]
# Customize these to match your preferences
user_preferences = "Keep podcast episodes, NPR newsletters, etc."
```

## Step 5: First Run

1. **Authenticate with Gmail**:

```bash
gmail-unsub scan --days 7
```

This will:
- Open a browser for OAuth authentication
- Save the token for future use
- Scan your last 7 days of emails

2. **Review labeled emails** in Gmail to verify classification

3. **Unsubscribe**:

```bash
gmail-unsub unsubscribe
```

## Troubleshooting

### "Credentials file not found"

- Make sure `credentials.json` is in the current directory or update the path in `config.toml`
- Verify the file was downloaded correctly from Google Cloud Console

### "API key not found in environment variable"

- Make sure you've exported the environment variable in your shell
- Check the variable name matches `api_key_env` in your config
- For persistent setup, add to your `~/.bashrc` or `~/.zshrc`:

```bash
export GOOGLE_API_KEY=your_key_here
```

### "Rate limit exceeded"

- Gmail API has rate limits (15,000 quota units per minute per user)
- The tool implements exponential backoff automatically
- If you hit limits frequently, reduce the number of emails processed at once

### Browser automation fails

- Make sure Playwright browsers are installed: `playwright install chromium`
- Try running with `--no-headless` to see what's happening
- Some unsubscribe pages may have CAPTCHAs or require manual intervention

### OAuth consent screen issues

- **"Access blocked"**: Make sure you added yourself as a test user in the OAuth consent screen configuration (Step 3 of [Advanced Setup](#advanced-using-your-own-oauth-credentials))
- **"This app isn't verified"**: This is normal for unverified apps. To remove it, you need to complete Google's app verification process (requires domain, privacy policy, etc.)
- **Using embedded credentials**: The tool's embedded credentials are in "Testing" mode. You'll need to contact the maintainer to be added as a test user, or create your own OAuth app
- For production use, you'd need to publish the app (requires verification and potentially CASA security assessment)
- For personal use, test user mode is sufficient

## Security Notes

- Never commit `credentials.json`, `token.json`, `config.toml`, or `.env` to version control
- These files are already in `.gitignore`
- Keep your API keys secure and rotate them if compromised
- The OAuth token grants access to your Gmail - keep it secure
- **Embedded OAuth Credentials**: The tool includes embedded OAuth credentials for convenience. For native/desktop apps, the client_secret is treated as public metadata - security comes from PKCE and user consent. For production use, consider creating your own OAuth app (see [Advanced Setup](#advanced-using-your-own-oauth-credentials))

## Next Steps

- Read [Configuration Guide](configuration.md) for advanced options
- See [Usage Examples](usage.md) for common workflows
- Customize prompts in `config.toml` to match your email preferences
