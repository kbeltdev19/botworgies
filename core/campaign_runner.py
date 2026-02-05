#!/usr/bin/env python3
"""
Unified Campaign Runner - Updated for Consolidated Architecture

Uses the new unified core modules:
- core.browser.UnifiedBrowserManager (Stagehand)
- core.ai.UnifiedAIService (Moonshot)
- adapters.UnifiedPlatformAdapter (AI-powered)
"""

import asyncio
import logging
import random
import yaml
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# New unified imports
from core.models import (
    JobPosting, UserProfile, Resume, ApplicationResult, 
    SearchConfig, PlatformType, ApplicationStatus
)
from core.browser import UnifiedBrowserManager
from core.ai import UnifiedAIService
from adapters import UnifiedPlatformAdapter, get_adapter

logger = logging.getLogger(__name__)


@dataclass
class CampaignConfig:
    """Configuration for a job application campaign."""
    name: str
    applicant_profile: UserProfile
    resume: Resume
    search_criteria: SearchConfig
    platforms: List[str] = field(default_factory=lambda: ['greenhouse', 'lever'])
    max_applications: int = 10  # Conservative default
    max_per_platform: Optional[int] = None
    auto_submit: bool = False
    min_match_score: float = 0.6
    exclude_companies: List[str] = field(default_factory=list)
    exclude_titles: List[str] = field(default_factory=list)
    delay_between_applications: Tuple[int, int] = (30, 60)
    delay_between_platforms: int = 300
    max_concurrent: int = 1
    retry_attempts: int = 3
    retry_delay: int = 300
    job_file: Optional[str] = None
    output_dir: Path = field(default_factory=lambda: Path("./campaign_output"))
    save_screenshots: bool = True
    generate_report: bool = True
    use_unified_adapter: bool = False  # Use legacy adapters (unified requires OpenAI)


@dataclass
class CampaignResult:
    """Result of a campaign run."""
    campaign_name: str
    start_time: datetime
    end_time: datetime
    total_jobs: int
    attempted: int
    successful: int
    failed: int
    skipped: int
    results: List[ApplicationResult]
    platform_stats: Dict[str, Dict[str, Any]]
    
    @property
    def duration_seconds(self) -> float:
        return (self.end_time - self.start_time).total_seconds()
    
    @property
    def success_rate(self) -> float:
        if self.attempted == 0:
            return 0.0
        return self.successful / self.attempted
    
    def to_dict(self) -> Dict:
        return {
            "campaign_name": self.campaign_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": self.duration_seconds,
            "total_jobs": self.total_jobs,
            "attempted": self.attempted,
            "successful": self.successful,
            "failed": self.failed,
            "skipped": self.skipped,
            "success_rate": self.success_rate,
            "platform_stats": self.platform_stats,
        }


class CampaignRunner:
    """
    Unified campaign runner using the new consolidated architecture.
    
    Usage:
        config = CampaignRunner.load_config("campaigns/configs/my_campaign.yaml")
        runner = CampaignRunner(config)
        result = await runner.run()
    """
    
    def __init__(self, config: CampaignConfig):
        self.config = config
        self.browser = UnifiedBrowserManager()
        self.ai = UnifiedAIService()
        self.results: List[ApplicationResult] = []
        self.platform_counts: Dict[str, int] = {}
        
        # Create output directory
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def run(self) -> CampaignResult:
        """Execute the campaign."""
        start_time = datetime.now()
        logger.info(f"🚀 Starting campaign: {self.config.name}")
        logger.info(f"👤 Applicant: {self.config.applicant_profile.full_name}")
        logger.info(f"🎯 Max Applications: {self.config.max_applications}")
        logger.info(f"✅ Auto-Submit: {self.config.auto_submit}")
        
        # Initialize browser
        await self.browser.init()
        
        try:
            # 1. Search for jobs
            all_jobs = await self._search_all_platforms()
            
            # 2. Filter and rank jobs
            filtered_jobs = self._filter_jobs(all_jobs)
            
            # 3. Apply to each job
            for i, job in enumerate(filtered_jobs[:self.config.max_applications]):
                logger.info(f"\n[{i+1}/{min(len(filtered_jobs), self.config.max_applications)}] {job.title} at {job.company}")
                
                # Apply with retry
                result = await self._apply_with_retry(job)
                self.results.append(result)
                
                # Update stats
                platform_key = job.platform.value if hasattr(job.platform, 'value') else str(job.platform)
                self.platform_counts[platform_key] = self.platform_counts.get(platform_key, 0) + 1
                
                # Log progress
                self._log_progress(i + 1)
                
                # Rate limiting
                if i < len(filtered_jobs) - 1 and i < self.config.max_applications - 1:
                    delay = random.randint(*self.config.delay_between_applications)
                    logger.info(f"⏱️  Waiting {delay}s before next application...")
                    await asyncio.sleep(delay)
            
        finally:
            # Cleanup
            await self.browser.close_all()
        
        end_time = datetime.now()
        
        # Build result
        result = CampaignResult(
            campaign_name=self.config.name,
            start_time=start_time,
            end_time=end_time,
            total_jobs=len(filtered_jobs),
            attempted=len(self.results),
            successful=sum(1 for r in self.results if r.success),
            failed=sum(1 for r in self.results if not r.success),
            skipped=len(filtered_jobs) - len(self.results),
            results=self.results,
            platform_stats=self._calculate_platform_stats()
        )
        
        # Save results
        if self.config.generate_report:
            self._save_results(result)
        
        self._print_summary(result)
        
        return result
    
    async def _search_all_platforms(self) -> List[JobPosting]:
        """Search for jobs across all configured platforms."""
        all_jobs = []
        
        # Try to load from job file first
        if self.config.job_file and Path(self.config.job_file).exists():
            logger.info(f"📁 Loading jobs from file: {self.config.job_file}")
            try:
                data = json.loads(Path(self.config.job_file).read_text())
                # Handle both list format and dict with 'jobs' key
                if isinstance(data, list):
                    file_jobs = data
                else:
                    file_jobs = data.get('jobs', [])
                for job_data in file_jobs:
                    all_jobs.append(JobPosting(
                        id=job_data.get('id', f"file_{len(all_jobs)}"),
                        platform=PlatformType(job_data.get('platform', 'external')),
                        title=job_data.get('title', 'Unknown'),
                        company=job_data.get('company', 'Unknown'),
                        location=job_data.get('location', 'Remote'),
                        url=job_data.get('url', ''),
                        description=job_data.get('description', ''),
                        easy_apply=job_data.get('easy_apply', True),
                        remote=job_data.get('is_remote', True)
                    ))
                logger.info(f"✅ Loaded {len(all_jobs)} jobs from file")
                return all_jobs
            except Exception as e:
                logger.error(f"❌ Failed to load job file: {e}")
        
        # Search via adapters
        for platform_name in self.config.platforms:
            try:
                logger.info(f"🔍 Searching {platform_name}...")
                
                if self.config.use_unified_adapter:
                    # Use new unified adapter
                    adapter = UnifiedPlatformAdapter(
                        user_profile=self.config.applicant_profile,
                        browser_manager=self.browser,
                        ai_service=self.ai
                    )
                else:
                    # Use legacy adapter
                    adapter = get_adapter(platform_name, self.browser)
                
                jobs = await adapter.search_jobs(self.config.search_criteria)
                logger.info(f"✅ Found {len(jobs)} jobs on {platform_name}")
                all_jobs.extend(jobs)
                
                # Delay between platforms
                if platform_name != self.config.platforms[-1]:
                    await asyncio.sleep(self.config.delay_between_platforms)
                    
            except Exception as e:
                logger.error(f"❌ Failed to search {platform_name}: {e}")
                continue
        
        logger.info(f"📊 Total jobs found: {len(all_jobs)}")
        return all_jobs
    
    def _filter_jobs(self, jobs: List[JobPosting]) -> List[JobPosting]:
        """Filter and rank jobs based on criteria."""
        filtered = []
        seen = set()
        
        for job in jobs:
            # Deduplicate
            key = f"{job.company}_{job.title}"
            if key in seen:
                continue
            seen.add(key)
            
            # Check exclusions
            if any(excluded.lower() in job.company.lower() 
                   for excluded in self.config.exclude_companies):
                continue
            
            if any(excluded.lower() in job.title.lower() 
                   for excluded in self.config.exclude_titles):
                continue
            
            # Check platform limit
            platform_key = job.platform.value if hasattr(job.platform, 'value') else str(job.platform)
            if self.config.max_per_platform and self.platform_counts.get(platform_key, 0) >= self.config.max_per_platform:
                continue
            
            # Calculate match score
            score = self._calculate_match_score(job)
            if score < self.config.min_match_score:
                continue
            
            filtered.append(job)
        
        # Sort by match score
        filtered.sort(key=lambda j: self._calculate_match_score(j), reverse=True)
        
        logger.info(f"🎯 Filtered to {len(filtered)} jobs")
        return filtered
    
    def _calculate_match_score(self, job: JobPosting) -> float:
        """Calculate how well a job matches search criteria."""
        score = 0.5  # Base score
        
        # Title match
        if self.config.search_criteria.roles:
            title_lower = job.title.lower()
            for role in self.config.search_criteria.roles:
                if role.lower() in title_lower:
                    score += 0.2
                    break
        
        # Keyword match
        if job.description and self.config.search_criteria.required_keywords:
            desc_lower = job.description.lower()
            matched = sum(1 for kw in self.config.search_criteria.required_keywords 
                         if kw.lower() in desc_lower)
            score += 0.2 * (matched / len(self.config.search_criteria.required_keywords))
        
        # Easy apply bonus
        if job.easy_apply:
            score += 0.1
        
        return min(score, 1.0)
    
    async def _apply_with_retry(self, job: JobPosting) -> ApplicationResult:
        """Apply to a job with retry logic."""
        for attempt in range(self.config.retry_attempts):
            try:
                if self.config.use_unified_adapter:
                    # Use new unified adapter
                    adapter = UnifiedPlatformAdapter(
                        user_profile=self.config.applicant_profile,
                        browser_manager=self.browser,
                        ai_service=self.ai
                    )
                    result = await adapter.apply(job, self.config.resume)
                else:
                    # Use legacy adapter
                    adapter = get_adapter(job.platform.value, self.browser)
                    result = await adapter.apply_to_job(
                        job=job,
                        resume=self.config.resume,
                        profile=self.config.applicant_profile,
                        auto_submit=self.config.auto_submit
                    )
                
                if result.success:
                    logger.info(f"✅ Application successful! Confirmation: {result.confirmation_id}")
                    return result
                else:
                    logger.warning(f"⚠️  Application failed: {result.message}")
                    if attempt == 0:
                        return result
                    
            except Exception as e:
                logger.error(f"❌ Attempt {attempt + 1} failed: {e}")
                
                if attempt < self.config.retry_attempts - 1:
                    logger.info(f"⏱️  Waiting {self.config.retry_delay}s before retry...")
                    await asyncio.sleep(self.config.retry_delay)
        
        return ApplicationResult(
            status=ApplicationStatus.ERROR,
            message=f"Failed after {self.config.retry_attempts} attempts"
        )
    
    def _log_progress(self, current: int):
        """Log campaign progress."""
        successful = sum(1 for r in self.results if r.success)
        rate = successful / len(self.results) * 100 if self.results else 0
        logger.info(f"📈 Progress: {current} processed, {successful} successful ({rate:.1f}%)")
    
    def _calculate_platform_stats(self) -> Dict[str, Dict[str, Any]]:
        """Calculate statistics per platform."""
        stats = {}
        
        for result in self.results:
            platform = result.platform if hasattr(result, 'platform') else 'unknown'
            
            if platform not in stats:
                stats[platform] = {'attempted': 0, 'successful': 0, 'failed': 0}
            
            stats[platform]['attempted'] += 1
            if result.success:
                stats[platform]['successful'] += 1
            else:
                stats[platform]['failed'] += 1
        
        for platform, data in stats.items():
            data['success_rate'] = data['successful'] / data['attempted'] if data['attempted'] > 0 else 0
        
        return stats
    
    def _save_results(self, result: CampaignResult):
        """Save campaign results to file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = self.config.name.replace(' ', '_').replace('/', '_')
        
        # JSON results
        json_path = self.config.output_dir / f"{safe_name}_{timestamp}.json"
        json_path.write_text(json.dumps(result.to_dict(), indent=2))
        
        # Text summary
        summary_path = self.config.output_dir / f"{safe_name}_{timestamp}.txt"
        summary_path.write_text(self._generate_text_report(result))
        
        logger.info(f"💾 Results saved to {self.config.output_dir}")
    
    def _generate_text_report(self, result: CampaignResult) -> str:
        """Generate text report."""
        report = f"""
{'='*70}
CAMPAIGN REPORT: {result.campaign_name}
{'='*70}

Duration: {result.duration_seconds / 60:.1f} minutes

SUMMARY:
  Total Jobs Found: {result.total_jobs}
  Attempted: {result.attempted}
  Successful: {result.successful}
  Failed: {result.failed}
  Skipped: {result.skipped}
  Success Rate: {result.success_rate * 100:.1f}%

PLATFORM BREAKDOWN:
"""
        for platform, stats in result.platform_stats.items():
            report += f"  {platform:15s}: {stats['successful']}/{stats['attempted']} ({stats['success_rate']*100:.1f}%)\n"
        
        report += "\n" + "="*70 + "\n"
        return report
    
    def _print_summary(self, result: CampaignResult):
        """Print campaign summary to console."""
        print("\n" + "="*70)
        print(f"🎉 CAMPAIGN COMPLETE: {result.campaign_name}")
        print("="*70)
        print(f"⏱️  Duration: {result.duration_seconds / 60:.1f} minutes")
        print(f"✅ Success Rate: {result.success_rate * 100:.1f}%")
        print(f"📝 Successful: {result.successful}/{result.attempted}")
        print("="*70 + "\n")
    
    @staticmethod
    def load_config(path: Path) -> CampaignConfig:
        """Load campaign configuration from YAML file."""
        data = yaml.safe_load(path.read_text())
        
        # Handle both old and new YAML formats
        
        # Build SearchConfig
        search_data = data.get('search', {})
        search_criteria = SearchConfig(
            roles=search_data.get('roles', []),
            locations=search_data.get('locations', ['Remote']),
            required_keywords=search_data.get('required_keywords', []),
            exclude_keywords=search_data.get('exclude_keywords', []),
            easy_apply_only=search_data.get('easy_apply_only', False),
        )
        
        # Build UserProfile (support both old and new formats)
        applicant_data = data.get('applicant', {})
        if not applicant_data:
            # Old format - top level fields
            applicant_data = {
                'first_name': data.get('name', '').split()[0] if data.get('name') else '',
                'last_name': ' '.join(data.get('name', '').split()[1:]) if data.get('name') else '',
                'email': data.get('email', ''),
                'phone': data.get('phone', ''),
                'location': data.get('location', ''),
            }
        
        profile = UserProfile(
            first_name=applicant_data.get('first_name', ''),
            last_name=applicant_data.get('last_name', ''),
            email=applicant_data.get('email', ''),
            phone=applicant_data.get('phone', ''),
            linkedin_url=applicant_data.get('linkedin_url') or applicant_data.get('linkedin', ''),
            location=applicant_data.get('location', ''),
            years_experience=applicant_data.get('years_experience'),
            custom_answers=applicant_data.get('custom_answers', {})
        )
        
        # Build Resume
        resume_data = data.get('resume', {})
        if not resume_data:
            # Old format
            resume_path = data.get('resume_path', '')
        else:
            resume_path = resume_data.get('path', '')
        
        resume = Resume(
            file_path=resume_path,
            raw_text="",
            parsed_data={}
        )
        
        # Get strategy settings
        strategy = data.get('strategy', {})
        targets = data.get('targets', {})
        
        return CampaignConfig(
            name=data.get('name', 'Unnamed Campaign'),
            applicant_profile=profile,
            resume=resume,
            search_criteria=search_criteria,
            platforms=search_data.get('platforms', ['greenhouse', 'lever']),
            max_applications=targets.get('total', 10),
            max_per_platform=targets.get('daily_max'),
            auto_submit=strategy.get('auto_submit', False),
            delay_between_applications=strategy.get('delay_range', [30, 60]),
            output_dir=Path(data.get('output', {}).get('directory', './campaign_output')),
            save_screenshots=data.get('output', {}).get('save_screenshots', True),
            job_file=data.get('job_file')
        )
