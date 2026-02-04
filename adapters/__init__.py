"""
Job Platform Adapters
Unified interface for applying to jobs across different platforms.
Supports: LinkedIn, Indeed, Greenhouse, Workday, Lever, ClearanceJobs, and external ATS.

New adapters added:
- Ashby (API-based)
- SmartRecruiters (API-based)
- Dice (Browser-based)
- RemoteOK (API-based)
- Remotive (API-based)
- USAJobs (API-based)
- WeWorkRemotely (Scraping)
- HackerNews (API-based)
- JobSpy (Multi-platform scraper - requires Python 3.10+)
  * LinkedIn, Indeed, ZipRecruiter, Glassdoor, Google Jobs
"""

from .base import (
    JobPlatformAdapter,
    PlatformType,
    JobPosting,
    ApplicationResult,
    ApplicationStatus,
    SearchConfig,
    UserProfile,
    Resume
)
from .linkedin import LinkedInAdapter
from .indeed import IndeedAdapter
from .greenhouse import GreenhouseAdapter
from .workday import WorkdayAdapter
from .lever import LeverAdapter
from .company import CompanyWebsiteAdapter
from .external import ExternalApplicationAdapter
from .clearancejobs import ClearanceJobsAdapter
from .rss_adapter import RSSAdapter
from .ashby import AshbyAdapter
from .smartrecruiters import SmartRecruitersAdapter
from .dice import DiceAdapter
from .remoteok import RemoteOKAdapter
from .remotive import RemotiveAdapter
from .usajobs import USAJobsAdapter
from .weworkremotely import WeWorkRemotelyAdapter

# JobSpy integration (requires Python 3.10+)
try:
    from .jobspy_scraper import JobSpyScraper, JobSpyConfig, JobSpySearchBuilder
    from .jobspy_adapter import JobSpyAdapter
    JOBSY_AVAILABLE = True
except ImportError:
    JOBSY_AVAILABLE = False
    JobSpyScraper = None
    JobSpyConfig = None
    JobSpySearchBuilder = None
    JobSpyAdapter = None


# Platform URL patterns for detection
PLATFORM_PATTERNS = {
    "linkedin": ["linkedin.com/jobs", "linkedin.com/in/"],
    "indeed": ["indeed.com"],
    "greenhouse": ["greenhouse.io", "boards.greenhouse"],
    "workday": ["myworkdayjobs.com", "workday.com"],
    "lever": ["lever.co", "jobs.lever"],
    "clearancejobs": ["clearancejobs.com"],
    "usajobs": ["usajobs.gov"],
    "icims": ["icims.com", "careers-"],
    "taleo": ["taleo.net", "taleo.com"],
    "smartrecruiters": ["smartrecruiters.com"],
    "jobvite": ["jobvite.com"],
    "ashbyhq": ["ashbyhq.com", "jobs.ashby"],
    "bamboohr": ["bamboohr.com"],
    "brassring": ["brassring.com"],
    "successfactors": ["successfactors.com", "successfactors.eu"],
    "dice": ["dice.com"],
    "remoteok": ["remoteok.com"],
    "remotive": ["remotive.com"],
    "weworkremotely": ["weworkremotely.com"],
    "stackoverflow": ["stackoverflow.com/jobs"],
    "authenticjobs": ["authenticjobs.com"],
    "workingnomads": ["workingnomads.co"],
    "ziprecruiter": ["ziprecruiter.com"],
    "monster": ["monster.com"],
    "careerbuilder": ["careerbuilder.com"],
    "simplyhired": ["simplyhired.com"],
    "craigslist": ["craigslist.org"],
    "news.ycombinator": ["news.ycombinator.com"],
    "ycombinator": ["ycombinator.com"],
    "wellfound": ["wellfound.com", "angel.co"],
    "angellist": ["angel.co"],
}

# Adapters registry
ADAPTERS = {
    "linkedin": LinkedInAdapter,
    "indeed": IndeedAdapter,
    "greenhouse": GreenhouseAdapter,
    "workday": WorkdayAdapter,
    "lever": LeverAdapter,
    "clearancejobs": ClearanceJobsAdapter,
    "usajobs": USAJobsAdapter,
    "smartrecruiters": SmartRecruitersAdapter,
    "ashby": AshbyAdapter,
    "ashbyhq": AshbyAdapter,
    "dice": DiceAdapter,
    "remoteok": RemoteOKAdapter,
    "remotive": RemotiveAdapter,
    "weworkremotely": WeWorkRemotelyAdapter,
    "company": CompanyWebsiteAdapter,
    "external": ExternalApplicationAdapter,
    "rss": RSSAdapter,
}


def get_adapter(platform: str, browser_manager, session_cookie: str = None, **kwargs) -> JobPlatformAdapter:
    """
    Factory function to get the appropriate adapter for a platform.

    Args:
        platform: Platform identifier or URL
        browser_manager: StealthBrowserManager instance
        session_cookie: Optional session cookie for authenticated platforms
        **kwargs: Additional arguments to pass to adapter constructor

    Returns:
        Appropriate platform adapter
    """
    platform_lower = platform.lower()

    # Detect platform from URL if full URL provided
    if "://" in platform_lower or "." in platform_lower:
        detected = detect_platform_from_url(platform)
        if detected != "unknown":
            platform_lower = detected

    adapter_class = ADAPTERS.get(platform_lower)

    if not adapter_class:
        # Try to use ClearanceJobs adapter for external sites since it has
        # good external site handling
        if platform_lower in ["icims", "taleo", "jobvite", "external"]:
            adapter_class = ClearanceJobsAdapter
        else:
            raise ValueError(f"Unsupported platform: {platform}. Supported: {list(ADAPTERS.keys())}")

    # All adapters can accept session_cookie now
    return adapter_class(browser_manager, session_cookie=session_cookie, **kwargs)


def detect_platform_from_url(url: str) -> str:
    """
    Detect which platform a job URL belongs to.

    Args:
        url: Job posting URL

    Returns:
        Platform identifier or 'unknown'
    """
    url_lower = url.lower()

    for platform, patterns in PLATFORM_PATTERNS.items():
        if any(pattern in url_lower for pattern in patterns):
            return platform

    # Additional heuristics for common ATS patterns
    if "/careers/" in url_lower or "/jobs/" in url_lower:
        # Could be a company career page
        return "company"

    return "unknown"


def get_external_platform_type(url: str) -> str:
    """
    Get the external ATS type from a URL for routing to appropriate handler.

    Args:
        url: External application URL

    Returns:
        ATS type identifier
    """
    url_lower = url.lower()

    ats_patterns = {
        "workday": ["myworkday", "workday.com", "wd5.myworkdayjobs"],
        "icims": ["icims.com"],
        "taleo": ["taleo.net", "taleo.com"],
        "greenhouse": ["greenhouse.io", "boards.greenhouse"],
        "lever": ["lever.co", "jobs.lever"],
        "smartrecruiters": ["smartrecruiters.com"],
        "jobvite": ["jobvite.com"],
        "successfactors": ["successfactors.com", "successfactors.eu"],
        "bamboohr": ["bamboohr.com"],
        "ashbyhq": ["ashbyhq.com", "jobs.ashby"],
        "brassring": ["brassring.com"],
        "ashby": ["jobs.ashbyhq.com"],
        "dice": ["dice.com"],
        "usajobs": ["usajobs.gov"],
        "clearancejobs": ["clearancejobs.com"],
    }

    for ats, patterns in ats_patterns.items():
        if any(pattern in url_lower for pattern in patterns):
            return ats

    return "generic"


def is_external_application(url: str, source_platform: str) -> bool:
    """
    Check if a URL leads to an external application site.

    Args:
        url: Target URL
        source_platform: Original platform where job was found

    Returns:
        True if URL is external to source platform
    """
    detected = detect_platform_from_url(url)
    return detected != "unknown" and detected != source_platform


def get_all_adapters_for_search(browser_manager) -> list:
    """
    Get all available adapters for job searching.
    
    Returns:
        List of initialized adapters ready for searching
    """
    adapters = []
    
    # API-based adapters (no browser needed for search)
    api_adapters = [
        GreenhouseAdapter(),
        LeverAdapter(),
        AshbyAdapter(),
        SmartRecruitersAdapter(),
        RemoteOKAdapter(),
        RemotiveAdapter(),
        WeWorkRemotelyAdapter(),
        USAJobsAdapter(),
        RSSAdapter(),
    ]
    adapters.extend(api_adapters)
    
    # Browser-based adapters
    if browser_manager:
        browser_adapters = [
            LinkedInAdapter(browser_manager),
            IndeedAdapter(browser_manager),
            DiceAdapter(browser_manager),
            ClearanceJobsAdapter(browser_manager),
        ]
        adapters.extend(browser_adapters)
    
    return adapters


__all__ = [
    # Base classes
    "JobPlatformAdapter",
    "PlatformType",
    "JobPosting",
    "ApplicationResult",
    "ApplicationStatus",
    "SearchConfig",
    "UserProfile",
    "Resume",
    # Adapters
    "LinkedInAdapter",
    "IndeedAdapter",
    "GreenhouseAdapter",
    "WorkdayAdapter",
    "LeverAdapter",
    "ClearanceJobsAdapter",
    "CompanyWebsiteAdapter",
    "USAJobsAdapter",
    "SmartRecruitersAdapter",
    "AshbyAdapter",
    "DiceAdapter",
    "RemoteOKAdapter",
    "RemotiveAdapter",
    "WeWorkRemotelyAdapter",
    "RSSAdapter",
    # JobSpy (if available)
    "JobSpyScraper",
    "JobSpyConfig",
    "JobSpySearchBuilder",
    "JobSpyAdapter",
    "JOBSY_AVAILABLE",
    # Factory functions
    "get_adapter",
    "detect_platform_from_url",
    "get_external_platform_type",
    "is_external_application",
    "get_all_adapters_for_search",
]
