#!/usr/bin/env python3
"""
Kent Le - 1000 Applications Run
Complete campaign: Collect jobs + Apply in one script

Usage:
    python kent_1000_run.py              # Default: 100 jobs
    python kent_1000_run.py 1000         # Full 1000 applications
    python kent_1000_run.py 500 --dry    # Collect only, don't apply
"""

import sys
import argparse
import asyncio

# Import the batch collection and application modules
from kent_batch_apply import collect_jobs, prioritize_jobs, save_job_list, print_summary
from kent_apply_to_jobs import ApplicationRunner


async def main():
    parser = argparse.ArgumentParser(description='Kent Le - Automated Job Applications')
    parser.add_argument('count', type=int, nargs='?', default=100, help='Number of jobs to apply to')
    parser.add_argument('--dry-run', action='store_true', help='Collect jobs only, do not apply')
    parser.add_argument('--skip-collect', action='store_true', help='Skip collection, use existing jobs file')
    parser.add_argument('--jobs-file', type=str, help='Path to existing jobs JSON file')
    args = parser.parse_args()
    
    target = args.count
    
    print("\n" + "🚀"*35)
    print(f"   KENT LE - {target} APPLICATIONS CAMPAIGN")
    print("   " + "🚀"*35)
    
    # Phase 1: Collect Jobs
    if not args.skip_collect and not args.jobs_file:
        print("\n📦 PHASE 1: JOB COLLECTION")
        print("-" * 70)
        
        jobs = await collect_jobs(target)
        
        if not jobs:
            print("\n❌ No jobs found!")
            return
        
        # Prioritize and save
        prioritized = prioritize_jobs(jobs)
        output_dir, jobs_data = save_job_list(prioritized, target)
        print_summary(jobs_data, output_dir)
        
        jobs_file = output_dir / "jobs_to_apply.json"
    else:
        # Use provided jobs file
        from pathlib import Path
        jobs_file = Path(args.jobs_file) if args.jobs_file else None
        if not jobs_file or not jobs_file.exists():
            print("\n❌ Jobs file not found!")
            return
        output_dir = jobs_file.parent
    
    # Phase 2: Apply to Jobs
    if args.dry_run:
        print("\n🏃 DRY RUN - Jobs collected but not applying")
        print(f"Jobs file: {jobs_file}")
        print("\nTo apply, run:")
        print(f"  python campaigns/kent_apply_to_jobs.py {jobs_file}")
        return
    
    print("\n📦 PHASE 2: AUTOMATED APPLICATIONS")
    print("-" * 70)
    print(f"Starting automated applications to {target} jobs...")
    print("This may take several hours. Press Ctrl+C to pause.\n")
    
    # Run applications
    runner = ApplicationRunner(str(jobs_file))
    await runner.run()
    
    print("\n" + "="*70)
    print("🎉 CAMPAIGN COMPLETE!")
    print("="*70)
    print(f"\nResults saved to: {output_dir}")
    print("\nNext steps:")
    print("1. Review application_results.json for details")
    print("2. Follow up on 'external' applications manually")
    print("3. Track responses and interviews")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Campaign interrupted by user")
        print("Progress has been saved. Run again to continue.")
        sys.exit(0)
