#!/usr/bin/env python3
"""
Campaign Runner with Duplicate Checking & Verification

Usage:
    python run_campaign_with_dupecheck.py --candidate kent|matt --jobs 1000
"""

import sys
import os
import argparse
import asyncio
import json
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from campaigns.duplicate_checker import DuplicateChecker, CampaignTracker

# Load environment
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)


async def run_kent_campaign(num_jobs: int = 1000):
    """Run Kent Le's campaign with duplicate checking."""
    from ats_automation.production_kent_le_1000_improved import KENT_LE_PROFILE, ImprovedCampaignRunner
    
    user_id = "kle4311@gmail.com"
    campaign_id = f"kent_le_{datetime.now().strftime('%Y%m%d_%H%M')}"
    
    print("="*70)
    print("🚀 KENT LE CAMPAIGN (with duplicate checking)")
    print("="*70)
    print(f"Email: {KENT_LE_PROFILE.email}")
    print(f"Location: Auburn, AL / Remote")
    print(f"Target: {num_jobs} jobs")
    print(f"Concurrent: 50")
    print()
    
    # Load job URLs
    job_file = Path(__file__).parent.parent / "ats_automation" / "testing" / "job_urls_1000.txt"
    with open(job_file) as f:
        all_urls = [line.strip() for line in f if line.strip()][:num_jobs]
    
    # Initialize duplicate checker and tracker
    checker = DuplicateChecker()
    tracker = CampaignTracker(user_id, campaign_id)
    
    # Filter duplicates
    new_urls, duplicates = tracker.load_jobs(all_urls)
    
    if not new_urls:
        print("⚠️  No new jobs to apply to (all duplicates)")
        return
    
    print(f"\n✅ Proceeding with {len(new_urls)} new jobs\n")
    
    # Run campaign
    runner = ImprovedCampaignRunner(KENT_LE_PROFILE)
    report = await runner.run_campaign(
        job_urls=new_urls,
        concurrent=50,
        location="Auburn, AL / Remote",
        use_pool=True
    )
    
    # Update tracker with results
    for result in runner.results:
        if result.success:
            tracker.record_success(result.job_url)
        else:
            tracker.record_failure(result.job_url)
    
    # Verify campaign
    print("\n🔍 Verifying campaign...")
    verification = tracker.verify()
    
    print("\n📊 VERIFICATION REPORT:")
    print(f"   Total expected: {verification['total_expected']}")
    print(f"   Verified applied: {verification['verified_applied']}")
    print(f"   Missing: {verification['missing']}")
    print(f"   Success rate: {verification['success_rate']:.1f}%")
    
    # Final stats
    stats = checker.get_application_stats(user_id)
    print("\n📈 LIFETIME STATS:")
    print(f"   Total applications: {stats['total_applications']}")
    print(f"   Unique jobs cached: {stats['cached_unique']}")
    
    return report


async def run_matt_campaign(num_jobs: int = 1000):
    """Run Matt Edwards' campaign with duplicate checking."""
    from ats_automation.production_matt_edwards_1000 import MATT_EDWARDS_PROFILE, MattEdwardsCampaignRunner
    
    user_id = "edwardsdmatt@gmail.com"
    campaign_id = f"matt_edwards_{datetime.now().strftime('%Y%m%d_%H%M')}"
    
    print("="*70)
    print("🚀 MATT EDWARDS CAMPAIGN (with duplicate checking)")
    print("="*70)
    print(f"Email: {MATT_EDWARDS_PROFILE.email}")
    print(f"Location: Atlanta, GA / Remote")
    print(f"Clearance: Secret")
    print(f"Target: {num_jobs} jobs")
    print(f"Concurrent: 30")
    print()
    
    # Load job URLs
    job_file = Path(__file__).parent.parent / "ats_automation" / "testing" / "job_urls_1000.txt"
    with open(job_file) as f:
        all_urls = [line.strip() for line in f if line.strip()][:num_jobs]
    
    # Initialize duplicate checker and tracker
    checker = DuplicateChecker()
    tracker = CampaignTracker(user_id, campaign_id)
    
    # Filter duplicates
    new_urls, duplicates = tracker.load_jobs(all_urls)
    
    if not new_urls:
        print("⚠️  No new jobs to apply to (all duplicates)")
        return
    
    print(f"\n✅ Proceeding with {len(new_urls)} new jobs\n")
    
    # Run campaign
    runner = MattEdwardsCampaignRunner(MATT_EDWARDS_PROFILE)
    report = await runner.run_campaign(
        job_urls=new_urls,
        concurrent=30,
        location="Atlanta, GA / Remote"
    )
    
    # Update tracker with results
    for result in runner.results:
        if result.success:
            tracker.record_success(result.job_url)
        else:
            tracker.record_failure(result.job_url)
    
    # Verify campaign
    print("\n🔍 Verifying campaign...")
    verification = tracker.verify()
    
    print("\n📊 VERIFICATION REPORT:")
    print(f"   Total expected: {verification['total_expected']}")
    print(f"   Verified applied: {verification['verified_applied']}")
    print(f"   Missing: {verification['missing']}")
    print(f"   Success rate: {verification['success_rate']:.1f}%")
    
    # Final stats
    stats = checker.get_application_stats(user_id)
    print("\n📈 LIFETIME STATS:")
    print(f"   Total applications: {stats['total_applications']}")
    print(f"   Unique jobs cached: {stats['cached_unique']}")
    
    return report


def check_status(candidate: str):
    """Check application status for a candidate."""
    user_id = f"{candidate}_001"
    checker = DuplicateChecker()
    
    print(f"\n📊 Application Status for {candidate.upper()}:")
    print("="*50)
    
    stats = checker.get_application_stats(user_id)
    print(f"\nTotal Applications: {stats['total_applications']}")
    print(f"Cached Unique Jobs: {stats['cached_unique']}")
    
    if stats['by_status']:
        print("\nBy Status:")
        for status, count in sorted(stats['by_status'].items()):
            print(f"   {status:20} {count:4d}")
    
    applied_urls = checker.get_applied_urls(user_id)
    print(f"\nTotal Unique URLs Applied: {len(applied_urls)}")


def main():
    parser = argparse.ArgumentParser(description="Run job campaign with duplicate checking")
    parser.add_argument("--candidate", choices=["kent", "matt"], required=True,
                       help="Which candidate to run campaign for")
    parser.add_argument("--jobs", type=int, default=1000,
                       help="Number of jobs to apply to")
    parser.add_argument("--status", action="store_true",
                       help="Check application status only")
    
    args = parser.parse_args()
    
    if args.status:
        check_status(args.candidate)
        return
    
    # Run campaign
    if args.candidate == "kent":
        report = asyncio.run(run_kent_campaign(args.jobs))
    else:
        report = asyncio.run(run_matt_campaign(args.jobs))
    
    print("\n" + "="*70)
    print("✅ CAMPAIGN COMPLETE")
    print("="*70)


if __name__ == "__main__":
    main()
