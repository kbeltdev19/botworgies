#!/bin/bash
export $(cat ../.env | grep -v '^#' | xargs)
python3 -c "
import sys
sys.path.insert(0, '..')
import asyncio
from KEVIN_1000_REAL import RealJobCampaign

async def main():
    campaign = RealJobCampaign(target=1000)
    await campaign.run()

asyncio.run(main())
" 2>&1
