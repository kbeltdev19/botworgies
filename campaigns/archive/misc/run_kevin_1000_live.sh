#!/bin/bash
#
# Kevin Beltran - 1000 Live Production Applications Runner
# Usage: ./run_kevin_1000_live.sh [--test 50]
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  KEVIN BELTRAN - 1000 LIVE PRODUCTION APPLICATIONS              ║"
echo "║  BrowserBase Proxies + CAPTCHA Solving                          ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check for test mode
TEST_JOBS=""
if [ "$1" == "--test" ] && [ -n "$2" ]; then
    TEST_JOBS="$2"
    echo -e "${YELLOW}⚠️  TEST MODE: Running $TEST_JOBS jobs only${NC}"
fi

# Check Python
echo -e "\n${BLUE}📋 Checking environment...${NC}"
python3 --version || { echo -e "${RED}❌ Python 3 not found${NC}"; exit 1; }

# Check credentials
echo -e "\n${BLUE}🔐 Checking credentials...${NC}"

if [ -z "$BROWSERBASE_API_KEY" ]; then
    echo -e "${RED}❌ BROWSERBASE_API_KEY not set${NC}"
    echo "   Set it with: export BROWSERBASE_API_KEY=your_key"
    exit 1
else
    echo -e "${GREEN}✓ BROWSERBASE_API_KEY is set${NC}"
fi

if [ -z "$BROWSERBASE_PROJECT_ID" ]; then
    echo -e "${YELLOW}⚠️  BROWSERBASE_PROJECT_ID not set (optional)${NC}"
else
    echo -e "${GREEN}✓ BROWSERBASE_PROJECT_ID is set${NC}"
fi

# Change to campaigns directory
cd "$(dirname "$0")"

# Run the campaign
echo -e "\n${BLUE}🚀 Starting production campaign...${NC}"
echo ""

if [ -n "$TEST_JOBS" ]; then
    # Run quick test with specified number of jobs
    python3 -c "
import sys
sys.path.insert(0, '..')
import asyncio
from KEVIN_1000_LIVE_PRODUCTION import LiveProductionCampaign

class QuickTest(LiveProductionCampaign):
    def __init__(self, target):
        self.target = target
        from KEVIN_1000_LIVE_PRODUCTION import CampaignReport, KEVIN_PROFILE
        from pathlib import Path
        from datetime import datetime
        
        self.report = CampaignReport(
            campaign_id=f'kevin_test_{datetime.now().strftime(\"%Y%m%d_%H%M%S\")}',
            start_time=datetime.now(),
            target_applications=target
        )
        self.output_dir = Path('output/kevin_1000_live')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.browser_manager = None
        self.results_lock = asyncio.Lock()
        
        import os
        self.has_browserbase = bool(os.environ.get('BROWSERBASE_API_KEY'))
        self.has_moonshot = bool(os.environ.get('MOONSHOT_API_KEY'))
        
        print('=' * 80)
        print('🚀 KEVIN BELTRAN - LIVE TEST (' + str(target) + ' JOBS)')
        print('=' * 80)

async def main():
    campaign = QuickTest($TEST_JOBS)
    await campaign.initialize()
    jobs = campaign.load_or_generate_jobs()[:$TEST_JOBS]
    await campaign.run_applications(jobs)
    campaign.generate_final_report()
    await campaign.browser_manager.close_all_sessions()

asyncio.run(main())
"
else
    # Run full 1000 job campaign
    python3 KEVIN_1000_LIVE_PRODUCTION.py
fi

echo ""
echo -e "${GREEN}✅ Campaign complete!${NC}"
echo ""
echo -e "${BLUE}📊 Check results in:${NC}"
echo "   campaigns/output/kevin_1000_live/"
