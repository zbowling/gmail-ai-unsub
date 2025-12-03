# Gmail AI Unsubscribe Tool

AI-powered tool to identify and automatically unsubscribe from marketing emails in Gmail using Large Language Models (LLMs) and browser automation.

**Website**: [zacbowling.com](https://zacbowling.com)

## Features

- **AI-Powered Classification**: Uses LLMs (Gemini, Claude, or OpenAI) to identify marketing emails with customizable prompts
- **Automatic Unsubscription**: Handles multiple unsubscribe methods:
  - RFC 8058 One-Click unsubscribe (HTTP POST)
  - Mailto unsubscribe (sends email)
  - Browser automation for complex unsubscribe pages (using AI vision models)
- **Gmail Integration**: Seamlessly integrates with Gmail API to label and manage emails
- **User Control**: Fully configurable prompts and criteria for email classification
- **State Tracking**: Tracks unsubscribe attempts and results

## Installation

### Prerequisites

- Python 3.12 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- **Gmail API credentials** - You must create your own OAuth app (see [Gmail API Setup](#gmail-api-setup-required) below)
- LLM API key (Gemini, Anthropic, or OpenAI)

### Install from Source

```bash
# Clone the repository
git clone https://github.com/yourusername/gmail-ai-unsub.git
cd gmail-ai-unsub

# Install using uv (recommended)
uv pip install -e .

# Or using pip
pip install -e .
```

### Install from PyPI (when published)

```bash
pip install gmail-ai-unsub
```

## Gmail API Setup (Required)

**Important**: This tool's OAuth app is not yet verified with Google, so **all users must create their own OAuth credentials** to use the tool. This is a one-time setup that takes about 10 minutes.

Follow the steps below to create your own Google Cloud OAuth app. This is required for the tool to access your Gmail account.

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
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.modify`
   - `https://www.googleapis.com/auth/gmail.send`
6. Click **Save and Continue**
7. **Test users**: Add your Google account email(s) as test users
   - This allows you to use the app while it's in "Testing" mode
   - Click **Add Users** and enter your email
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

**Option B: Use environment variables (for development)**

1. Create a `.env` file in the project root:
   ```bash
   GMAIL_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GMAIL_CLIENT_SECRET=your-client-secret
   ```
2. Load it before running:
   ```bash
   export $(cat .env | xargs)
   ```

**Option C: Specify in config.toml**

```toml
[gmail]
credentials_file = "/path/to/credentials.json"
```

### Important Notes

- **Testing Mode**: Your app starts in "Testing" mode. Only test users you added can use it.
- **Unverified App Warning**: Users will see "This app isn't verified" - this is normal for unverified apps.
- **Production Use**: To remove the warning, you need to:
  - Complete app verification (requires domain, privacy policy, etc.)
  - For Gmail scopes, this may require a CASA security assessment (expensive)
  - See [docs/oauth-credentials.md](docs/oauth-credentials.md) for details
- **Rate Limits**: Testing mode has lower rate limits. For production, consider app verification.

### Troubleshooting

- **"Access blocked"**: Make sure you added yourself as a test user in Step 3
- **"Invalid client"**: Check that you copied the Client ID and Secret correctly
- **"Redirect URI mismatch"**: Desktop app type uses `http://localhost` - this should work automatically

For more details, see [docs/oauth-credentials.md](docs/oauth-credentials.md).

## Quick Start

### Step 1: Set Up Gmail API Credentials (Required)

**You must create your own OAuth app** - the tool's app is not verified with Google yet. Follow the [Gmail API Setup](#gmail-api-setup-required) steps above to:
1. Create a Google Cloud project
2. Enable Gmail API
3. Configure OAuth consent screen
4. Create OAuth credentials
5. Download your `credentials.json` file

This is a one-time setup that takes about 10 minutes.

### Step 2: Interactive Setup

Run the setup wizard to create your configuration:

```bash
gmail-unsub setup
```

This will guide you through:
- Selecting your LLM provider (Gemini, Claude, or OpenAI)
- Choosing a model and configuring settings
- Setting up Gmail OAuth authentication (pointing to your `credentials.json`)
- Customizing labels and classification prompts

### Alternative: Manual Setup

1. **Set up Gmail API credentials** (required):
   - Follow the [Gmail API Setup](#gmail-api-setup-required) steps above
   - Download your `credentials.json` file
2. **Create a config file**:

```bash
cp config.example.toml ~/.gmail-ai-unsub/config.toml
# Edit config.toml with your API keys and preferences
```

3. **Set your LLM API key**:

```bash
export GOOGLE_API_KEY=your_gemini_api_key
# Or for Anthropic:
# export ANTHROPIC_API_KEY=your_key
```

### Running the Tool

4. **Scan your inbox**:

```bash
gmail-unsub scan --days 30
```

5. **Review labeled emails in Gmail**, then unsubscribe:

```bash
gmail-unsub unsubscribe
```

## Usage

### Initialize Configuration

Run the interactive setup wizard:

```bash
gmail-unsub setup
```

Options:
- `--force`: Overwrite existing config file

### Scan Emails

Scan your inbox and label emails for unsubscription:

```bash
gmail-unsub scan --days 30 --label "Unsubscribe"
```

The AI will analyze your emails and apply the "Unsubscribe" label to emails matching your criteria. Review the labeled emails in Gmail before running the unsubscribe command.

Options:
- `--days`: Number of days of emails to scan (default: 30)
- `--label`: Label name for emails to unsubscribe from (default: "Unsubscribe")
- `--config`: Path to config.toml file

### Unsubscribe

Unsubscribe from labeled emails:

```bash
gmail-unsub unsubscribe --label "Unsubscribe" --headless
```

Options:
- `--label`: Label name for emails to unsubscribe from (default: "Unsubscribe")
- `--headless/--no-headless`: Run browser in headless mode
- `--config`: Path to config.toml file

**Tip**: You can manually apply the "Unsubscribe" label to any email in Gmail, and the tool will process it on the next run. This is useful for emails the AI classifier missed or for one-off unsubscriptions.

### Check Status

View status of unsubscribe attempts:

```bash
gmail-unsub status
```

## Configuration

See [docs/configuration.md](docs/configuration.md) for detailed configuration options.

Key configuration sections:
- `[gmail]`: Gmail API credentials
- `[llm]`: LLM provider and model selection
- `[prompts]`: Customizable prompts for email classification
- `[labels]`: Gmail label names
- `[unsubscribe]`: Browser automation settings

## How It Works

1. **Scanning Phase**:
   - Fetches emails from your Gmail inbox
   - Sends email content to an LLM for classification
   - Labels emails identified as marketing
   - Extracts unsubscribe links (from headers or body)

2. **Unsubscribe Phase**:
   - Attempts RFC 8058 one-click unsubscribe (fast, automatic)
   - Falls back to mailto unsubscribe (sends email)
   - Uses browser automation with AI vision for complex pages
   - Updates labels based on success/failure

## Known Issues

Some email senders use unsubscribe mechanisms that are difficult to automate. The following domains have been identified as problematic:

### High Failure Rate Domains

- **manage.kmail-lists.com** (4+ failures) - Complex unsubscribe flows requiring multiple steps
- **www.linkedin.com** (3+ failures) - Requires login or has complex preference centers
- **click.emails.zappos.com** (2+ failures) - JWT-based unsubscribe links that may expire
- **us.engagingnetworks.app** (2+ failures) - Multi-step unsubscribe process
- **actionnetwork.org** (2+ failures) - Some unsubscribe links return 404 errors

### Other Problematic Domains

- **link.theatlantic.com** - Complex preference management
- **www.tiktok.com** - Requires account verification
- **unsubscribe.kit.com** - Token-based links that may be single-use
- **data.em.officedepot.com** - URL encoding issues with unsubscribe links
- **click.twitch.tv** - Complex preference center

### Workarounds

For these senders, you may need to:
1. Manually unsubscribe through their website
2. Use Gmail's built-in "Unsubscribe" button (if available)
3. Mark emails as spam (Gmail will learn to filter them)

We're actively working on improving browser automation to handle these cases. If you encounter issues with specific senders, please [open an issue](https://github.com/zbowling/gmail-ai-unsub/issues) with details.

## Supported LLM Providers

- **Google Gemini**:
  - `gemini-3-pro-preview` (latest, Nov 2025, use with `thinking_level=high` or `low` based on speed needs)
  - `gemini-2.5-computer-use` (for browser automation, though gemini-3-pro often better)
  - Note: Gemini 2.0 models are not recommended
- **Anthropic Claude**:
  - `claude-4-5-sonnet-20250514` (latest Claude 4.5 series)
  - `claude-4-opus-20250514` (most capable)
- **OpenAI**:
  - `gpt-5` (latest flagship, Aug 2025, PhD-level performance)
  - `gpt-5-mini` (faster variant)
  - `gpt-4.1` (improved coding, 1M token context)
  - `o4-mini` (reasoning model with vision)
  - `o3` (reasoning with configurable analysis depth)

## Requirements

- Gmail account with API access
- LLM API key (Gemini, Anthropic, or OpenAI)
- Internet connection

## Security & Privacy

- All API keys and credentials are stored locally
- Gmail API uses OAuth2 authentication with PKCE
- No data is sent to third parties except your chosen LLM provider
- All processing happens on your machine
- **OAuth Credentials**: The tool includes embedded OAuth credentials for convenience. For production use, consider creating your own OAuth app (see [Developer Setup](#developer-setup)). For native/desktop apps, the client_secret is treated as public metadata - security comes from PKCE and user consent.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions welcome!

- For development setup, see [Developer Setup](#developer-setup)
- For releasing to PyPI, see [docs/releasing.md](docs/releasing.md)
- Please run `ruff check --fix .` and `ruff format .` before submitting PRs

## Support

For issues, questions, or feature requests, please open an issue on GitHub.

## Acknowledgments

Built with:
- [LangChain](https://github.com/langchain-ai/langchain) for LLM integration
- [browser-use](https://github.com/browser-use/browser-use) for browser automation
- [Gmail API](https://developers.google.com/gmail/api) for email access
