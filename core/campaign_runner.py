"""
Unified Campaign Runner

Replaces 20+ individual campaign files with a single configurable runner.
Campaigns are defined via YAML configuration files, not code.
"""

import asyncio
import logging
import random
import yaml
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from adapters.base import JobPosting, UserProfile, Resume, ApplicationResult, SearchConfig, PlatformType
from .adapter_base import UnifiedJobAdapter
from monitoring.application_monitor import get_monitor
from monitoring.iteration_engine import get_iteration_engine
from browser.stealth_manager import StealthBrowserManager

logger = logging.getLogger(__name__)


@dataclass
class CampaignConfig:
    """Configuration for a job application campaign."""
    # Identity
    name: str
    applicant_profile: UserProfile
    resume: Resume
    
    # Job search criteria
    search_criteria: SearchConfig
    platforms: List[str] = field(default_factory=lambda: ['greenhouse', 'lever'])
    
    # Limits
    max_applications: int = 100
    max_per_platform: Optional[int] = None
    
    # Application settings
    auto_submit: bool = False
    min_match_score: float = 0.6
    exclude_companies: List[str] = field(default_factory=list)
    exclude_titles: List[str] = field(default_factory=list)
    
    # Rate limiting
    delay_between_applications: Tuple[int, int] = (30, 60)
    delay_between_platforms: int = 300  # 5 minutes
    max_concurrent: int = 1  # Sequential by default for safety
    
    # Retry settings
    retry_attempts: int = 3
    retry_delay: int = 300
    
    # Features
    enable_iteration: bool = True
    enable_monitoring: bool = True
    stop_on_low_success_rate: bool = True
    min_success_rate: float = 0.3
    
    # Job source
    job_file: Optional[str] = None  # Path to JSON file with pre-scraped jobs
    
    # Output
    output_dir: Path = field(default_factory=lambda: Path("./campaign_output"))
    save_screenshots: bool = True
    generate_report: bool = True


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
    Unified campaign runner for job applications.
    
    Replaces individual campaign files (matt_1000.py, kevin_1000.py, etc.)
    with a single configurable runner.
    
    Usage:
        # Load campaign from YAML
        config = CampaignRunner.load_config("campaigns/matt_edwards.yaml")
        
        # Run campaign
        runner = CampaignRunner(config)
        result = await runner.run()
        
        # Save results
        runner.save_results(result)
    
    Example YAML config:
        ```yaml
        name: "Matt Edwards - 1000 Applications"
        
        applicant:
          first_name: "Matt"
          last_name: "Edwards"
          email: "matt@example.com"
          phone: "555-123-4567"
          linkedin_url: "https://linkedin.com/in/mattedwards"
          years_experience: 5
          custom_answers:
            salary_expectations: "$100k - $130k"
            notice_period: "2 weeks"
        
        resume:
          path: "/path/to/resume.pdf"
        
        search:
          roles:
            - "Software Engineer"
            - "Backend Developer"
          locations:
            - "Remote"
            - "San Francisco"
          required_keywords:
            - "Python"
            - "AWS"
        
        platforms:
          - greenhouse
          - lever
          - linkedin
        
        limits:
          max_applications: 1000
          max_per_platform: 400
        
        settings:
          auto_submit: false
          delay_between_applications: [30, 60]
          retry_attempts: 3
        ```
    """
    
    def __init__(self, config: CampaignConfig):
        self.config = config
        self.browser = StealthBrowserManager()
        self.monitor = get_monitor() if config.enable_monitoring else None
        self.iterator = get_iteration_engine() if config.enable_iteration else None
        
        # Create output directory
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Stats
        self.results: List[ApplicationResult] = []
        self.platform_counts: Dict[str, int] = {}
    
    async def run(self) -> CampaignResult:
        """Execute the campaign."""
        start_time = datetime.now()
        logger.info(f"Starting campaign: {self.config.name}")
        logger.info(f"Configuration: {self.config}")
        
        # 1. Search for jobs across platforms
        all_jobs = await self._search_all_platforms()
        
        # 2. Filter and rank jobs
        filtered_jobs = self._filter_jobs(all_jobs)
        
        # 3. Apply to each job
        for i, job in enumerate(filtered_jobs[:self.config.max_applications]):
            logger.info(f"\n[{i+1}/{min(len(filtered_jobs), self.config.max_applications)}] Processing: {job.title} at {job.company}")
            
            # Check if we should stop due to low success rate
            if self._should_stop_early():
                logger.warning("Stopping campaign due to low success rate")
                break
            
            # Apply with retry
            result = await self._apply_with_retry(job)
            self.results.append(result)
            
            # Update platform count
            self.platform_counts[job.platform.value] = self.platform_counts.get(job.platform.value, 0) + 1
            
            # Apply iteration learnings if failed
            if not result.success and self.iterator:
                analysis = self.iterator.analyze_failure(result.application_id if hasattr(result, 'application_id') else "unknown")
                if analysis:
                    logger.info(f"Failure analysis: {analysis.suggested_fix}")
            
            # Log progress
            self._log_progress(i + 1)
            
            # Rate limiting
            if i < len(filtered_jobs) - 1:  # Don't delay after last
                delay = random.randint(*self.config.delay_between_applications)
                logger.info(f"Waiting {delay}s before next application...")
                await asyncio.sleep(delay)
        
        end_time = datetime.now()
        
        # Build result
        result = CampaignResult(
            campaign_name=self.config.name,
            start_time=start_time,
            end_time=end_time,
            total_jobs=len(filtered_jobs),
            attempted=len(self.results),
            successful=sum(1 for r in self.results if r.success),
            failed=sum(1 for r in self.results if not r.success and r.status.value == 'error'),
            skipped=len(filtered_jobs) - len(self.results),
            results=self.results,
            platform_stats=self._calculate_platform_stats()
        )
        
        # Save results
        if self.config.generate_report:
            self._save_results(result)
        
        # Print summary
        self._print_summary(result)
        
        return result
    
    async def _search_all_platforms(self) -> List[JobPosting]:
        """Search for jobs across all configured platforms."""
        all_jobs = []
        
        # Try to load from job file first (if specified in config)
        job_file = getattr(self.config, 'job_file', None)
        if job_file and Path(job_file).exists():
            logger.info(f"Loading jobs from file: {job_file}")
            try:
                import json
                data = json.loads(Path(job_file).read_text())
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
                logger.info(f"Loaded {len(all_jobs)} jobs from file")
                return all_jobs
            except Exception as e:
                logger.error(f"Failed to load job file: {e}")
        
        # Fall back to API search
        for platform_name in self.config.platforms:
            try:
                logger.info(f"Searching {platform_name}...")
                
                # Get adapter for platform
                from adapters import get_adapter
                adapter = get_adapter(platform_name, self.browser)
                
                # Search
                jobs = await adapter.search_jobs(self.config.search_criteria)
                
                logger.info(f"Found {len(jobs)} jobs on {platform_name}")
                all_jobs.extend(jobs)
                
                # Delay between platforms
                if platform_name != self.config.platforms[-1]:
                    await asyncio.sleep(self.config.delay_between_platforms)
                    
            except Exception as e:
                logger.error(f"Failed to search {platform_name}: {e}")
                continue
        
        logger.info(f"Total jobs found: {len(all_jobs)}")
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
            platform_count = self.platform_counts.get(job.platform.value, 0)
            if self.config.max_per_platform and platform_count >= self.config.max_per_platform:
                continue
            
            # Calculate match score
            score = self._calculate_match_score(job)
            if score < self.config.min_match_score:
                continue
            
            filtered.append(job)
        
        # Sort by match score (descending)
        filtered.sort(key=lambda j: self._calculate_match_score(j), reverse=True)
        
        logger.info(f"Filtered to {len(filtered)} jobs")
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
                # Use working legacy adapters for now
                # Unified adapters will be swapped in once fully tested
                adapter = self._get_working_adapter(job)
                
                result = await adapter.apply_to_job(
                    job=job,
                    resume=self.config.resume,
                    profile=self.config.applicant_profile,
                    auto_submit=self.config.auto_submit
                )
                
                if result.success or result.status.value != 'error':
                    return result
                
                # Failed, but not an error - don't retry
                if attempt == 0:
                    return result
                    
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {e}")
                
                if attempt < self.config.retry_attempts - 1:
                    logger.info(f"Waiting {self.config.retry_delay}s before retry...")
                    await asyncio.sleep(self.config.retry_delay)
        
        from adapters.base import ApplicationStatus
        return ApplicationResult(
            status=ApplicationStatus.ERROR,
            message=f"Failed after {self.config.retry_attempts} attempts"
        )
    
    def _get_working_adapter(self, job: JobPosting):
        """
        Get the appropriate working adapter for a job.
        
        Uses handlers with actual browser automation for form filling.
        Detects platform from URL if platform type is generic.
        """
        from adapters.base import PlatformType
        from adapters import get_external_platform_type
        
        platform = job.platform
        url = job.url.lower()
        
        # Detect platform from URL for generic platforms
        if platform in [PlatformType.EXTERNAL, PlatformType.COMPANY_WEBSITE]:
            detected = get_external_platform_type(url)
            logger.info(f"Detected platform from URL: {detected}")
        else:
            detected = platform.value if hasattr(platform, 'value') else str(platform)
        
        # Use direct_apply for Greenhouse, Lever, Ashby (has browser automation)
        if detected == 'greenhouse' or 'greenhouse' in url:
            from adapters.direct_apply import DirectApplyHandler
            handler = DirectApplyHandler(self.browser)
            handler.platform_type = 'greenhouse'
            return handler
        
        elif detected == 'lever' or 'lever.co' in url:
            from adapters.direct_apply import DirectApplyHandler
            handler = DirectApplyHandler(self.browser)
            handler.platform_type = 'lever'
            return handler
        
        elif detected == 'ashby' or 'ashby' in url:
            from adapters.direct_apply import DirectApplyHandler
            handler = DirectApplyHandler(self.browser)
            handler.platform_type = 'ashby'
            return handler
        
        # Use complex_forms for Workday, Taleo, etc.
        elif detected == 'workday' or 'myworkday' in url or 'workday.com' in url:
            from adapters.complex_forms import ComplexFormHandler
            return ComplexFormHandler(self.browser)
        
        elif detected == 'icims' or 'icims' in url:
            from adapters.complex_forms import ComplexFormHandler
            return ComplexFormHandler(self.browser)
        
        elif detected == 'taleo' or 'taleo' in url:
            from adapters.complex_forms import ComplexFormHandler
            return ComplexFormHandler(self.browser)
        
        elif platform == PlatformType.LINKEDIN or 'linkedin' in url:
            from adapters.linkedin import LinkedInAdapter
            return LinkedInAdapter(self.browser)
        
        elif platform == PlatformType.INDEED or 'indeed' in url:
            from adapters.indeed import IndeedAdapter
            return IndeedAdapter(self.browser)
        
        else:
            # Fallback to router which detects from URL
            from adapters.ats_router import ATSRouter
            return ATSRouter(self.browser)
    
    def _should_stop_early(self) -> bool:
        """Check if campaign should stop due to low success rate."""
        if not self.config.stop_on_low_success_rate:
            return False
        
        if len(self.results) < 10:  # Need minimum sample size
            return False
        
        recent = self.results[-10:]
        success_rate = sum(1 for r in recent if r.success) / len(recent)
        
        return success_rate < self.config.min_success_rate
    
    def _log_progress(self, current: int):
        """Log campaign progress."""
        successful = sum(1 for r in self.results if r.success)
        rate = successful / len(self.results) * 100 if self.results else 0
        
        logger.info(f"Progress: {current} processed, {successful} successful ({rate:.1f}%)")
    
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
        
        # Calculate rates
        for platform, data in stats.items():
            data['success_rate'] = data['successful'] / data['attempted'] if data['attempted'] > 0 else 0
        
        return stats
    
    def _save_results(self, result: CampaignResult):
        """Save campaign results to file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # JSON results
        json_path = self.config.output_dir / f"{self.config.name.replace(' ', '_')}_{timestamp}.json"
        import json
        json_path.write_text(json.dumps(result.to_dict(), indent=2))
        
        # Text summary
        summary_path = self.config.output_dir / f"{self.config.name.replace(' ', '_')}_{timestamp}.txt"
        summary_path.write_text(self._generate_text_report(result))
        
        logger.info(f"Results saved to {self.config.output_dir}")
    
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
        print(f"CAMPAIGN COMPLETE: {result.campaign_name}")
        print("="*70)
        print(f"Duration: {result.duration_seconds / 60:.1f} minutes")
        print(f"Success Rate: {result.success_rate * 100:.1f}%")
        print(f"Successful: {result.successful}/{result.attempted}")
        print("="*70 + "\n")
    
    @staticmethod
    def load_config(path: Path) -> CampaignConfig:
        """Load campaign configuration from YAML file."""
        data = yaml.safe_load(path.read_text())
        
        # Build SearchConfig
        search_data = data.get('search', {})
        search_criteria = SearchConfig(
            roles=search_data.get('roles', []),
            locations=search_data.get('locations', ['Remote']),
            required_keywords=search_data.get('required_keywords', []),
            exclude_keywords=search_data.get('exclude_keywords', []),
            easy_apply_only=search_data.get('easy_apply_only', False),
        )
        
        # Build UserProfile
        applicant_data = data.get('applicant', {})
        profile = UserProfile(
            first_name=applicant_data['first_name'],
            last_name=applicant_data['last_name'],
            email=applicant_data['email'],
            phone=applicant_data.get('phone', ''),
            linkedin_url=applicant_data.get('linkedin_url'),
            years_experience=applicant_data.get('years_experience'),
            custom_answers=applicant_data.get('custom_answers', {})
        )
        
        # Build Resume
        resume_data = data.get('resume', {})
        resume = Resume(
            file_path=resume_data['path'],
            raw_text="",  # Will be loaded from file
            parsed_data={}
        )
        
        # Build CampaignConfig
        limits = data.get('limits', {})
        settings = data.get('settings', {})
        output = data.get('output', {})
        
        return CampaignConfig(
            name=data['name'],
            applicant_profile=profile,
            resume=resume,
            search_criteria=search_criteria,
            platforms=data.get('platforms', ['greenhouse', 'lever']),
            max_applications=limits.get('max_applications', 100),
            max_per_platform=limits.get('max_per_platform'),
            auto_submit=settings.get('auto_submit', False),
            delay_between_applications=settings.get('delay_between_applications', [30, 60]),
            retry_attempts=settings.get('retry_attempts', 3),
            job_file=data.get('job_file'),
            output_dir=Path(output.get('dir', './campaign_output')),
            save_screenshots=output.get('save_screenshots', True),
            generate_report=output.get('generate_report', True)
        )


# Example campaign YAML that replaces entire Python files:
EXAMPLE_CAMPAIGN_YAML = """
name: "Software Engineer - Remote"

applicant:
  first_name: "Your"
  last_name: "Name"
  email: "your.email@example.com"
  phone: "555-123-4567"
  linkedin_url: "https://linkedin.com/in/yourprofile"
  years_experience: 5
  custom_answers:
    salary_expectations: "$100,000 - $130,000"
    notice_period: "2 weeks"
    willing_to_relocate: "No"

resume:
  path: "/path/to/your/resume.pdf"

search:
  roles:
    - "Software Engineer"
    - "Backend Engineer"
    - "Full Stack Developer"
  locations:
    - "Remote"
    - "San Francisco"
    - "New York"
  required_keywords:
    - "Python"
    - "AWS"
  exclude_keywords:
    - "Senior Staff"
    - "Principal"

platforms:
  - greenhouse
  - lever
  - ashby
  - linkedin

limits:
  max_applications: 100
  max_per_platform: 40

settings:
  auto_submit: false
  delay_between_applications: [30, 60]
  retry_attempts: 3
  stop_on_low_success_rate: true
  min_success_rate: 0.3
"""
