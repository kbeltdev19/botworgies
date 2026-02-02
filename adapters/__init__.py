"""
Job Platform Adapters
Unified interface for applying to jobs across different platforms.
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


def get_adapter(platform: str, browser_manager) -> JobPlatformAdapter:
    """
    Factory function to get the appropriate adapter for a platform.
    
    Args:
        platform: Platform identifier (linkedin, indeed, greenhouse, workday, lever)
        browser_manager: StealthBrowserManager instance
    
    Returns:
        Appropriate platform adapter
    """
    adapters = {
        "linkedin": LinkedInAdapter,
        "indeed": IndeedAdapter,
        "greenhouse": GreenhouseAdapter,
        "workday": WorkdayAdapter,
        "lever": LeverAdapter,
    }
    
    platform_lower = platform.lower()
    
    # Also detect from URL
    if "linkedin.com" in platform_lower:
        platform_lower = "linkedin"
    elif "indeed.com" in platform_lower:
        platform_lower = "indeed"
    elif "greenhouse.io" in platform_lower or "boards.greenhouse" in platform_lower:
        platform_lower = "greenhouse"
    elif "myworkdayjobs.com" in platform_lower or "workday" in platform_lower:
        platform_lower = "workday"
    elif "lever.co" in platform_lower:
        platform_lower = "lever"
    
    adapter_class = adapters.get(platform_lower)
    
    if not adapter_class:
        raise ValueError(f"Unsupported platform: {platform}. Supported: {list(adapters.keys())}")
    
    return adapter_class(browser_manager)


def detect_platform_from_url(url: str) -> str:
    """
    Detect which platform a job URL belongs to.
    
    Returns platform identifier or 'unknown'.
    """
    url_lower = url.lower()
    
    if "linkedin.com" in url_lower:
        return "linkedin"
    elif "indeed.com" in url_lower:
        return "indeed"
    elif "greenhouse.io" in url_lower or "boards.greenhouse" in url_lower:
        return "greenhouse"
    elif "myworkdayjobs.com" in url_lower:
        return "workday"
    elif "lever.co" in url_lower:
        return "lever"
    
    return "unknown"


__all__ = [
    "JobPlatformAdapter",
    "PlatformType",
    "JobPosting",
    "ApplicationResult",
    "ApplicationStatus",
    "SearchConfig",
    "UserProfile",
    "Resume",
    "LinkedInAdapter",
    "IndeedAdapter",
    "GreenhouseAdapter",
    "WorkdayAdapter",
    "LeverAdapter",
    "get_adapter",
    "detect_platform_from_url",
]
