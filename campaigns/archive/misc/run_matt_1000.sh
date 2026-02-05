#!/bin/bash
#
# Matt Edwards 1000-Job Production Campaign Launcher
# Usage: ./run_matt_1000.sh [monitor|run]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CAMPAIGN_SCRIPT="$SCRIPT_DIR/MATT_1000_PRODUCTION.py"
MONITOR_SCRIPT="$SCRIPT_DIR/matt_monitor.py"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     MATT EDWARDS 1000-JOB PRODUCTION CAMPAIGN                  ║${NC}"
echo -e "${BLUE}║     20 Concurrent Sessions - Real Applications                 ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check environment
echo -e "${YELLOW}🔍 Checking environment...${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python: $(python3 --version)${NC}"

# Check environment variables
if [ -z "$BROWSERBASE_API_KEY" ]; then
    echo -e "${YELLOW}⚠️  BROWSERBASE_API_KEY not set in environment${NC}"
fi

if [ -z "$MOONSHOT_API_KEY" ]; then
    echo -e "${YELLOW}⚠️  MOONSHOT_API_KEY not set in environment${NC}"
fi

# Check resume file
RESUME_FILE="$SCRIPT_DIR/../data/matt_edwards_resume.pdf"
if [ ! -f "$RESUME_FILE" ]; then
    echo -e "${RED}❌ Resume not found: $RESUME_FILE${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Resume found${NC}"

# Check jobs file
JOBS_FILE="$SCRIPT_DIR/matt_edwards_1000_jobs.json"
if [ ! -f "$JOBS_FILE" ]; then
    echo -e "${RED}❌ Jobs file not found: $JOBS_FILE${NC}"
    exit 1
fi
JOB_COUNT=$(python3 -c "import json; print(len(json.load(open('$JOBS_FILE'))['jobs']))")
echo -e "${GREEN}✅ Jobs file found: $JOB_COUNT jobs${NC}"

echo ""

# Show campaign info
echo -e "${BLUE}📋 Campaign Details:${NC}"
echo "   Candidate: Matt Edwards"
echo "   Email: edwardsdmatt@gmail.com"
echo "   Location: Atlanta, GA"
echo "   Target: 1000 jobs"
echo "   Concurrent Sessions: 20"
echo "   Estimated Duration: ~50 minutes"
echo ""

# Parse command
COMMAND="${1:-run}"

if [ "$COMMAND" == "monitor" ]; then
    echo -e "${BLUE}📊 Starting monitor...${NC}"
    echo "   Press Ctrl+C to stop monitoring"
    echo ""
    python3 "$MONITOR_SCRIPT"
    
elif [ "$COMMAND" == "run" ]; then
    echo -e "${YELLOW}⚠️  WARNING: This will submit REAL job applications!${NC}"
    echo ""
    read -p "Are you sure you want to continue? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        echo -e "${YELLOW}Campaign cancelled.${NC}"
        exit 0
    fi
    
    echo ""
    echo -e "${GREEN}🚀 Starting production campaign...${NC}"
    echo ""
    
    # Run campaign in background and capture PID
    python3 "$CAMPAIGN_SCRIPT" &
    CAMPAIGN_PID=$!
    
    echo -e "${BLUE}Campaign PID: $CAMPAIGN_PID${NC}"
    echo -e "${BLUE}Output directory: $SCRIPT_DIR/output/matt_edwards_production/${NC}"
    echo ""
    echo "Commands:"
    echo "   Monitor progress:  ./run_matt_1000.sh monitor"
    echo "   View logs:         tail -f $SCRIPT_DIR/output/matt_edwards_production/*.log"
    echo "   Stop campaign:     kill $CAMPAIGN_PID"
    echo ""
    
    # Wait for campaign
    wait $CAMPAIGN_PID
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}✅ Campaign completed successfully!${NC}"
    else
        echo -e "${RED}❌ Campaign failed with exit code $EXIT_CODE${NC}"
    fi
    
else
    echo "Usage: $0 [run|monitor]"
    echo ""
    echo "Commands:"
    echo "   run     - Start the production campaign"
    echo "   monitor - Monitor campaign progress"
    echo ""
    exit 1
fi
