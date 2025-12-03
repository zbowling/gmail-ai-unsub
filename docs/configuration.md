# Configuration Reference

Complete reference for `config.toml` configuration options.

## File Locations

The tool uses platform-specific directories following XDG Base Directory conventions.

### Config File Search Order

1. Current working directory (`./config.toml`)
2. Platform-specific config directory (see below)
3. Legacy location (`~/.gmail-ai-unsub/config.toml`)

You can also specify a custom path with `--config` flag.

### Platform-Specific Directories

**Linux** (follows XDG Base Directory Specification):
- Config: `~/.config/gmail-ai-unsub/config.toml`
- Data: `~/.local/share/gmail-ai-unsub/`
- State: `~/.local/state/gmail-ai-unsub/state.json`
- Cache: `~/.cache/gmail-ai-unsub/`

**macOS**:
- Config: `~/Library/Application Support/gmail-ai-unsub/config.toml`
- Data: `~/Library/Application Support/gmail-ai-unsub/`
- State: `~/Library/Application Support/gmail-ai-unsub/state.json`
- Cache: `~/Library/Caches/gmail-ai-unsub/`

**Windows**:
- Config: `%LOCALAPPDATA%\gmail-ai-unsub\gmail-ai-unsub\config.toml`
- Data: `%LOCALAPPDATA%\gmail-ai-unsub\gmail-ai-unsub\`
- State: `%LOCALAPPDATA%\gmail-ai-unsub\gmail-ai-unsub\state.json`
- Cache: `%LOCALAPPDATA%\gmail-ai-unsub\gmail-ai-unsub\Cache\`

### XDG Environment Variables

On all platforms, you can override directories using XDG environment variables:
- `XDG_CONFIG_HOME`: Override config directory base
- `XDG_DATA_HOME`: Override data directory base
- `XDG_STATE_HOME`: Override state directory base
- `XDG_CACHE_HOME`: Override cache directory base

## Configuration Sections

### `[gmail]` - Gmail API Settings

```toml
[gmail]
credentials_file = "credentials.json"  # Path to OAuth2 credentials JSON
token_file = "token.json"              # Path to OAuth token cache
```

- `credentials_file`: Path to the JSON file downloaded from Google Cloud Console
- `token_file`: Where to store the OAuth token (created automatically)

### `[llm]` - LLM Provider Settings

```toml
[llm]
provider = "google"                    # "google", "anthropic", or "openai"
model = "gemini-3-pro-preview"         # Model name (see below)

# API Key - choose one option:
api_key = "your_api_key_here"          # Option 1: Store directly in config
# api_key_env = "GOOGLE_API_KEY"       # Option 2: Use environment variable
```

**API Key Options:**

You can provide your API key in two ways:

1. **Direct in config** (recommended for personal use):
   ```toml
   api_key = "AIza..."
   ```
   Keep your config.toml private and don't commit it to version control.

2. **Environment variable** (recommended for shared/CI environments):
   ```toml
   api_key_env = "GOOGLE_API_KEY"
   ```
   Then set: `export GOOGLE_API_KEY=your_key`

The tool checks `api_key` first, then falls back to the environment variable.

**Get your API keys from:**

| Provider | URL |
|----------|-----|
| Google Gemini | https://aistudio.google.com/apikey |
| Anthropic Claude | https://console.anthropic.com/settings/keys |
| OpenAI | https://platform.openai.com/api-keys |

**Provider Options:**

- `google`: Google Gemini models
  - `gemini-2.5-flash-lite` (fastest, good for simple tasks)
  - `gemini-2.5-flash` (fast and capable, **recommended**)
  - `gemini-3-pro-preview` (best quality with `thinking_level=low`, slower)
- `anthropic`: Anthropic Claude models
  - `claude-4-5-haiku` (fast and efficient, **recommended**)
  - `claude-4-5-sonnet` (more capable, slower)
- `openai`: OpenAI models
  - `gpt-5-nano` (fastest)
  - `gpt-5-mini` (fast and capable, **recommended**)
  - `o4-mini` (reasoning model, slower)

**Default Environment Variables (if using api_key_env):**

- Google: `GOOGLE_API_KEY`
- Anthropic: `ANTHROPIC_API_KEY`
- OpenAI: `OPENAI_API_KEY`

**Temperature Setting:**

```toml
[llm]
temperature = 0.1  # Range: 0.0 to 1.0
```

- `0.0-0.3`: More deterministic, consistent outputs (recommended for classification)
- `0.4-0.7`: Balanced creativity and consistency
- `0.8-1.0`: More creative, varied outputs

**Reasoning/Thinking Level:**

```toml
[llm]
thinking_level = "high"  # Optional
```

For **Gemini 3** models:
- `"low"`: Faster responses, minimal reasoning overhead
- `"high"`: Deeper reasoning, better for complex classification tasks
- `"dynamic"`: Model decides based on task complexity (default)

For **OpenAI o-series** models (o3, o4-mini):
- `"low"`: Quick analysis
- `"medium"`: Balanced analysis
- `"high"`: Deep analysis, thorough reasoning

**Max Tokens:**

```toml
[llm]
max_tokens = 4096  # Optional, defaults to model's limit
```

Controls the maximum length of the model's response. For classification tasks, the default is usually sufficient.

### `[labels]` - Gmail Label Names

```toml
[labels]
marketing = "Unsubscribe"            # Action label - triggers unsubscription
unsubscribed = "Unsubscribed"        # Applied after successful unsubscription
failed = "Unsubscribe-Failed"        # Label for failed attempts (review manually)
```

**How Labels Work:**

- `marketing` (default: "Unsubscribe"): This is an **action label**. Any email with this label will be processed for unsubscription. You can:
  - Let the AI scan apply it automatically
  - Manually apply it to any email you want to unsubscribe from
- `unsubscribed`: Applied after successful unsubscription
- `failed`: Applied when unsubscription fails - review these to manually unsubscribe

Labels can be hierarchical (use `/` separator). The tool will create parent labels automatically.

### `[prompts]` - Email Classification Prompts

Customize how the AI identifies emails to suggest for unsubscription. Remember: **some marketing may be wanted** - be specific about what you don't want.

```toml
[prompts]
system = "You are an expert email analyst helping identify unwanted subscription emails."

marketing_criteria = """
Emails to suggest for unsubscription:
- Unwanted newsletters you never signed up for
- Promotional emails from companies you don't buy from
- Marketing campaigns and advertisements
- Spam-like notifications
"""

exclusions = """
NEVER suggest unsubscribing from:
- Transaction receipts and order confirmations
- Password resets and security alerts
- Personal correspondence
- Banking and financial notifications
- Newsletters you actually want to read
"""

# Free-form user preferences (optional)
# This will be added to the classification prompt to help the AI understand your preferences
# Example: "Keep podcast episode notifications, NPR newsletters, and Stratechery. Unsubscribe from all other Substack and Medium newsletters."
user_preferences = ""
```

These prompts are sent to the LLM for email classification. Customize them to match your preferences.

**Tips:**
- Be specific about what you consider marketing
- List examples of what to exclude
- The more detailed, the better the classification
- Use `user_preferences` for free-form text about specific brands, newsletters, or types of emails you want to keep or avoid

### `[storage]` - State Storage

```toml
[storage]
state_file = "~/.gmail-ai-unsub/state.json"
```

Path to the JSON file storing unsubscribe links and processing status.

### `[browser]` - Browser Automation Model Settings

Configure a separate LLM model for browser automation (navigating unsubscribe pages). This can be different from the classification model.

```toml
[browser]
provider = "browser-use"  # "browser-use", "google", "anthropic", "openai", or "" to use llm.provider
model = ""                 # Model name (leave empty to use llm.model)
api_key = ""              # Optional: separate API key for browser automation
api_key_env = ""          # Optional: environment variable for browser API key
```

**Provider Options:**

- `browser-use`: Browser-Use's optimized model (fastest, recommended)
  - No model name needed
  - Requires `BROWSER_USE_API_KEY` environment variable or `api_key` in config
- `google`: Gemini 2.5 Computer Use (specialized for UI automation)
  - Model: `gemini-2.5-computer-use-preview-10-2025`
- `anthropic`: Claude 4.5 (excellent vision capabilities)
  - Model: `claude-4-5-sonnet` or `claude-4-5-haiku`
- `openai`: GPT-5 (good general purpose)
  - Model: `gpt-5-mini` or `gpt-5-nano`
- Leave `provider` empty to use the same model as classification

**Why Use a Separate Browser Model?**

Browser automation benefits from:
- Vision models that can "see" the page
- Specialized models optimized for UI interaction
- Faster models for quick navigation tasks

See:
- [Browser-Use Speed Matters](https://browser-use.com/posts/speed-matters)
- [Gemini Computer Use](https://ai.google.dev/gemini-api/docs/computer-use)

### `[unsubscribe]` - Unsubscribe Settings

```toml
[unsubscribe]
headless = true              # Run browser in headless mode
browser_timeout = 60         # Browser operation timeout (seconds)
enable_mailto = true         # Enable mailto: unsubscribe via email
```

- `headless`: Set to `false` to see the browser during automation (useful for debugging)
- `browser_timeout`: How long to wait for browser operations
- `enable_mailto`: Whether to send emails for mailto: unsubscribe links

## Example Configurations

### Minimal Configuration

```toml
[gmail]
credentials_file = "credentials.json"

[llm]
provider = "google"
model = "gemini-3-pro-preview"
api_key_env = "GOOGLE_API_KEY"
```

### Full Configuration

```toml
[gmail]
credentials_file = "credentials.json"
token_file = "token.json"

[llm]
provider = "google"
model = "gemini-3-pro-preview"
api_key_env = "GOOGLE_API_KEY"
temperature = 0.1           # Lower for consistent classification
thinking_level = "high"     # Deep reasoning for better accuracy

[labels]
marketing = "Unsubscribe"
unsubscribed = "Unsubscribed"
failed = "Unsubscribe-Failed"

[prompts]
system = "You are an expert email analyst specializing in identifying marketing emails."
marketing_criteria = "Newsletters, promotional offers, sales pitches, product announcements"
exclusions = "Receipts, password resets, personal emails, banking notifications"
user_preferences = "Keep NPR newsletters and Stratechery. Unsubscribe from all other Substack newsletters."

[storage]
state_file = "~/.gmail-ai-unsub/state.json"

[unsubscribe]
headless = true
browser_timeout = 90
enable_mailto = true
```

### Using Anthropic Claude

```toml
[llm]
provider = "anthropic"
model = "claude-4-5-sonnet-20250514"  # Latest Claude 4.5 series
api_key_env = "ANTHROPIC_API_KEY"
temperature = 0.1
```

### Using OpenAI GPT-5

```toml
[llm]
provider = "openai"
model = "gpt-5"  # Latest flagship model (Aug 2025)
api_key_env = "OPENAI_API_KEY"
temperature = 0.1
```

### Using OpenAI o-series (Reasoning Models)

```toml
[llm]
provider = "openai"
model = "o4-mini"  # Or "o3" for deeper reasoning
api_key_env = "OPENAI_API_KEY"
temperature = 0.1
thinking_level = "high"  # "low", "medium", or "high" for analysis depth
```

### Speed vs Quality Trade-offs

For **faster processing** (high volume):
```toml
[llm]
provider = "google"
model = "gemini-3-pro-preview"
thinking_level = "low"   # Faster, less reasoning overhead
temperature = 0.0        # Most deterministic
```

For **best accuracy** (important emails):
```toml
[llm]
provider = "google"
model = "gemini-3-pro-preview"
thinking_level = "high"  # Deep reasoning
temperature = 0.1        # Slightly creative but consistent
```

**Note**: Model identifiers may change. Always check the official API documentation for the most current model names:
- [Google Gemini Models](https://ai.google.dev/gemini-api/docs/models)
- [Anthropic Claude Models](https://docs.anthropic.com/claude/docs/models-overview)
- [OpenAI Models](https://platform.openai.com/docs/models)

## Environment Variables

API keys can be provided in two ways:

1. **In config.toml** (recommended for personal use):
   ```toml
   [llm]
   api_key = "your_key_here"
   ```

2. **As environment variables** (recommended for shared/CI environments):
   ```bash
   # For Gemini
   export GOOGLE_API_KEY=your_key_here

   # For Claude
   export ANTHROPIC_API_KEY=your_key_here

   # For OpenAI
   export OPENAI_API_KEY=your_key_here

   # For Browser-Use
   export BROWSER_USE_API_KEY=your_key_here
   ```

The tool checks `api_key` in config first, then falls back to the environment variable specified in `api_key_env` (or the default for each provider).

For persistent setup, add environment variables to `~/.bashrc` or `~/.zshrc`.

## Validation

The tool validates configuration on startup:
- Checks that credentials file exists
- Verifies API key is set in environment
- Validates model names (basic check)

Errors will be shown with helpful messages.

## Advanced: Multiple Configs

You can maintain different configs for different purposes:

```bash
# Development config
gmail-unsub scan --config config.dev.toml

# Production config
gmail-unsub scan --config config.prod.toml
```
