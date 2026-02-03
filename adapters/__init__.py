"""
Job Platform Adapters
Unified interface for applying to jobs across different platforms.
Supports: LinkedIn, Indeed, Greenhouse, Workday, Lever, ClearanceJobs, and external ATS.
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
from .clearancejobs import ClearanceJobsAdapter
from .rss_adapter import RSSAdapter


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
}

# Adapters registry
ADAPTERS = {
    "linkedin": LinkedInAdapter,
    "indeed": IndeedAdapter,
    "greenhouse": GreenhouseAdapter,
    "workday": WorkdayAdapter,
    "lever": LeverAdapter,
    "clearancejobs": ClearanceJobsAdapter,
    "company": CompanyWebsiteAdapter,
    "rss": RSSAdapter,
}


def get_adapter(platform: str, browser_manager, session_cookie: str = None) -> JobPlatformAdapter:
    """
    Factory function to get the appropriate adapter for a platform.

    Args:
        platform: Platform identifier or URL
        browser_manager: StealthBrowserManager instance
        session_cookie: Optional session cookie for authenticated platforms

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
        if platform_lower in ["icims", "taleo", "smartrecruiters", "jobvite", "external"]:
            adapter_class = ClearanceJobsAdapter
        else:
            raise ValueError(f"Unsupported platform: {platform}. Supported: {list(ADAPTERS.keys())}")

    # All adapters can accept session_cookie now
    return adapter_class(browser_manager, session_cookie=session_cookie)


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
    # Factory functions
    "get_adapter",
    "detect_platform_from_url",
    "get_external_platform_type",
    "is_external_application",
]
