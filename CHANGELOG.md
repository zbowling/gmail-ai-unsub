# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2025-12-03

### Fixed

- Fixed shellcheck errors in GitHub Actions workflow files (proper variable quoting)
- Fixed ruff formatting issues in CLI code
- Removed unused type ignore comments flagged by mypy
- Added type ignore comments for pyrefly on dynamically added OAuth methods
- Configured mypy to allow type ignores needed by pyrefly
- Removed invalid pyrefly config key that caused warnings
- All CI checks now passing successfully

### Changed

- Enabled mypy and ty type checking in pre-commit hooks
- Improved pre-commit hook configuration for better developer experience

## [0.1.0] - 2025-12-02

### Added

- Initial release of gmail-ai-unsub
- AI-powered email classification using LangChain (supports Gemini, Claude, OpenAI)
- Multi-strategy unsubscribe automation:
  - RFC 8058 One-Click unsubscribe (HTTP POST)
  - Mailto unsubscribe (sends email)
  - Browser automation for complex unsubscribe pages using AI vision models
- Gmail API integration with OAuth2 authentication
- Interactive setup wizard (`gmail-unsub setup`) with rich TUI
- SQLite-based email analysis cache to avoid redundant LLM calls
- State tracking for unsubscribe attempts and sender history
- Cross-platform support (Linux, macOS, Windows) with XDG directory compliance
- CLI commands:
  - `scan`: Identify and label marketing emails
  - `unsubscribe`: Interactive unsubscribe flow with Yes/No/Always prompts
  - `status`: View unsubscribe statistics
  - `cache`: Manage email analysis cache (stats, clear, remove)
- Support for multiple LLM providers (Google Gemini, Anthropic Claude, OpenAI)
- Customizable prompts for email classification
- BeautifulSoup4-based HTML email parsing for unsubscribe link extraction
- Quoted-printable MIME decoding
- URL validation and accessibility testing
- Sender tracking to avoid redundant unsubscribe attempts
- Rich terminal output with spinners, Gmail links, and color-coded results
- Comprehensive documentation (README, AGENTS.md, docs/)
- GitHub Actions CI/CD (linting, type checking, testing)
- PyPI release workflow with credential injection
- Conventional commits standard
- Unit tests with pytest

[Unreleased]: https://github.com/zbowling/gmail-ai-unsub/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/zbowling/gmail-ai-unsub/releases/tag/v0.1.1
[0.1.0]: https://github.com/zbowling/gmail-ai-unsub/releases/tag/v0.1.0
