#!/bin/bash
# Run a live campaign with BrowserBase + Moonshot

set -e

echo "=================================="
echo "🚀 Job Applier - Live Campaign"
echo "=================================="
echo ""

# Load environment
export $(cat .env | grep -v '^#' | xargs)

echo "📋 Configuration:"
echo "  BrowserBase: $BROWSERBASE_API_KEY"
echo "  Moonshot: ${MOONSHOT_API_KEY:0:20}..."
echo ""

# Default to test_small.yaml if no argument provided
CONFIG_FILE="${1:-campaigns/configs/test_small.yaml}"

echo "📝 Using config: $CONFIG_FILE"
echo ""

# Run campaign
echo "🎯 Starting campaign..."
python3 campaigns/run_campaign.py \
  --config "$CONFIG_FILE" \
  --verbose

echo ""
echo "✅ Campaign complete!"
