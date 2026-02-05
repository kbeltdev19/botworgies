#!/usr/bin/env python3
"""
Run Kent Le campaign with live monitoring
Target: 10+ jobs/min with 35 concurrent
"""

import sys
import os
from pathlib import Path

env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import json
from datetime import datetime
from ats_automation.production_kent_le_1000_improved import KENT_LE_PROFILE, ImprovedCampaignRunner

async def run():
    # Load job URLs - skip first 122 already done
    job_file = Path("ats_automation/testing/job_urls_1000.txt")
    with open(job_file) as f:
        all_urls = [line.strip() for line in f if line.strip()]
    
    remaining = all_urls[122:1000]
    
    print("="*70)
    print("🚀 KENT LE - FAST CAMPAIGN STARTING")
    print("="*70)
    print(f"Total remaining: {len(remaining)}")
    print(f"Target rate: 10+ jobs/min")
    print(f"Concurrent: 35")
    print(f"Started: {datetime.now().strftime('%H:%M:%S')}")
    print("="*70 + "\n")
    
    runner = ImprovedCampaignRunner(KENT_LE_PROFILE)
    
    report = await runner.run_campaign(
        job_urls=remaining,
        concurrent=35,
        location="Auburn, AL / Remote",
        use_pool=True
    )
    
    print("\n✅ DONE!")
    print(f"Rate: {report.get('total_jobs', 0) / report.get('duration_minutes', 1):.1f} jobs/min")

if __name__ == "__main__":
    asyncio.run(run())
