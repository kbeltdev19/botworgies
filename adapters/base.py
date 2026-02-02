"""
Base adapter interface for job platforms.
All platform-specific adapters inherit from this.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class PlatformType(str, Enum):
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    GREENHOUSE = "greenhouse"
    WORKDAY = "workday"
    LEVER = "lever"
    ASHBY = "ashby"
    CLEARANCEJOBS = "clearancejobs"
    USAJOBS = "usajobs"
    ICIMS = "icims"
    TALEO = "taleo"
    SMARTRECRUITERS = "smartrecruiters"
    COMPANY_WEBSITE = "company"  # Generic company career pages
    EXTERNAL = "external"  # External/unknown ATS


class ApplicationStatus(str, Enum):
    PENDING = "pending"
    READY_TO_SUBMIT = "ready_to_submit"
    PENDING_REVIEW = "pending_review"
    SUBMITTED = "submitted"
    EXTERNAL_APPLICATION = "external_application"
    FAILED = "failed"
    ERROR = "error"


@dataclass
class JobPosting:
    """Represents a job posting from any platform."""
    id: str
    platform: PlatformType
    title: str
    company: str
    location: str
    url: str
    description: Optional[str] = None
    salary_range: Optional[str] = None
    posted_date: Optional[datetime] = None
    easy_apply: bool = False
    requirements: Optional[str] = None  # Can be string or list
    remote: bool = False
    job_type: str = "full-time"  # full-time, part-time, contract
    experience_level: str = "mid"  # entry, mid, senior, lead
    external_apply_url: Optional[str] = None  # URL for external application
    clearance_required: Optional[str] = None  # Security clearance level
    source_platform: Optional[str] = None  # Original source if redirected


@dataclass
class ApplicationResult:
    """Result of an application attempt."""
    status: ApplicationStatus
    message: str = ""
    confirmation_id: Optional[str] = None
    screenshot_path: Optional[str] = None
    external_url: Optional[str] = None
    error: Optional[str] = None
    submitted_at: Optional[datetime] = None


@dataclass
class SearchConfig:
    """Configuration for job search."""
    roles: List[str]  # Job titles to search for
    locations: List[str]  # Locations (including "Remote")
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    exclude_keywords: List[str] = field(default_factory=list)
    required_keywords: List[str] = field(default_factory=list)
    posted_within_days: int = 7
    experience_levels: List[str] = field(default_factory=lambda: ["mid", "senior"])
    company_sizes: List[str] = field(default_factory=list)
    industries: List[str] = field(default_factory=list)
    easy_apply_only: bool = False
    country: str = "US"  # Country filter: US, CA, GB, DE, ALL
    careers_url: Optional[str] = None  # Company careers page URL for direct scraping


@dataclass 
class UserProfile:
    """User's profile information for applications."""
    first_name: str
    last_name: str
    email: str
    phone: str
    linkedin_url: Optional[str] = None
    location: str = ""
    website: Optional[str] = None
    
    # Pre-filled answers for common questions
    work_authorization: str = "Yes"  # Are you authorized to work?
    sponsorship_required: str = "No"  # Do you require sponsorship?
    years_experience: Optional[int] = None
    
    # Custom Q&A
    custom_answers: dict = field(default_factory=dict)


@dataclass
class Resume:
    """Resume data for applications."""
    file_path: str
    raw_text: str
    parsed_data: dict
    tailored_version: Optional[dict] = None


class JobPlatformAdapter(ABC):
    """
    Abstract base class for job platform adapters.
    Each platform (LinkedIn, Indeed, etc.) implements this interface.
    """

    platform: PlatformType

    def __init__(self, browser_manager, session_cookie: Optional[str] = None):
        self.browser_manager = browser_manager
        self.session_cookie = session_cookie
        self._session = None
    
    @abstractmethod
    async def search_jobs(self, criteria: SearchConfig) -> List[JobPosting]:
        """Search for jobs matching the criteria."""
        pass
    
    @abstractmethod
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get full details for a specific job posting."""
        pass
    
    @abstractmethod
    async def apply_to_job(
        self, 
        job: JobPosting, 
        resume: Resume,
        profile: UserProfile,
        cover_letter: Optional[str] = None,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """Apply to a specific job."""
        pass
    
    async def get_session(self):
        """Get or create a browser session for this platform."""
        if not self._session:
            self._session = await self.browser_manager.create_stealth_session(
                self.platform.value
            )
        return self._session

    async def close(self):
        """Close the platform session."""
        if self._session:
            await self.browser_manager.close_session(self._session.session_id)
            self._session = None

    def _log(self, message: str, level: str = "info"):
        """Log a message with platform prefix."""
        prefix = self.platform.value.upper() if hasattr(self, 'platform') else "ADAPTER"
        print(f"[{prefix}] {message}")
    
    def _score_job_fit(self, job: JobPosting, criteria: SearchConfig) -> float:
        """
        Score how well a job matches search criteria.
        Returns 0-1 score.
        """
        score = 0.5  # Base score
        
        # Title match
        title_lower = job.title.lower()
        for role in criteria.roles:
            if role.lower() in title_lower:
                score += 0.2
                break
        
        # Location match
        loc_lower = job.location.lower()
        for location in criteria.locations:
            if location.lower() in loc_lower or location.lower() == "remote" and job.remote:
                score += 0.1
                break
        
        # Required keywords in description
        if job.description:
            desc_lower = job.description.lower()
            matched_required = sum(1 for kw in criteria.required_keywords if kw.lower() in desc_lower)
            if criteria.required_keywords:
                score += 0.2 * (matched_required / len(criteria.required_keywords))
        
        # Exclude keywords
        if job.description:
            for kw in criteria.exclude_keywords:
                if kw.lower() in job.description.lower():
                    score -= 0.3
        
        # Easy apply bonus
        if job.easy_apply:
            score += 0.1
        
        return max(0, min(1, score))
