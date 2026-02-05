#!/usr/bin/env python3
"""
Simple Campaign Runner - Uses pre-scraped jobs for testing.
"""

import asyncio
import json
import yaml
import random
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_simple_campaign(profile_path: str, limit: int = 50, daily_limit: int = 25):
    """Run a simple campaign using pre-scraped jobs."""
    
    # Load profile
    with open(profile_path) as f:
        profile = yaml.safe_load(f)
    
    name = profile.get('name', 'Unknown')
    logger.info(f"Starting campaign for: {name}")
    
    # Load pre-scraped jobs
    jobs_file = Path('campaigns/output/optimized_scraped_jobs.json')
    if not jobs_file.exists():
        logger.error("No pre-scraped jobs found!")
        return
    
    with open(jobs_file) as f:
        all_jobs = json.load(f)
    
    logger.info(f"Loaded {len(all_jobs)} pre-scraped jobs")
    
    # Filter jobs by profile roles
    search_roles = profile.get('search', {}).get('roles', [])
    keywords = [kw.lower() for role in search_roles for kw in role.split()]
    keywords.extend(['software', 'engineer', 'developer', 'manager'])
    
    matching_jobs = []
    for job in all_jobs:
        title = job.get('title', '').lower()
        if any(kw in title for kw in keywords):
            matching_jobs.append(job)
    
    logger.info(f"Found {len(matching_jobs)} matching jobs")
    
    # Limit to target
    target_jobs = matching_jobs[:limit]
    logger.info(f"Will attempt to apply to {len(target_jobs)} jobs (daily limit: {daily_limit})")
    
    # Simulate applications
    stats = {
        'attempted': 0,
        'successful': 0,
        'failed': 0,
    }
    
    for i, job in enumerate(target_jobs[:daily_limit], 1):
        logger.info(f"\n[{i}/{daily_limit}] Applying to: {job.get('title', 'N/A')} @ {job.get('company', 'N/A')}")
        logger.info(f"  Platform: {job.get('platform', 'unknown')}")
        logger.info(f"  URL: {job.get('url', 'N/A')[:60]}...")
        
        stats['attempted'] += 1
        
        # Simulate application delay
        await asyncio.sleep(random.uniform(2, 5))
        
        # For demo, mark as successful
        stats['successful'] += 1
        logger.info("  ✅ Success")
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("CAMPAIGN SUMMARY")
    logger.info("="*60)
    logger.info(f"Target jobs: {len(target_jobs)}")
    logger.info(f"Daily limit: {daily_limit}")
    logger.info(f"Attempted: {stats['attempted']}")
    logger.info(f"Successful: {stats['successful']}")
    logger.info(f"Failed: {stats['failed']}")
    logger.info(f"Success rate: {(stats['successful']/stats['attempted']*100) if stats['attempted'] > 0 else 0:.1f}%")
    logger.info("="*60)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', default='campaigns/profiles/kevin_beltran.yaml')
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--daily-limit', type=int, default=25)
    args = parser.parse_args()
    
    asyncio.run(run_simple_campaign(args.profile, args.limit, args.daily_limit))
