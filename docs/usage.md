# Usage Examples

Common usage patterns and workflows for Gmail AI Unsubscribe Tool.

## Getting Started

### Interactive Setup (Recommended)

The easiest way to get started is with the interactive setup wizard:

```bash
gmail-unsub setup
```

This will guide you through:
1. Selecting your LLM provider (Google Gemini, Anthropic Claude, or OpenAI)
2. Choosing a model and configuring settings (temperature, reasoning mode)
3. Setting up Gmail API credentials path
4. Customizing labels for organizing emails
5. Optionally customizing classification prompts
6. Configuring browser automation settings

The wizard creates your config at the platform-specific location (e.g., `~/.config/gmail-ai-unsub/config.toml` on Linux).

**Updating existing config**: If you already have a config file, running `gmail-unsub setup` again will prefill all questions with your current values. Just press Enter to keep existing settings or change specific options.

## Basic Workflow

### 1. Initial Scan

Scan your inbox for emails to unsubscribe from:

```bash
gmail-unsub scan --days 30
```

This will:
- Fetch emails from the last 30 days
- Classify each email using the LLM based on your criteria
- Apply the "Unsubscribe" label to emails matching your criteria
- Extract and cache unsubscribe links

### 2. Review in Gmail

Open Gmail and review the emails labeled "Unsubscribe":
- Verify the classification is correct
- Remove the label from any false positives (emails you want to keep)
- Keep the label on emails you want to unsubscribe from
- **Tip**: You can manually add the "Unsubscribe" label to any email to include it

### 3. Unsubscribe

Process all labeled emails:

```bash
gmail-unsub unsubscribe
```

This will:
- Process each email with the "Unsubscribe" label
- Try header-based unsubscribe first (fast)
- Use browser automation for complex pages
- Apply "Unsubscribed" label on success
- Apply "Unsubscribe-Failed" label on failure (review these manually)

### 4. Check Status

View unsubscribe statistics:

```bash
gmail-unsub status
```

## Advanced Usage

### Custom Label Names

Use different label names:

```bash
# Scan with custom label
gmail-unsub scan --days 30 --label "Newsletters/ToReview"

# Unsubscribe from that label
gmail-unsub unsubscribe --label "Newsletters/ToReview"
```

### Headless vs Visible Browser

Run browser automation in visible mode for debugging:

```bash
gmail-unsub unsubscribe --no-headless
```

This opens a browser window so you can see what's happening.

### Scanning Specific Time Ranges

Scan different time periods:

```bash
# Last week
gmail-unsub scan --days 7

# Last 3 months
gmail-unsub scan --days 90

# Last year
gmail-unsub scan --days 365
```

### Using Different Config Files

Maintain separate configs for different purposes:

```bash
# Development/testing
gmail-unsub scan --config config.test.toml

# Production
gmail-unsub scan --config config.prod.toml
```

## Workflow Patterns

### Weekly Cleanup

Set up a weekly cron job:

```bash
# Add to crontab (crontab -e)
0 9 * * 0 cd /path/to/project && gmail-unsub scan --days 7 && gmail-unsub unsubscribe
```

### Two-Pass Review

1. **First pass - conservative**:
   - Scan with strict prompts (fewer false positives)
   - Review in Gmail
   - Manually add label to any missed emails

2. **Second pass - unsubscribe**:
   - Run unsubscribe on the final label set

### Gradual Unsubscription

1. Scan and label emails
2. Review in Gmail
3. Unsubscribe in small batches:

```bash
# Process 10 emails at a time (manual, or script it)
gmail-unsub unsubscribe
# Review results
gmail-unsub status
# Repeat
```

## Troubleshooting Workflows

### Re-scanning After Prompt Changes

If you update your classification prompts:

```bash
# Remove old labels first (in Gmail or via API)
# Then re-scan
gmail-unsub scan --days 30
```

### Retrying Failed Unsubscribes

Failed unsubscribes are labeled "Unsubscribe-Failed". To retry:

1. In Gmail, move failed emails back to "Unsubscribe" label
2. Run unsubscribe again:

```bash
gmail-unsub unsubscribe
```

### Debugging Classification

To see why emails are classified a certain way:

1. Run scan with verbose output (if implemented)
2. Check the `reason` field in classification results
3. Adjust prompts in `config.toml` based on results

### Debugging Browser Automation

When browser automation fails:

1. Run with `--no-headless` to see what's happening
2. Check the error message in status:

```bash
gmail-unsub status
```

3. Some pages may require manual intervention (CAPTCHAs, etc.)

## Integration Examples

### With Email Filters

Combine with Gmail filters for better organization:

1. Create Gmail filter to auto-label certain senders
2. Use this tool to scan and classify the rest
3. Unsubscribe from both sets

### With Other Tools

Use alongside other email management tools:

```bash
# Clean up with this tool
gmail-unsub scan --days 30
gmail-unsub unsubscribe

# Then use other tools for archiving, etc.
```

## Best Practices

1. **Start Small**: Begin with `--days 7` to test the tool
2. **Review First**: Always review labeled emails before unsubscribing
3. **Customize Prompts**: Adjust prompts to match your email patterns
4. **Monitor Status**: Check `gmail-unsub status` regularly
5. **Backup State**: The state file can be backed up for recovery

## Performance Tips

- **Batch Processing**: The tool processes emails in batches automatically
- **Quota Management**: Uses metadata format when possible to save quota
- **Rate Limiting**: Automatically handles Gmail API rate limits
- **Parallel Processing**: Future versions may support parallel LLM calls

## Security Considerations

- **API Keys**: Never commit API keys or credentials
- **OAuth Tokens**: Keep token files secure
- **State File**: Contains email IDs and unsubscribe links (sensitive)
- **Browser Automation**: Runs locally, no data sent externally
