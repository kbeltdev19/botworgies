"""
Job Platform Adapters - Unified Interface

This module provides adapters for different job platforms.

For new code, use the UnifiedPlatformAdapter which handles all platforms
using AI-powered browser automation via Stagehand.

Legacy platform-specific adapters are still available for backwards compatibility.
"""

# Re-export from core (unified models)
from core.models import (
    JobPlatformAdapter,
    PlatformType,
    JobPosting,
    ApplicationResult,
    ApplicationStatus,
    SearchConfig,
    UserProfile,
    Resume,
    score_job_fit,
    detect_platform_from_url,
)

# Unified adapter (recommended for new code)
from .unified import UnifiedPlatformAdapter, create_adapter

# Legacy platform-specific adapters (for backwards compatibility)
from .linkedin import LinkedInAdapter
from .indeed import IndeedAdapter
from .greenhouse import GreenhouseAdapter
from .workday import WorkdayAdapter
from .lever import LeverAdapter
from .company import CompanyWebsiteAdapter
from .clearancejobs import ClearanceJobsAdapter
from .rss_adapter import RSSAdapter
from .ashby import AshbyAdapter
from .smartrecruiters import SmartRecruitersAdapter
from .dice import DiceAdapter
from .remoteok import RemoteOKAdapter
from .remotive import RemotiveAdapter
from .usajobs import USAJobsAdapter
from .weworkremotely import WeWorkRemotelyAdapter
from .hn_jobs import HNJobsAdapter as HackerNewsAdapter


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
    "ashbyhq": ["ashbyhq.com", "jobs.ashby"],
    "dice": ["dice.com"],
    "remoteok": ["remoteok.com"],
    "remotive": ["remotive.com"],
    "weworkremotely": ["weworkremotely.com"],
    "stackoverflow": ["stackoverflow.com/jobs"],
    "hackernews": ["news.ycombinator.com"],
    "ziprecruiter": ["ziprecruiter.com"],
}


# Legacy adapters registry (kept for backwards compatibility)
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
    "hackernews": HackerNewsAdapter,
    "company": CompanyWebsiteAdapter,
    "rss": RSSAdapter,
}


def get_adapter(platform: str, browser_manager=None, session_cookie: str = None, **kwargs):
    """
    Factory function to get the appropriate adapter for a platform.
    
    For new code, this returns the UnifiedPlatformAdapter by default.
    Set use_unified=False to get legacy platform-specific adapters.
    
    Args:
        platform: Platform identifier or URL
        browser_manager: Browser manager instance (optional)
        session_cookie: Optional session cookie for authenticated platforms
        use_unified: If True (default), return UnifiedPlatformAdapter
        **kwargs: Additional arguments passed to adapter
        
    Returns:
        JobPlatformAdapter instance
    """
    use_unified = kwargs.pop('use_unified', True)
    
    if use_unified:
        from core import UnifiedBrowserManager, UserProfile
        
        profile = kwargs.get('user_profile') or UserProfile(
            first_name=kwargs.get('first_name', ''),
            last_name=kwargs.get('last_name', ''),
            email=kwargs.get('email', ''),
            phone=kwargs.get('phone', '')
        )
        
        return UnifiedPlatformAdapter(
            user_profile=profile,
            browser_manager=browser_manager
        )
    
    # Legacy adapter selection
    platform_lower = platform.lower()
    
    # Detect platform from URL if full URL provided
    if "://" in platform_lower or "." in platform_lower:
        detected = detect_platform_from_url(platform)
        if detected != "unknown":
            platform_lower = detected
    
    adapter_class = ADAPTERS.get(platform_lower)
    
    if not adapter_class:
        # Default to unified adapter
        return get_adapter(platform, browser_manager, session_cookie, use_unified=True, **kwargs)
    
    return adapter_class(browser_manager, session_cookie=session_cookie, **kwargs)


def get_external_platform_type(url: str) -> str:
    """Get the external ATS type from a URL."""
    return detect_platform_from_url(url)


def is_external_application(url: str, source_platform: str) -> bool:
    """Check if a URL leads to an external application site."""
    detected = detect_platform_from_url(url)
    return detected != "unknown" and detected != source_platform


__all__ = [
    # Core models (from core.models)
    "JobPlatformAdapter",
    "PlatformType",
    "JobPosting",
    "ApplicationResult",
    "ApplicationStatus",
    "SearchConfig",
    "UserProfile",
    "Resume",
    "score_job_fit",
    "detect_platform_from_url",
    
    # Unified adapter (recommended)
    "UnifiedPlatformAdapter",
    "create_adapter",
    
    # Legacy adapters
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
    "HackerNewsAdapter",
    "RSSAdapter",
    
    # Factory functions
    "get_adapter",
    "get_external_platform_type",
    "is_external_application",
]
