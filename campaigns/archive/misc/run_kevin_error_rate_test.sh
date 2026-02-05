#!/bin/bash
#
# Kevin Beltran - 1000 Application Error Rate Test Runner
# Usage: ./run_kevin_error_rate_test.sh [--production]
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║     KEVIN BELTRAN - 1000 APPLICATION ERROR RATE TEST             ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check for production mode
PRODUCTION_MODE=false
if [ "$1" == "--production" ]; then
    PRODUCTION_MODE=true
    echo -e "${GREEN}✓ Production mode enabled${NC}"
fi

# Check Python version
echo -e "\n${BLUE}📋 Checking environment...${NC}"
python3 --version || { echo -e "${RED}❌ Python 3 not found${NC}"; exit 1; }

# Check for required environment variables
echo -e "\n${BLUE}🔐 Checking credentials...${NC}"

if [ -z "$BROWSERBASE_API_KEY" ]; then
    echo -e "${YELLOW}⚠️  BROWSERBASE_API_KEY not set${NC}"
    if [ "$PRODUCTION_MODE" = true ]; then
        echo -e "${RED}❌ Production mode requires BROWSERBASE_API_KEY${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ BROWSERBASE_API_KEY is set${NC}"
fi

if [ -z "$MOONSHOT_API_KEY" ]; then
    echo -e "${YELLOW}⚠️  MOONSHOT_API_KEY not set${NC}"
    if [ "$PRODUCTION_MODE" = true ]; then
        echo -e "${RED}❌ Production mode requires MOONSHOT_API_KEY${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ MOONSHOT_API_KEY is set${NC}"
fi

if [ "$PRODUCTION_MODE" = false ]; then
    echo -e "\n${YELLOW}⚠️  Running in SIMULATION mode (no real applications)${NC}"
    echo -e "${YELLOW}   To run in production mode: ./run_kevin_error_rate_test.sh --production${NC}"
fi

# Change to campaigns directory
cd "$(dirname "$0")"

# Run the test
echo -e "\n${BLUE}🚀 Starting error rate test...${NC}"
echo -e "${BLUE}   This will take approximately 2-4 hours to complete${NC}"
echo ""

python3 KEVIN_1000_ERROR_RATE_TEST.py

# Check exit code
if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✅ Error rate test completed successfully!${NC}"
    
    # Show report location
    REPORT_FILE="output/kevin_error_rate_test/error_rate_report.json"
    if [ -f "$REPORT_FILE" ]; then
        echo -e "\n${BLUE}📊 Report available at:${NC}"
        echo "   $REPORT_FILE"
        
        # Try to extract key stats
        if command -v python3 &> /dev/null; then
            echo -e "\n${BLUE}📈 Quick Stats:${NC}"
            python3 -c "
import json
with open('$REPORT_FILE') as f:
    data = json.load(f)
    stats = data['overall_stats']
    print(f\"   Total Attempted: {stats['total_attempted']}\")
    print(f\"   Successful: {stats['total_successful']}\")
    print(f\"   Failed: {stats['total_failed']}\")
    print(f\"   Success Rate: {stats['overall_success_rate']:.2f}%\")
    print(f\"   Error Rate: {stats['overall_error_rate']:.2f}%\")
"
        fi
    fi
else
    echo -e "\n${RED}❌ Error rate test failed${NC}"
    exit 1
fi
