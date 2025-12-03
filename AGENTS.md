# AGENTS.md - Project Structure and Purpose

This document is intended for AI development tools and future maintainers to understand the project structure and design decisions.

## Project Purpose

`gmail-ai-unsub` is a Python CLI tool that uses Large Language Models (LLMs) to identify marketing emails in Gmail and automatically unsubscribe from them. The tool combines:

1. **Email Classification**: LLM-based analysis to identify marketing/promotional emails
2. **Unsubscribe Automation**: Multiple strategies for unsubscribing (headers, mailto, browser automation)

## Architecture Overview

### Core Components

```
src/gmail_ai_unsub/
├── cli.py              # Click-based CLI entry point
├── config.py           # TOML configuration loader
├── storage.py          # JSON state persistence
├── gmail/              # Gmail API integration
│   ├── auth.py         # OAuth2 authentication
│   ├── client.py       # API client with retry logic
│   └── labels.py       # Label management
├── classifier/         # Email classification
│   └── email_classifier.py  # LangChain-based LLM classifier
└── unsubscribe/        # Unsubscribe automation
    ├── extractor.py    # Extract unsubscribe links/headers
    ├── email_unsub.py  # Header-based unsubscribe (RFC 8058)
    └── browser_agent.py # Browser automation with browser-use
```

### Design Decisions

#### 0. Build System: uv-build

- **Build Backend**: `uv-build` (specified in `pyproject.toml`)
- **Why**: Explicitly chosen by project maintainer
- **Important**: **DO NOT** change to another build system (hatchling, setuptools, etc.) without explicit user approval
- **Rationale**: The build system is a fundamental project decision that affects packaging, distribution, and CI/CD

#### 1. LangChain for LLM Integration
- **Why**: Consistent API across providers (Gemini, Claude, OpenAI)
- **Why**: Required by `browser-use` for browser automation
- **Why**: Built-in structured output parsing (Pydantic integration)
- **Trade-off**: Adds dependency overhead, but simplifies multi-provider support

#### 2. browser-use for Browser Automation
- **Why**: Modern, actively maintained, integrates with LangChain
- **Why**: Supports vision models (Gemini 2.5 Computer Use, GPT-4V)
- **Why**: Handles complex unsubscribe pages with dark patterns
- **Alternative considered**: Stagehand, but browser-use has better LangChain integration

#### 3. TOML Configuration
- **Why**: Human-readable, supports nested structures
- **Why**: Standard format for Python projects
- **Why**: Easy to template and document

#### 4. JSON State Storage
- **Why**: Simple, human-readable, no database needed
- **Why**: Stores unsubscribe links and processing status
- **Why**: Easy to inspect and debug

#### 5. Two-Phase Workflow
- **Phase 1 (Scan)**: Identify and label marketing emails
- **Phase 2 (Unsubscribe)**: Process labeled emails for unsubscription
- **Why**: Allows user review before unsubscribing
- **Why**: Separates concerns (classification vs. action)

### Key Flows

#### Email Classification Flow

```
1. Gmail API → Fetch messages (metadata format for quota efficiency)
2. Extract subject, from, body
3. LangChain → Send to LLM with user-defined prompts
4. LLM → Returns structured result (is_marketing, confidence, reason)
5. If marketing → Apply label, extract unsubscribe link
6. Store unsubscribe link in state.json
```

#### Unsubscribe Flow

```
1. Load emails with marketing label
2. For each email:
   a. Check state.json for cached unsubscribe link
   b. If not found, extract from message (header or body)
   c. Try header-based unsubscribe (RFC 8058 one-click or mailto)
   d. If header fails and URL exists → Browser automation
   e. Update labels and state based on result
```

### Gmail API Considerations

- **Quota Management**: Uses `format=metadata` when possible (5 units vs. full message)
- **Rate Limiting**: Exponential backoff for 429 errors
- **OAuth Scopes**: Requires `gmail.readonly`, `gmail.modify`, `gmail.send`
  - `gmail.readonly`: Read email messages and metadata for classification
  - `gmail.modify`: Add/remove labels on messages
  - `gmail.send`: Send unsubscribe emails (for mailto: links)

#### OAuth Credentials Management

The tool uses a flexible credential management system suitable for open-source distribution.

**Approach:**
- **Development/CI**: Credentials loaded from environment variables (`GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`)
  - Use `.env` file (gitignored) for local development
  - Use GitHub Secrets for CI builds
- **PyPI Wheels**: Credentials injected at build time via `BUILD_GMAIL_CLIENT_ID` and `BUILD_GMAIL_CLIENT_SECRET`
  - Build script: `scripts/build-with-credentials.sh`
  - Credentials are embedded in the wheel but not in source tree
- **Source Tree**: Contains testing/placeholder credentials (not production secrets)
- **User Override**: Users can provide their own `credentials.json` for custom OAuth apps

**Security Model:**
- For native/desktop apps, Google treats them as "public clients"
- The client_secret cannot be kept truly secret in open-source apps
- Security comes from:
  - PKCE (Proof Key for Code Exchange) - implemented via `google_auth_oauthlib`
  - User consent (OAuth flow)
  - Minimal scopes requested
- Committing credentials to GitHub doesn't meaningfully reduce security for native apps
- The embedded credentials are treated as public metadata, not secrets

**Build Process:**
1. Source tree has placeholder/testing credentials
2. At build time, `scripts/inject-credentials.py` replaces them with production credentials
3. Wheel is built with credentials embedded
4. Source changes are reverted (credentials not committed)

See `docs/oauth-credentials.md` for detailed documentation.

### LLM Provider Support

The tool supports multiple providers through LangChain:
- **Google Gemini**: Default, good for vision tasks (browser automation)
- **Anthropic Claude**: Strong reasoning, good for classification
- **OpenAI**: Widely available, good general performance

### Error Handling

- **Gmail API**: Retry with exponential backoff for rate limits
- **LLM API**: Failures logged, continue processing other emails
- **Browser Automation**: Timeout-based, errors stored in state
- **State Persistence**: JSON file, atomic writes

### Testing Strategy

- **Unit Tests**: Mock Gmail API and LLM responses
- **Integration Tests**: Test with real Gmail API (requires credentials)
- **CI**: Runs linting (ruff), type checking (mypy, ty, pyrefly), workflow linting (actionlint), and tests (pytest)

### Commit Message Standards

**This project follows the [Conventional Commits](https://www.conventionalcommits.org/) specification.**

All commit messages should follow this format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

#### Types

- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation only changes
- **style**: Code style changes (formatting, missing semicolons, etc.)
- **refactor**: Code refactoring without feature changes or bug fixes
- **perf**: Performance improvements
- **test**: Adding or updating tests
- **build**: Changes to build system or dependencies
- **ci**: Changes to CI configuration
- **chore**: Other changes that don't modify src or test files

#### Scope (optional)

Examples: `gmail`, `cli`, `classifier`, `unsubscribe`, `auth`, `config`

#### Subject

- Use imperative, present tense: "add" not "added" nor "adds"
- Don't capitalize first letter
- No period (.) at the end
- Maximum 72 characters

#### Body (optional)

- Explain the "what" and "why" vs. "how"
- Wrap at 72 characters
- Can include multiple paragraphs

#### Footer (optional)

- Breaking changes: `BREAKING CHANGE: <description>`
- Issue references: `Fixes #123`, `Closes #456`

#### Examples

```
feat(cli): add interactive unsubscribe flow with Yes/No/Always prompts

Implements interactive confirmation for each unsubscribe attempt,
allowing users to review before unsubscribing. Adds --yes flag
to skip prompts for batch processing.

Closes #42
```

```
fix(extractor): handle malformed URLs with spaces in headers

Office Depot and similar senders sometimes include spaces in
List-Unsubscribe headers. Strip spaces before validation.

Fixes #38
```

```
docs: add developer setup guide for Google Cloud OAuth

Comprehensive step-by-step instructions for creating OAuth apps,
configuring consent screen, and adding test users.
```

### Code Quality and Linting

**The project uses pre-commit hooks to automatically run checks before each commit!**

The project uses `ruff` for both linting and formatting, plus additional checks via pre-commit hooks. Pre-commit is configured to run the same checks as CI (except for slower type checkers and tests).

#### Pre-commit Setup

Pre-commit hooks are automatically installed when you run:

```bash
uv sync --all-extras
uv run pre-commit install
```

After installation, pre-commit will automatically run checks on every commit. You can also run checks manually:

```bash
# Run pre-commit on all files
uv run pre-commit run --all-files

# Run pre-commit on staged files only (default on commit)
uv run pre-commit run
```

#### Quick Checks (Manual)

If you want to run checks manually without pre-commit:

```bash
# Check for linting issues
uv run ruff check .

# Auto-fix linting issues (when possible)
uv run ruff check --fix .

# Check code formatting
uv run ruff format --check .

# Auto-format code
uv run ruff format .
```

#### Before Committing

Pre-commit hooks will automatically:
- Fix trailing whitespace and end-of-file issues
- Check YAML, TOML, and JSON syntax
- Lint GitHub Actions workflows (actionlint)
- Run ruff linting (with auto-fix)
- Run ruff formatting

For slower checks (mypy, ty, pyrefly, pytest), these are run in CI. You can enable them in `.pre-commit-config.yaml` if desired.

#### Common Ruff Issues

- **Unused imports (F401)**: Remove imports that aren't used
- **Unused variables (F841)**: Remove or use variables that are assigned but never read
- **Ambiguous variable names (E741)**: Use descriptive names instead of single letters like `l`, `o`, `I`
- **Exception handling (B904)**: Use `raise ... from err` or `raise ... from None` in except clauses
- **Import sorting (I001)**: Let ruff auto-fix with `ruff check --fix`

#### Type Checking

The project uses multiple type checkers for comprehensive coverage:

```bash
# Run mypy type checker
uv run mypy src/

# Run ty type checker (faster, written in Rust)
uvx ty check src/

# Run pyrefly type checker (catches additional errors)
uvx pyrefly check --summarize-errors
```

**Why multiple type checkers?**
- `mypy`: Comprehensive type checking with extensive plugin ecosystem
- `ty`: Extremely fast type checker that catches different classes of errors, written in Rust
- `pyrefly`: Catches additional type errors and attribute access issues that other checkers might miss

All three are run in CI to ensure maximum type safety. Some third-party libraries (like `googleapiclient`) don't have type stubs and are configured to be ignored in `pyproject.toml` or use `# type: ignore` comments.

### Future Enhancements

Potential improvements (not in current scope):
- TUI (Terminal UI) for interactive email review
- Batch processing optimizations
- More sophisticated unsubscribe link extraction
- Support for additional email providers (not just Gmail)
- Webhook notifications for unsubscribe status

### Dependencies

Key dependencies and their roles:
- `uv-build`: Build backend (DO NOT change without user approval)
- `langchain`: LLM abstraction layer
- `browser-use`: Browser automation with AI
- `google-api-python-client`: Gmail API access
- `click`: CLI framework
- `platformdirs`: Cross-platform directory paths (XDG on Linux, AppData on Windows)
- `pydantic`: Data validation and structured output
- `playwright`: Browser engine (via browser-use)

### Configuration Philosophy

- **Progressive Disclosure**: Basic config in README, detailed in docs/
- **User Control**: All prompts are configurable
- **Sensible Defaults**: Works out of the box with minimal config
- **Security**: Credentials never committed, gitignored
- **Cross-Platform**: Uses `platformdirs` for XDG-compliant paths on all platforms

### Cross-Platform Directory Support

The tool uses `platformdirs` to follow platform conventions:

**Linux** (XDG Base Directory Specification):
- Config: `~/.config/gmail-ai-unsub/`
- Data: `~/.local/share/gmail-ai-unsub/`
- State: `~/.local/state/gmail-ai-unsub/`
- Cache: `~/.cache/gmail-ai-unsub/`

**macOS**:
- All: `~/Library/Application Support/gmail-ai-unsub/`
- Cache: `~/Library/Caches/gmail-ai-unsub/`

**Windows**:
- All: `%LOCALAPPDATA%\gmail-ai-unsub\gmail-ai-unsub\`

XDG environment variables (`XDG_CONFIG_HOME`, etc.) are respected on all platforms.

See `src/gmail_ai_unsub/paths.py` for the implementation.

### State Management

State is stored in JSON file (platform-specific location, e.g., `~/.local/state/gmail-ai-unsub/state.json` on Linux):
- Unsubscribe links (cached from extraction)
- Processing status (pending, success, failed)
- Error messages for debugging

This allows:
- Resuming interrupted unsubscribe operations
- Debugging failed attempts
- Auditing unsubscribe history
