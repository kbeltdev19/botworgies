#!/bin/bash
# Run Kevin Beltran's 1000-Job Campaign
# ServiceNow / ITSM - Remote Contract Focus

cd "$(dirname "$0")"

echo "=================================="
echo "Kevin Beltran 1000-Job Campaign"
echo "=================================="
echo ""
echo "Configuration:"
echo "  - Target: 1000 applications"
echo "  - Session Limit: 1000"
echo "  - Concurrent Browsers: 50"
echo "  - Focus: ServiceNow / ITSM / Federal"
echo "  - Location: Remote (Atlanta, GA base)"
echo "  - Salary: $85k+"
echo ""

# Check environment
if [ -z "$MOONSHOT_API_KEY" ]; then
    echo "⚠️  Warning: MOONSHOT_API_KEY not set"
fi

if [ -z "$BROWSERBASE_API_KEY" ]; then
    echo "⚠️  Warning: BROWSERBASE_API_KEY not set"
fi

echo "Starting campaign..."
echo ""

python3 kevin_beltran_1000_campaign.py "$@"
