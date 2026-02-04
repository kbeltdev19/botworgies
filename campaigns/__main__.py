#!/usr/bin/env python3
"""
Unified Campaign Runner - Single-command campaign execution.

Usage:
    python -m campaigns run --profile profiles/kevin.yaml --limit 1000
    python -m campaigns quick --name "John Doe" --email "john@example.com" --resume "resume.pdf"
"""

import argparse
import asyncio
import sys
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))


class UnifiedCampaignRunner:
    """Main campaign runner with all optimizations."""
    
    def __init__(self):
        from campaigns.core.browser_pool import get_browser_pool
        from campaigns.core.rate_limiter import get_rate_limiter
        from campaigns.core.batch_processor import BatchProcessor
        from ai.cache.kimi_cache import create_cached_kimi_service
        from campaigns.core.resume_manager import get_resume_manager
        
        self.browser_pool = get_browser_pool(max_sessions=10)
        self.rate_limiter = get_rate_limiter()
        self.batch_processor = BatchProcessor(batch_size=25, max_concurrent=7)
        self.ai_service = create_cached_kimi_service()
        
        self.stats = {
            'jobs_scraped': 0,
            'jobs_processed': 0,
            'jobs_succeeded': 0,
            'jobs_failed': 0,
        }
    
    async def run_from_profile(self, profile_path: str, limit: int = 1000):
        """Run campaign from YAML profile."""
        profile = self._load_profile(profile_path)
        
        logger.info(f"="*70)
        logger.info(f"🚀 RUNNING CAMPAIGN: {profile['name']}")
        logger.info(f"="*70)
        
        # Initialize resume manager
        from campaigns.core.resume_manager import get_resume_manager
        resume_manager = get_resume_manager(profile['resume']['path'])
        
        # Scrape jobs
        jobs = await self._scrape_jobs(profile['search'], limit)
        
        # Process jobs
        results = await self._process_jobs(jobs, profile)
        
        # Print summary
        self._print_summary(results)
        
        return results
    
    async def run_quick(
        self,
        name: str,
        email: str,
        resume_path: str,
        roles: list,
        locations: list,
        limit: int = 100
    ):
        """Quick campaign with minimal config."""
        logger.info(f"="*70)
        logger.info(f"🚀 QUICK CAMPAIGN: {name}")
        logger.info(f"="*70)
        
        profile = {
            'name': name,
            'email': email,
            'resume': {'path': resume_path},
            'search': {
                'roles': roles,
                'locations': locations,
            },
            'strategy': {
                'max_concurrent': 5,
                'delay_range': [5, 15],
                'auto_submit': True,
            }
        }
        
        # Scrape and process
        jobs = await self._scrape_jobs(profile['search'], limit)
        results = await self._process_jobs(jobs, profile)
        
        self._print_summary(results)
        
        return results
    
    def _load_profile(self, path: str) -> Dict:
        """Load YAML profile."""
        with open(path) as f:
            return yaml.safe_load(f)
    
    async def _scrape_jobs(self, search_config: Dict, limit: int) -> list:
        """Scrape jobs using optimized scrapers."""
        from adapters.job_boards import UnifiedJobPipeline, SearchCriteria
        
        logger.info("\n📋 PHASE 1: JOB SCRAPING")
        
        pipeline = UnifiedJobPipeline()
        
        # Add scrapers based on search config
        platforms = search_config.get('platforms', ['indeed', 'linkedin', 'greenhouse', 'lever'])
        
        # Create criteria
        criteria = SearchCriteria(
            query=' OR '.join(search_config['roles']),
            location=search_config.get('locations', ['Remote'])[0],
            remote_only=search_config.get('remote_only', True),
            max_results=limit,
        )
        
        # Scrape
        jobs = await pipeline.search_all(criteria)
        
        self.stats['jobs_scraped'] = len(jobs)
        logger.info(f"✅ Scraped {len(jobs)} jobs")
        
        return jobs
    
    async def _process_jobs(self, jobs: list, profile: Dict) -> list:
        """Process jobs with batch processor."""
        from campaigns.core.batch_processor import BatchJob
        
        logger.info("\n📋 PHASE 2: JOB PROCESSING")
        
        # Convert to BatchJobs
        batch_jobs = []
        for job in jobs:
            platform = getattr(job, 'platform', 'unknown')
            priority = 10 if platform == 'greenhouse' else 20 if platform == 'lever' else 50
            
            batch_jobs.append(BatchJob(
                job_id=getattr(job, 'id', 'unknown'),
                platform=platform,
                job_data={
                    'title': getattr(job, 'title', ''),
                    'company': getattr(job, 'company', ''),
                    'url': getattr(job, 'url', ''),
                    'description': getattr(job, 'description', ''),
                },
                priority=priority
            ))
        
        # Process
        results = await self.batch_processor.process_batch(
            batch_jobs,
            self._apply_to_job,
            browser_manager=None  # Will be created by pool
        )
        
        return results
    
    async def _apply_to_job(self, batch_job, session) -> Dict:
        """Apply to a single job."""
        # This would use the appropriate handler based on platform
        # For now, return placeholder
        return {
            'job_id': batch_job.job_id,
            'platform': batch_job.platform,
            'status': 'processed',
        }
    
    def _print_summary(self, results: list):
        """Print campaign summary."""
        logger.info("\n" + "="*70)
        logger.info("📊 CAMPAIGN SUMMARY")
        logger.info("="*70)
        
        stats = self.batch_processor.get_stats()
        
        logger.info(f"Jobs Scraped: {self.stats['jobs_scraped']}")
        logger.info(f"Jobs Processed: {stats.get('jobs_processed', 0)}")
        logger.info(f"Jobs Succeeded: {stats.get('jobs_succeeded', 0)}")
        logger.info(f"Jobs Failed: {stats.get('jobs_failed', 0)}")
        logger.info(f"Success Rate: {stats.get('success_rate', '0%')}")
        
        # AI cache stats
        ai_stats = self.ai_service.get_stats()
        logger.info(f"\nAI Cache Hit Rate: {ai_stats.get('hit_rate', '0%')}")
        logger.info(f"Estimated Cost Saved: {ai_stats.get('estimated_cost_saved', '$0')}")


def main():
    parser = argparse.ArgumentParser(
        description='Unified Job Application Campaign Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run from profile
  python -m campaigns run --profile profiles/kevin.yaml --limit 1000
  
  # Quick campaign
  python -m campaigns quick --name "John Doe" --email "john@example.com" \\
    --resume "resume.pdf" --roles "Engineer" "Developer" --limit 100
  
  # Dashboard mode
  python -m campaigns dashboard --port 8080
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run campaign from profile')
    run_parser.add_argument('--profile', '-p', required=True, help='Path to YAML profile')
    run_parser.add_argument('--limit', '-l', type=int, default=1000, help='Max jobs to apply')
    run_parser.add_argument('--auto-submit', action='store_true', help='Auto-submit applications')
    
    # Quick command
    quick_parser = subparsers.add_parser('quick', help='Quick campaign with minimal config')
    quick_parser.add_argument('--name', '-n', required=True, help='Candidate name')
    quick_parser.add_argument('--email', '-e', required=True, help='Email address')
    quick_parser.add_argument('--resume', '-r', required=True, help='Path to resume')
    quick_parser.add_argument('--roles', required=True, nargs='+', help='Job titles to search')
    quick_parser.add_argument('--locations', nargs='+', default=['Remote'], help='Locations')
    quick_parser.add_argument('--limit', '-l', type=int, default=100, help='Max jobs')
    
    # Dashboard command
    dashboard_parser = subparsers.add_parser('dashboard', help='Start dashboard')
    dashboard_parser.add_argument('--port', '-p', type=int, default=8080, help='Port')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    runner = UnifiedCampaignRunner()
    
    if args.command == 'run':
        asyncio.run(runner.run_from_profile(args.profile, args.limit))
    elif args.command == 'quick':
        asyncio.run(runner.run_quick(
            name=args.name,
            email=args.email,
            resume_path=args.resume,
            roles=args.roles,
            locations=args.locations,
            limit=args.limit
        ))
    elif args.command == 'dashboard':
        print(f"Dashboard not yet implemented. Port: {args.port}")


if __name__ == '__main__':
    main()
