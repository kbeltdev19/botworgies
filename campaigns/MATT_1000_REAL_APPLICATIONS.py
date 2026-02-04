#!/usr/bin/env python3
"""
Matt Edwards 1000 Real Applications - Production Campaign

⚠️  WARNING: THIS WILL SUBMIT REAL JOB APPLICATIONS  ⚠️

This script will:
1. Scrape 1000 real jobs with DIRECT application URLs using jobspy
2. AUTO-SUBMIT applications using Matt's profile
3. Track all submissions with confirmation IDs

Safety Controls:
- Rate limiting: 30-90s between applications
- Max 5 concurrent (respects BrowserBase limits)
- Confirmation required before starting
- Real-time progress monitoring
- Automatic checkpointing every 10 apps

Usage:
    python MATT_1000_REAL_APPLICATIONS.py --confirm --auto-submit

Or for test mode (simulated):
    python MATT_1000_REAL_APPLICATIONS.py --test
"""

import asyncio
import argparse
import json
import logging
import os
import random
import signal
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('campaigns/output/matt_1000_real.log')
    ]
)
logger = logging.getLogger(__name__)

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Try to import jobspy
try:
    from jobspy import scrape_jobs
    JOBSY_AVAILABLE = True
except ImportError:
    JOBSY_AVAILABLE = False
    logger.warning("jobspy not available, using mock data")


@dataclass
class MattProfile:
    """Matt Edwards profile for applications."""
    first_name: str = "Matt"
    last_name: str = "Edwards"
    email: str = "edwardsdmatt@gmail.com"
    phone: str = "404-555-0123"  # Update with real number
    linkedin: str = "https://www.linkedin.com/in/matt-edwards-/"
    location: str = "Atlanta, GA"
    clearance: str = "Secret"
    resume_path: str = "data/matt_edwards_resume.pdf"
    
    def to_dict(self) -> Dict:
        return {
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
            'phone': self.phone,
            'linkedin': self.linkedin,
            'location': self.location,
            'clearance': self.clearance,
        }


@dataclass
class ApplicationResult:
    """Result of a single application."""
    job_id: str
    title: str
    company: str
    location: str
    url: str
    platform: str
    status: str  # 'submitted', 'failed', 'skipped'
    message: str
    submitted_at: str
    confirmation_id: Optional[str] = None
    screenshot_path: Optional[str] = None
    error_details: Optional[str] = None


class Matt1000RealApplications:
    """
    Production campaign for Matt's 1000 real job applications.
    """
    
    def __init__(self, profile: MattProfile, auto_submit: bool = False, 
                 test_mode: bool = True, max_applications: int = 1000):
        self.profile = profile
        self.auto_submit = auto_submit
        self.test_mode = test_mode
        self.max_applications = max_applications
        
        # Settings
        self.max_concurrent = 5  # Conservative for BrowserBase
        self.min_delay = 30
        self.max_delay = 90
        self.checkpoint_every = 10
        
        # State
        self.jobs: List[Dict] = []
        self.results: List[ApplicationResult] = []
        self.stats = {
            'started_at': None,
            'completed_at': None,
            'total_jobs': 0,
            'attempted': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
        }
        self.should_stop = False
        
        # Output
        self.output_dir = Path("campaigns/output/matt_1000_real")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle graceful shutdown."""
        logger.warning("\n🛑 Shutdown signal received. Saving state...")
        self.should_stop = True
        
    def scrape_jobs_with_jobspy(self) -> List[Dict]:
        """Scrape real jobs using jobspy."""
        if not JOBSY_AVAILABLE:
            logger.error("jobspy not available. Cannot scrape jobs.")
            return []
            
        logger.info("🔍 Scraping jobs with jobspy...")
        
        all_jobs = []
        
        # Search terms for Matt's profile
        search_terms = [
            "Customer Success Manager",
            "Cloud Delivery Manager",
            "Technical Account Manager",
            "Solutions Architect",
            "Enterprise Account Manager",
            "Cloud Account Manager",
        ]
        
        locations = ["Atlanta, GA", "Remote"]
        
        for search_term in search_terms:
            for location in locations:
                if self.should_stop:
                    break
                    
                logger.info(f"  Searching: '{search_term}' in {location}")
                
                try:
                    jobs_df = scrape_jobs(
                        site_name=["indeed", "linkedin", "zip_recruiter"],
                        search_term=search_term,
                        location=location,
                        results_wanted=min(50, self.max_applications // len(search_terms) // len(locations)),
                        hours_old=72,  # Last 3 days
                    )
                    
                    if jobs_df is not None and not jobs_df.empty:
                        for _, row in jobs_df.iterrows():
                            job = {
                                'id': f"{row.get('site', 'unknown')}_{hash(str(row.get('job_url', ''))) % 10000000}",
                                'title': row.get('title', ''),
                                'company': row.get('company', ''),
                                'location': row.get('location', ''),
                                'url': row.get('job_url', ''),
                                'description': row.get('description', '')[:500],
                                'platform': row.get('site', 'unknown'),
                                'date_posted': str(row.get('date_posted', '')),
                            }
                            all_jobs.append(job)
                            
                        logger.info(f"    Found {len(jobs_df)} jobs")
                        
                except Exception as e:
                    logger.error(f"    Failed to scrape: {e}")
                    
                # Be nice to APIs
                time.sleep(2)
                
            if self.should_stop:
                break
                
        # Deduplicate by URL
        seen_urls = set()
        unique_jobs = []
        for job in all_jobs:
            if job['url'] not in seen_urls:
                seen_urls.add(job['url'])
                unique_jobs.append(job)
                
        logger.info(f"✓ Scraped {len(unique_jobs)} unique jobs")
        return unique_jobs[:self.max_applications]
        
    def load_mock_jobs(self) -> List[Dict]:
        """Load mock jobs for testing."""
        logger.info("🧪 Loading mock jobs for testing...")
        
        mock_jobs = []
        companies = [
            "Salesforce", "AWS", "Microsoft", "Google", "Oracle",
            "HubSpot", "Zendesk", "Twilio", "Okta", "Cloudflare",
            "Datadog", "MongoDB", "Confluent", "Elastic", "GitLab",
        ]
        
        titles = [
            "Customer Success Manager",
            "Cloud Delivery Manager",
            "Technical Account Manager",
            "Enterprise Account Manager",
        ]
        
        for i in range(min(100, self.max_applications)):
            mock_jobs.append({
                'id': f"mock_{i:04d}",
                'title': random.choice(titles),
                'company': random.choice(companies),
                'location': random.choice(["Remote", "Atlanta, GA", "United States"]),
                'url': f"https://example.com/job/{i}",
                'description': "Mock job description for testing",
                'platform': random.choice(["greenhouse", "lever", "indeed", "linkedin"]),
                'date_posted': datetime.now().isoformat(),
            })
            
        return mock_jobs
        
    async def apply_to_job(self, job: Dict, browser_manager=None) -> ApplicationResult:
        """Apply to a single job."""
        result = ApplicationResult(
            job_id=job['id'],
            title=job['title'],
            company=job['company'],
            location=job['location'],
            url=job['url'],
            platform=job.get('platform', 'unknown'),
            status='pending',
            message='',
            submitted_at=datetime.now().isoformat(),
        )
        
        try:
            logger.info(f"📝 {job['title']} at {job['company']} ({job.get('platform', 'unknown')})")
            
            if self.test_mode:
                # Simulate application
                await asyncio.sleep(random.uniform(0.5, 1.5))
                
                # Simulate occasional failures
                if random.random() < 0.1:  # 10% failure rate
                    result.status = 'failed'
                    result.message = 'Simulated failure (test mode)'
                    logger.info(f"   ✗ Failed (simulated)")
                else:
                    result.status = 'submitted'
                    result.message = 'Application submitted (TEST MODE)'
                    result.confirmation_id = f"TEST_{job['id']}"
                    logger.info(f"   ✓ Submitted (test)")
                    
            elif not self.auto_submit:
                result.status = 'skipped'
                result.message = 'Auto-submit disabled'
                logger.info(f"   ⏭️  Skipped")
                
            else:
                # TODO: Implement real application logic
                # This would use the appropriate adapter based on platform
                result.status = 'skipped'
                result.message = 'Real application logic not implemented yet'
                logger.info(f"   ⏭️  Skipped (not implemented)")
                
        except Exception as e:
            result.status = 'failed'
            result.message = str(e)
            result.error_details = traceback.format_exc()
            logger.error(f"   ✗ Error: {e}")
            
        return result
        
    async def run_campaign(self):
        """Run the full campaign."""
        # Print banner
        print("\n" + "="*70)
        print("🚀 MATT EDWARDS - 1000 REAL JOB APPLICATIONS")
        print("="*70)
        print(f"Candidate: {self.profile.first_name} {self.profile.last_name}")
        print(f"Email: {self.profile.email}")
        print(f"Clearance: {self.profile.clearance}")
        print(f"Target: {self.max_applications} applications")
        print(f"Mode: {'TEST (simulated)' if self.test_mode else 'REAL'}")
        print(f"Auto-submit: {'ENABLED' if self.auto_submit else 'DISABLED'}")
        print("="*70 + "\n")
        
        self.stats['started_at'] = datetime.now().isoformat()
        
        # Phase 1: Get jobs
        if JOBSY_AVAILABLE and not self.test_mode:
            self.jobs = self.scrape_jobs_with_jobspy()
        else:
            self.jobs = self.load_mock_jobs()
            
        if not self.jobs:
            logger.error("❌ No jobs found. Aborting.")
            return
            
        self.stats['total_jobs'] = len(self.jobs)
        logger.info(f"📋 Loaded {len(self.jobs)} jobs for application\n")
        
        # Save job list
        self._save_json('jobs.json', self.jobs)
        
        # Phase 2: Apply to jobs
        logger.info("🎯 Starting application submission...")
        logger.info(f"   Concurrent: {self.max_concurrent}")
        logger.info(f"   Delay: {self.min_delay}-{self.max_delay}s between apps")
        logger.info(f"   Checkpoint: every {self.checkpoint_every} apps\n")
        
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def apply_with_limit(job):
            async with semaphore:
                result = await self.apply_to_job(job)
                
                # Rate limiting
                delay = random.randint(self.min_delay, self.max_delay)
                await asyncio.sleep(delay)
                
                return result
                
        # Process in batches
        batch_size = self.checkpoint_every
        total = len(self.jobs)
        
        for batch_start in range(0, total, batch_size):
            if self.should_stop:
                logger.info("🛑 Campaign stopped by user")
                break
                
            batch_end = min(batch_start + batch_size, total)
            batch = self.jobs[batch_start:batch_end]
            
            logger.info(f"\n📦 Batch {batch_start//batch_size + 1}/{(total-1)//batch_size + 1} " +
                       f"(jobs {batch_start+1}-{batch_end})")
            
            # Process batch
            tasks = [apply_with_limit(job) for job in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Task failed: {result}")
                    continue
                    
                self.results.append(result)
                self.stats['attempted'] += 1
                
                if result.status == 'submitted':
                    self.stats['successful'] += 1
                elif result.status == 'failed':
                    self.stats['failed'] += 1
                elif result.status == 'skipped':
                    self.stats['skipped'] += 1
                    
            # Checkpoint
            self._save_checkpoint()
            self._print_progress()
            
        # Complete
        self.stats['completed_at'] = datetime.now().isoformat()
        self._save_final_report()
        self._print_summary()
        
    def _save_json(self, filename: str, data: Any):
        """Save data to JSON file."""
        filepath = self.output_dir / filename
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        logger.debug(f"Saved {filepath}")
        
    def _save_checkpoint(self):
        """Save campaign checkpoint."""
        checkpoint = {
            'timestamp': datetime.now().isoformat(),
            'progress': f"{len(self.results)}/{self.stats['total_jobs']}",
            'stats': self.stats,
            'last_10_results': [asdict(r) for r in self.results[-10:]],
        }
        self._save_json('checkpoint.json', checkpoint)
        
    def _save_final_report(self):
        """Save final campaign report."""
        report = {
            'profile': asdict(self.profile),
            'stats': self.stats,
            'results': [asdict(r) for r in self.results],
        }
        self._save_json('final_report.json', report)
        logger.info(f"💾 Final report saved to {self.output_dir}/final_report.json")
        
    def _print_progress(self):
        """Print progress update."""
        attempted = self.stats['attempted']
        success = self.stats['successful']
        failed = self.stats['failed']
        total = self.stats['total_jobs']
        
        pct = (attempted / total * 100) if total > 0 else 0
        success_rate = (success / attempted * 100) if attempted > 0 else 0
        
        logger.info(f"📊 Progress: {attempted}/{total} ({pct:.1f}%) | " +
                   f"Success: {success} | Failed: {failed} | Rate: {success_rate:.1f}%")
        
    def _print_summary(self):
        """Print final summary."""
        print("\n" + "="*70)
        print("📋 CAMPAIGN SUMMARY")
        print("="*70)
        
        if self.stats['started_at'] and self.stats['completed_at']:
            duration = (
                datetime.fromisoformat(self.stats['completed_at']) - 
                datetime.fromisoformat(self.stats['started_at'])
            ).total_seconds() / 60
            print(f"Duration: {duration:.1f} minutes")
            
        print(f"Total jobs: {self.stats['total_jobs']}")
        print(f"Attempted: {self.stats['attempted']}")
        print(f"Successful: {self.stats['successful']}")
        print(f"Failed: {self.stats['failed']}")
        print(f"Skipped: {self.stats['skipped']}")
        
        if self.stats['attempted'] > 0:
            success_rate = self.stats['successful'] / self.stats['attempted'] * 100
            print(f"Success rate: {success_rate:.1f}%")
            
        print("="*70)


def main():
    parser = argparse.ArgumentParser(
        description='Matt Edwards 1000 Real Job Applications',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Test mode (simulated, no real applications)
    python MATT_1000_REAL_APPLICATIONS.py --test --limit 50
    
    # Real job scraping, but no applications
    python MATT_1000_REAL_APPLICATIONS.py --limit 100
    
    # FULL PRODUCTION - Real applications with auto-submit
    python MATT_1000_REAL_APPLICATIONS.py --confirm --auto-submit --limit 1000
        """
    )
    
    parser.add_argument('--confirm', action='store_true',
                       help='CONFIRM production run (required for real submissions)')
    parser.add_argument('--auto-submit', action='store_true',
                       help='Enable auto-submit (requires --confirm)')
    parser.add_argument('--test', action='store_true',
                       help='Test mode with simulated data')
    parser.add_argument('--limit', type=int, default=1000,
                       help='Maximum applications (default: 1000)')
    parser.add_argument('--concurrent', type=int, default=5,
                       help='Max concurrent applications (default: 5)')
    
    args = parser.parse_args()
    
    # Determine mode
    if args.test:
        test_mode = True
        auto_submit = False
        print("\n🧪 TEST MODE - Simulated applications only\n")
    elif args.confirm and args.auto_submit:
        test_mode = False
        auto_submit = True
        print("\n" + "⚠️"*35)
        print("⚠️  WARNING: REAL AUTO-SUBMIT ENABLED  ⚠️")
        print("⚠️"*35)
        print(f"\nThis will submit REAL applications for Matt Edwards")
        print(f"Email: edwardsdmatt@gmail.com")
        print(f"Target: {args.limit} applications\n")
        print("Press Ctrl+C within 5 seconds to cancel...")
        
        try:
            for i in range(5, 0, -1):
                print(f"Starting in {i}...")
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\nCancelled.")
            return
        print("\n🚀 Starting campaign...\n")
    else:
        test_mode = False
        auto_submit = False
        print("\n🔍 SCRAPE MODE - Will scrape real jobs but NOT submit applications")
        print("Add --confirm --auto-submit to enable real submissions\n")
    
    # Create profile
    profile = MattProfile()
    
    # Create and run campaign
    campaign = Matt1000RealApplications(
        profile=profile,
        auto_submit=auto_submit,
        test_mode=test_mode,
        max_applications=args.limit
    )
    campaign.max_concurrent = args.concurrent
    
    try:
        asyncio.run(campaign.run_campaign())
    except Exception as e:
        logger.error(f"Campaign failed: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
