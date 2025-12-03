#!/bin/bash
# Set GitHub secrets from .env file
# Usage: ./scripts/set-github-secrets.sh

set -e

if [ ! -f .env ]; then
    echo "Error: .env file not found"
    echo "Create a .env file with:"
    echo "  GMAIL_CLIENT_ID=your-id"
    echo "  GMAIL_CLIENT_SECRET=your-secret"
    echo "  PYPI_API_TOKEN=your-token (optional)"
    exit 1
fi

# Load .env file
set -a
source .env
set +a

# Set secrets
if [ -n "$GMAIL_CLIENT_ID" ]; then
    echo "Setting BUILD_GMAIL_CLIENT_ID..."
    gh secret set BUILD_GMAIL_CLIENT_ID --body "$GMAIL_CLIENT_ID"
    echo "✓ BUILD_GMAIL_CLIENT_ID set"
else
    echo "⚠ GMAIL_CLIENT_ID not found in .env"
fi

if [ -n "$GMAIL_CLIENT_SECRET" ]; then
    echo "Setting BUILD_GMAIL_CLIENT_SECRET..."
    gh secret set BUILD_GMAIL_CLIENT_SECRET --body "$GMAIL_CLIENT_SECRET"
    echo "✓ BUILD_GMAIL_CLIENT_SECRET set"
else
    echo "⚠ GMAIL_CLIENT_SECRET not found in .env"
fi

if [ -n "$PYPI_API_TOKEN" ]; then
    echo "Setting PYPI_API_TOKEN..."
    gh secret set PYPI_API_TOKEN --body "$PYPI_API_TOKEN"
    echo "✓ PYPI_API_TOKEN set"
else
    echo "ℹ PYPI_API_TOKEN not found in .env (optional, only needed if not using Trusted Publishing)"
fi

echo ""
echo "✓ All secrets set! You can verify with:"
echo "  gh secret list"
