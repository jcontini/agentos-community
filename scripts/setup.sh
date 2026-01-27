#!/bin/bash
# Setup script for agentos-community repository
# Configures git merge driver for manifest.json

set -e

echo "🔧 Setting up agentos-community repository..."

# Configure merge driver for manifest.json
echo "Configuring merge driver for manifest.json..."
git config merge.regenerate-manifest.driver "scripts/merge-manifest.sh %O %A %B"

echo "✅ Setup complete!"
echo ""
echo "The merge driver will automatically regenerate manifest.json during merges,"
echo "preventing conflicts when GitHub Actions updates the manifest."
