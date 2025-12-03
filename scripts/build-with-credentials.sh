#!/bin/bash
# Build script for PyPI wheels with OAuth credentials injected
# Usage: BUILD_GMAIL_CLIENT_ID=... BUILD_GMAIL_CLIENT_SECRET=... ./scripts/build-with-credentials.sh

set -e

# Check if credentials are provided
if [ -z "$BUILD_GMAIL_CLIENT_ID" ] || [ -z "$BUILD_GMAIL_CLIENT_SECRET" ]; then
    echo "Error: BUILD_GMAIL_CLIENT_ID and BUILD_GMAIL_CLIENT_SECRET must be set"
    echo ""
    echo "Usage:"
    echo "  BUILD_GMAIL_CLIENT_ID=your-id BUILD_GMAIL_CLIENT_SECRET=your-secret ./scripts/build-with-credentials.sh"
    echo ""
    echo "Or set them in your environment:"
    echo "  export BUILD_GMAIL_CLIENT_ID=your-id"
    echo "  export BUILD_GMAIL_CLIENT_SECRET=your-secret"
    echo "  ./scripts/build-with-credentials.sh"
    exit 1
fi

# Inject credentials into source
echo "Injecting credentials into source..."
python3 scripts/inject-credentials.py

# Build the wheel
echo "Building wheel..."
uv build

echo ""
echo "✓ Build complete! Wheel is in dist/"
echo "  Note: Credentials are now in the source. Consider reverting before committing."
