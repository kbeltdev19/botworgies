#!/usr/bin/env python3
"""
Unified Campaign - Combines job discovery with application.

This campaign:
1. Discovers jobs from multiple sources (JobSpy Indeed/ZipRecruiter)
2. Filters by keywords
3. Applies using appropriate handlers
4. Tracks results
"""

import asyncio
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, field

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class CampaignConfig:
    """Campaign configuration."""
    profile_path: str
    resume_path: str
    target_jobs: int = 100
    daily_limit: int = 100
    keywords: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=lambda: ["Remote", "United States"])
    sources: List[str] = field(default_factory=lambda: ["indeed", "zip_recruiter"])
    use_visual_agent: bool = True
    skip_linkedin: bool = True


@dataclass
class CampaignStats:
    """Campaign statistics."""
    jobs_discovered: int = 0
    jobs_filtered: int = 0
    applications_attempted: int = 0
    applications_successful: int = 0
    applications_failed: int = 0
    by_platform: Dict[str, Dict[str, int]] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.now)
    
    @property
    def elapsed_minutes(self) -> float:
        return (datetime.now() - self.start_time).total_seconds() / 60
    
    @property
    def success_rate(self) -> float:
        if self.applications_attempted == 0:
            return 0.0
        return (self.applications_successful / self.applications_attempted) * 100


class UnifiedCampaign:
    """
    Unified campaign that discovers and applies to jobs.
    """
    
    def __init__(self, config: CampaignConfig):
        self.config = config
        self.stats = CampaignStats()
        self.results: List[Dict] = []
        self.discovered_jobs: List[Dict] = []
        
        # Output directory
        self.output_dir = Path("campaigns/output")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Checkpoint file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.checkpoint_file = self.output_dir / f"unified_campaign_{timestamp}.json"
    
    async def run(self):
        """Run the complete campaign."""
        logger.info("=" * 60)
        logger.info("Starting Unified Campaign")
        logger.info("=" * 60)
        logger.info(f"Target: {self.config.target_jobs} jobs")
        logger.info(f"Daily limit: {self.config.daily_limit}")
        logger.info(f"Sources: {self.config.sources}")
        logger.info(f"Locations: {self.config.locations}")
        logger.info("=" * 60)
        
        try:
            # Phase 1: Discover jobs
            await self._discover_jobs()
            
            # Phase 2: Filter jobs
            await self._filter_jobs()
            
            # Phase 3: Apply to jobs
            await self._apply_to_jobs()
            
            # Phase 4: Generate report
            await self._generate_report()
            
        except Exception as e:
            logger.error(f"Campaign failed: {e}")
            raise
    
    async def _discover_jobs(self):
        """Discover jobs from all sources."""
        logger.info("\n[Phase 1] Discovering jobs...")
        
        from campaigns.job_discovery import JobDiscoveryPipeline
        
        pipeline = JobDiscoveryPipeline(output_dir=str(self.output_dir))
        
        # Use default keywords if none provided
        keywords = self.config.keywords or [
            "Software Engineer",
            "DevOps Engineer", 
            "IT Manager",
            "Product Manager",
            "Data Engineer"
        ]
        
        # Discover from JobSpy
        jobs = await pipeline.discover_from_jobspy(
            queries=keywords,
            locations=self.config.locations,
            sites=self.config.sources,
            max_results_per_query=min(self.config.target_jobs // len(keywords) + 10, 50),
            posted_within_days=7
        )
        
        self.discovered_jobs = [job.to_dict() for job in jobs]
        self.stats.jobs_discovered = len(jobs)
        
        logger.info(f"[Discovery] Found {len(jobs)} jobs")
        
        # Show breakdown by source
        by_source = {}
        for job in jobs:
            source = job.source
            by_source[source] = by_source.get(source, 0) + 1
        
        logger.info("[Discovery] By source:")
        for source, count in by_source.items():
            logger.info(f"  - {source}: {count}")
    
    async def _filter_jobs(self):
        """Filter jobs by relevance."""
        logger.info("\n[Phase 2] Filtering jobs...")
        
        # Keywords for filtering
        filter_keywords = [
            'software', 'engineer', 'developer', 'devops', 'manager',
            'product', 'data', 'cloud', 'senior', 'staff', 'principal'
        ]
        
        filtered = []
        for job in self.discovered_jobs:
            title = job.get('title', '').lower()
            
            # Check if title contains any filter keyword
            if any(kw in title for kw in filter_keywords):
                filtered.append(job)
        
        self.discovered_jobs = filtered[:self.config.target_jobs]
        self.stats.jobs_filtered = len(self.discovered_jobs)
        
        logger.info(f"[Filter] {len(filtered)} jobs after filtering")
        logger.info(f"[Filter] Limited to {len(self.discovered_jobs)} jobs for campaign")
    
    async def _apply_to_jobs(self):
        """Apply to discovered jobs."""
        logger.info("\n[Phase 3] Applying to jobs...")
        
        from campaigns.campaign_runner_v2 import CampaignRunnerV2, CampaignConfig as RunnerConfig
        
        # Create runner config
        runner_config = RunnerConfig(
            profile_path=self.config.profile_path,
            resume_path=self.config.resume_path,
            target_jobs=self.config.target_jobs,
            daily_limit=self.config.daily_limit,
            use_visual_agent=self.config.use_visual_agent
        )
        
        # Initialize runner
        runner = CampaignRunnerV2(runner_config)
        await runner.initialize()
        
        # Apply to each job
        for i, job in enumerate(self.discovered_jobs, 1):
            if self.stats.applications_attempted >= self.config.daily_limit:
                logger.info(f"[Apply] Daily limit ({self.config.daily_limit}) reached")
                break
            
            logger.info(f"\n[Apply] ({i}/{len(self.discovered_jobs)}) {job.get('title')} @ {job.get('company')}")
            
            try:
                # Convert job format for runner
                job_for_runner = {
                    'id': job.get('id'),
                    'title': job.get('title'),
                    'company': job.get('company'),
                    'location': job.get('location'),
                    'url': job.get('url'),
                    'platform': job.get('platform', 'unknown'),
                    'description': job.get('description', ''),
                }
                
                result = await runner._apply_to_job(job_for_runner)
                
                self.stats.applications_attempted += 1
                
                if result.get('success'):
                    self.stats.applications_successful += 1
                    platform = job.get('platform', 'unknown')
                    
                    if platform not in self.stats.by_platform:
                        self.stats.by_platform[platform] = {'attempted': 0, 'successful': 0}
                    self.stats.by_platform[platform]['attempted'] += 1
                    self.stats.by_platform[platform]['successful'] += 1
                    
                    logger.info(f"[Apply] ✅ SUCCESS")
                else:
                    self.stats.applications_failed += 1
                    logger.warning(f"[Apply] ❌ FAILED: {result.get('error', 'Unknown')}")
                
                self.results.append({
                    'job': job,
                    'result': result,
                    'timestamp': datetime.now().isoformat()
                })
                
                # Save checkpoint periodically
                if i % 10 == 0:
                    await self._save_checkpoint()
                
                # Small delay between applications
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"[Apply] Error: {e}")
                self.stats.applications_failed += 1
                continue
        
        logger.info(f"[Apply] Complete: {self.stats.applications_successful}/{self.stats.applications_attempted} successful")
    
    async def _generate_report(self):
        """Generate final campaign report."""
        logger.info("\n[Phase 4] Generating report...")
        
        report = {
            'campaign_config': {
                'target_jobs': self.config.target_jobs,
                'daily_limit': self.config.daily_limit,
                'sources': self.config.sources,
                'locations': self.config.locations,
            },
            'stats': {
                'jobs_discovered': self.stats.jobs_discovered,
                'jobs_filtered': self.stats.jobs_filtered,
                'applications_attempted': self.stats.applications_attempted,
                'applications_successful': self.stats.applications_successful,
                'applications_failed': self.stats.applications_failed,
                'success_rate': self.stats.success_rate,
                'elapsed_minutes': self.stats.elapsed_minutes,
                'by_platform': self.stats.by_platform,
            },
            'results': self.results,
            'generated_at': datetime.now().isoformat()
        }
        
        # Save report
        report_path = self.output_dir / f"unified_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info("=" * 60)
        logger.info("Campaign Complete!")
        logger.info("=" * 60)
        logger.info(f"Jobs discovered: {self.stats.jobs_discovered}")
        logger.info(f"Jobs filtered: {self.stats.jobs_filtered}")
        logger.info(f"Applications attempted: {self.stats.applications_attempted}")
        logger.info(f"Applications successful: {self.stats.applications_successful}")
        logger.info(f"Success rate: {self.stats.success_rate:.1f}%")
        logger.info(f"Elapsed time: {self.stats.elapsed_minutes:.1f} minutes")
        logger.info(f"Report saved: {report_path}")
        logger.info("=" * 60)
    
    async def _save_checkpoint(self):
        """Save campaign checkpoint."""
        checkpoint = {
            'stats': {
                'jobs_discovered': self.stats.jobs_discovered,
                'applications_attempted': self.stats.applications_attempted,
                'applications_successful': self.stats.applications_successful,
            },
            'results': self.results[-10:] if self.results else [],  # Last 10 results
            'timestamp': datetime.now().isoformat()
        }
        
        with open(self.checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)


async def main():
    """Run unified campaign."""
    parser = argparse.ArgumentParser(description='Unified Job Campaign')
    parser.add_argument('--profile', required=True, help='Path to profile YAML')
    parser.add_argument('--resume', required=True, help='Path to resume PDF')
    parser.add_argument('--target', type=int, default=50, help='Target number of jobs')
    parser.add_argument('--daily-limit', type=int, default=50, help='Daily application limit')
    parser.add_argument('--keywords', nargs='+', help='Job search keywords')
    parser.add_argument('--locations', nargs='+', default=['Remote', 'United States'])
    parser.add_argument('--no-visual', action='store_true', help='Disable Visual Form Agent')
    
    args = parser.parse_args()
    
    config = CampaignConfig(
        profile_path=args.profile,
        resume_path=args.resume,
        target_jobs=args.target,
        daily_limit=args.daily_limit,
        keywords=args.keywords or [],
        locations=args.locations,
        use_visual_agent=not args.no_visual
    )
    
    campaign = UnifiedCampaign(config)
    await campaign.run()


if __name__ == "__main__":
    asyncio.run(main())
