"""
Unified Job Campaign Runner

Uses the new job board pipeline to scrape from 40+ sources with:
- Intelligent deduplication across boards
- ATS routing for external applications
- Support for all major boards (Dice, ClearanceJobs, Indeed RSS, Greenhouse, Lever)

Usage:
    python unified_campaign_runner.py --query "software engineer" --location "Remote" --limit 500
"""

import asyncio
import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters.job_boards import (
    SearchCriteria, UnifiedJobPipeline, ATSRouter,
    DiceScraper, ClearanceJobsScraper, IndeedRssScraper,
    GreenhouseAPIScraper, LeverAPIScraper
)
from adapters.validation import SubmissionValidator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UnifiedCampaignRunner:
    """
    Campaign runner that scrapes from multiple job boards
    and applies to positions using appropriate ATS handlers.
    """
    
    def __init__(self, output_dir: str = "campaigns/output/unified"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.pipeline = UnifiedJobPipeline()
        self.router = ATSRouter()
        self.results: List[Dict] = []
        
    def setup_scrapers(self, 
                      enable_dice: bool = True,
                      enable_clearancejobs: bool = False,
                      enable_indeed: bool = True,
                      enable_greenhouse: bool = True,
                      enable_lever: bool = True,
                      clearance_creds: Optional[Dict] = None):
        """Configure which scrapers to use."""
        
        if enable_dice:
            self.pipeline.add_scraper(DiceScraper())
            logger.info("✓ Dice scraper enabled")
            
        if enable_clearancejobs and clearance_creds:
            self.pipeline.add_scraper(ClearanceJobsScraper(
                username=clearance_creds.get('username'),
                password=clearance_creds.get('password')
            ))
            logger.info("✓ ClearanceJobs scraper enabled")
            
        if enable_indeed:
            self.pipeline.add_scraper(IndeedRssScraper())
            logger.info("✓ Indeed RSS scraper enabled")
            
        if enable_greenhouse:
            self.pipeline.add_scraper(GreenhouseAPIScraper())
            logger.info("✓ Greenhouse API scraper enabled")
            
        if enable_lever:
            self.pipeline.add_scraper(LeverAPIScraper())
            logger.info("✓ Lever API scraper enabled")
            
    async def run_search(self, criteria: SearchCriteria) -> Dict:
        """Run the job search across all configured boards."""
        logger.info(f"Searching for: {criteria.query} in {criteria.location or 'any location'}")
        logger.info(f"Max results: {criteria.max_results}")
        
        start_time = datetime.now()
        
        # Run search
        jobs = await self.pipeline.search_all(criteria)
        
        search_duration = (datetime.now() - start_time).total_seconds()
        
        # Get stats
        stats = self.pipeline.get_stats()
        
        # Categorize by ATS type
        ats_breakdown = {}
        for job in jobs:
            ats = self.router.detect_ats(job.url) or 'unknown'
            ats_breakdown[ats] = ats_breakdown.get(ats, 0) + 1
            
        # Check for direct application URLs
        direct_urls = sum(1 for job in jobs if self.router.is_direct_application_url(job.url))
        
        result = {
            'search_criteria': {
                'query': criteria.query,
                'location': criteria.location,
                'remote_only': criteria.remote_only,
                'max_results': criteria.max_results,
            },
            'results': {
                'total_unique_jobs': len(jobs),
                'direct_apply_urls': direct_urls,
                'career_page_urls': len(jobs) - direct_urls,
                'by_source': stats['by_source'],
                'by_ats': ats_breakdown,
            },
            'deduplication': {
                'total_seen': stats['total_seen'],
                'duplicates_filtered': stats['duplicates_filtered'],
                'dedup_rate': f"{(stats['duplicates_filtered'] / max(stats['total_seen'], 1) * 100):.1f}%"
            },
            'performance': {
                'search_duration_seconds': search_duration,
                'jobs_per_second': len(jobs) / max(search_duration, 1)
            },
            'jobs': [
                {
                    'id': job.id,
                    'title': job.title,
                    'company': job.company,
                    'location': job.location,
                    'source': job.source,
                    'ats_type': self.router.detect_ats(job.url),
                    'is_direct_apply': self.router.is_direct_application_url(job.url),
                    'apply_url': job.apply_url,
                    'remote': job.remote,
                    'clearance_required': job.clearance_required,
                    'posted_date': job.posted_date.isoformat() if job.posted_date else None,
                }
                for job in jobs
            ]
        }
        
        self.results = result
        return result
        
    def save_results(self, filename: Optional[str] = None):
        """Save search results to JSON."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"unified_search_{timestamp}.json"
            
        filepath = self.output_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2)
            
        logger.info(f"Results saved to {filepath}")
        
        # Also save as CSV for easy viewing
        csv_path = filepath.with_suffix('.csv')
        self._save_csv(csv_path)
        
        return filepath
        
    def _save_csv(self, filepath: Path):
        """Save jobs as CSV."""
        import csv
        
        jobs = self.results.get('jobs', [])
        if not jobs:
            return
            
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'id', 'title', 'company', 'location', 'source',
                'ats_type', 'is_direct_apply', 'apply_url', 'remote'
            ])
            writer.writeheader()
            writer.writerows(jobs)
            
        logger.info(f"CSV saved to {filepath}")
        
    def print_summary(self):
        """Print a summary of the search results."""
        if not self.results:
            print("No results to display")
            return
            
        print("\n" + "="*60)
        print("UNIFIED JOB SEARCH RESULTS")
        print("="*60)
        
        criteria = self.results['search_criteria']
        print(f"\nSearch: {criteria['query']} in {criteria['location'] or 'Any Location'}")
        print(f"Remote only: {criteria['remote_only']}")
        
        results = self.results['results']
        print(f"\n📊 RESULTS:")
        print(f"  Total unique jobs: {results['total_unique_jobs']}")
        print(f"  Direct apply URLs: {results['direct_apply_urls']}")
        print(f"  Career page URLs: {results['career_page_urls']}")
        
        print(f"\n📡 BY SOURCE:")
        for source, count in sorted(results['by_source'].items(), key=lambda x: -x[1]):
            print(f"  {source}: {count}")
            
        print(f"\n🎯 BY ATS TYPE:")
        for ats, count in sorted(results['by_ats'].items(), key=lambda x: -x[1]):
            pct = (count / results['total_unique_jobs']) * 100
            print(f"  {ats}: {count} ({pct:.1f}%)")
            
        dedup = self.results['deduplication']
        print(f"\n🔄 DEDUPLICATION:")
        print(f"  Total seen: {dedup['total_seen']}")
        print(f"  Duplicates filtered: {dedup['duplicates_filtered']}")
        print(f"  Dedup rate: {dedup['dedup_rate']}")
        
        perf = self.results['performance']
        print(f"\n⚡ PERFORMANCE:")
        print(f"  Duration: {perf['search_duration_seconds']:.1f}s")
        print(f"  Speed: {perf['jobs_per_second']:.1f} jobs/sec")
        
        print("\n" + "="*60)


async def main():
    parser = argparse.ArgumentParser(
        description='Unified Job Board Campaign Runner'
    )
    parser.add_argument('--query', '-q', default='software engineer',
                       help='Job search query')
    parser.add_argument('--location', '-l', default='Remote',
                       help='Job location')
    parser.add_argument('--limit', '-n', type=int, default=100,
                       help='Maximum jobs to fetch')
    parser.add_argument('--remote-only', action='store_true',
                       help='Only remote jobs')
    parser.add_argument('--enable-clearancejobs', action='store_true',
                       help='Enable ClearanceJobs (requires credentials)')
    parser.add_argument('--clearance-user', help='ClearanceJobs username')
    parser.add_argument('--clearance-pass', help='ClearanceJobs password')
    parser.add_argument('--disable-dice', action='store_true',
                       help='Disable Dice scraper')
    parser.add_argument('--disable-indeed', action='store_true',
                       help='Disable Indeed scraper')
    parser.add_argument('--disable-greenhouse', action='store_true',
                       help='Disable Greenhouse scraper')
    parser.add_argument('--disable-lever', action='store_true',
                       help='Disable Lever scraper')
    parser.add_argument('--output', '-o', default='campaigns/output/unified',
                       help='Output directory')
    parser.add_argument('--save', '-s', action='store_true',
                       help='Save results to file')
    
    args = parser.parse_args()
    
    # Create runner
    runner = UnifiedCampaignRunner(output_dir=args.output)
    
    # Setup scrapers
    clearance_creds = None
    if args.enable_clearancejobs:
        if not args.clearance_user or not args.clearance_pass:
            print("Error: ClearanceJobs requires --clearance-user and --clearance-pass")
            return
        clearance_creds = {
            'username': args.clearance_user,
            'password': args.clearance_pass
        }
        
    runner.setup_scrapers(
        enable_dice=not args.disable_dice,
        enable_clearancejobs=args.enable_clearancejobs,
        enable_indeed=not args.disable_indeed,
        enable_greenhouse=not args.disable_greenhouse,
        enable_lever=not args.disable_lever,
        clearance_creds=clearance_creds
    )
    
    # Create search criteria
    criteria = SearchCriteria(
        query=args.query,
        location=args.location,
        remote_only=args.remote_only,
        max_results=args.limit
    )
    
    # Run search
    async with runner.pipeline.scrapers[0] if runner.pipeline.scrapers else None:
        results = await runner.run_search(criteria)
        
    # Print summary
    runner.print_summary()
    
    # Save if requested
    if args.save:
        filepath = runner.save_results()
        print(f"\n💾 Results saved to: {filepath}")


if __name__ == "__main__":
    asyncio.run(main())
