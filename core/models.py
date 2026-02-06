#!/usr/bin/env python3
"""
Unified Data Models for Job Applier

All shared data models are defined here to ensure consistency across the codebase.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


# ============== Enums ==============

class PlatformType(str, Enum):
    """Supported job platforms."""
    # Major platforms
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    DICE = "dice"
    
    # ATS Systems
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    WORKDAY = "workday"
    ASHBY = "ashby"
    SMARTRECRUITERS = "smartrecruiters"
    ICIMS = "icims"
    TALEO = "taleo"
    SUCCESSFACTORS = "successfactors"
    ADP = "adp"
    
    # Job boards
    REMOTEOK = "remoteok"
    REMOTIVE = "remotive"
    WEWORKREMOTELY = "weworkremotely"
    HACKERNEWS = "hackernews"
    ANGELLIST = "angellist"
    ZIPRECRUITER = "ziprecruiter"
    
    # Government/Clearance
    CLEARANCEJOBS = "clearancejobs"
    USAJOBS = "usajobs"
    
    # Generic
    COMPANY_WEBSITE = "company"
    EXTERNAL = "external"
    RSS = "rss"
    UNKNOWN = "unknown"


class ApplicationStatus(str, Enum):
    """Application status values."""
    PENDING = "pending"
    READY_TO_SUBMIT = "ready_to_submit"
    PENDING_REVIEW = "pending_review"
    SUBMITTED = "submitted"
    EXTERNAL_APPLICATION = "external_application"
    FAILED = "failed"
    ERROR = "error"


class ExperienceLevel(str, Enum):
    """Experience level categories."""
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    EXECUTIVE = "executive"


class JobType(str, Enum):
    """Job type categories."""
    FULL_TIME = "full-time"
    PART_TIME = "part-time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    TEMPORARY = "temporary"


# ============== Data Models ==============

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
    requirements: Optional[str] = None
    remote: bool = False
    job_type: JobType = JobType.FULL_TIME
    experience_level: ExperienceLevel = ExperienceLevel.MID
    external_apply_url: Optional[str] = None
    clearance_required: Optional[str] = None
    source_platform: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "platform": self.platform.value,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "url": self.url,
            "description": self.description,
            "salary_range": self.salary_range,
            "posted_date": self.posted_date.isoformat() if self.posted_date else None,
            "easy_apply": self.easy_apply,
            "remote": self.remote,
            "job_type": self.job_type.value,
            "experience_level": self.experience_level.value,
            "clearance_required": self.clearance_required,
        }


@dataclass
class ApplicationResult:
    """Result of a job application attempt."""
    status: ApplicationStatus
    message: str = ""
    confirmation_id: Optional[str] = None
    screenshot_path: Optional[str] = None
    external_url: Optional[str] = None
    error: Optional[str] = None
    submitted_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success(self) -> bool:
        """Check if application was successful."""
        return self.status == ApplicationStatus.SUBMITTED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "status": self.status.value,
            "message": self.message,
            "confirmation_id": self.confirmation_id,
            "error": self.error,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
        }


@dataclass
class UserProfile:
    """User's profile information for applications."""
    first_name: str
    last_name: str
    email: str
    phone: str
    location: str = ""
    linkedin_url: Optional[str] = None
    website: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    
    # Work authorization
    work_authorization: str = "Yes"
    sponsorship_required: str = "No"
    years_experience: Optional[int] = None
    
    # Resume/CV
    resume_path: Optional[str] = None
    resume_text: Optional[str] = None
    
    # Custom Q&A
    custom_answers: Dict[str, str] = field(default_factory=dict)
    
    @property
    def full_name(self) -> str:
        """Get full name."""
        return f"{self.first_name} {self.last_name}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone,
            "location": self.location,
            "linkedin_url": self.linkedin_url,
            "website": self.website,
            "work_authorization": self.work_authorization,
            "sponsorship_required": self.sponsorship_required,
            "years_experience": self.years_experience,
        }


@dataclass
class Resume:
    """Resume data for applications."""
    file_path: str
    raw_text: str
    parsed_data: Dict[str, Any] = field(default_factory=dict)
    tailored_version: Optional[Dict[str, Any]] = None
    
    def get_tailored_for_job(self, job: JobPosting) -> Dict[str, Any]:
        """Get resume tailored for specific job."""
        if self.tailored_version:
            return self.tailored_version
        return self.parsed_data


@dataclass
class SearchConfig:
    """Configuration for job search."""
    roles: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=lambda: ["Remote"])
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    exclude_keywords: List[str] = field(default_factory=list)
    required_keywords: List[str] = field(default_factory=list)
    exclude_companies: List[str] = field(default_factory=list)
    posted_within_days: int = 7
    experience_levels: List[ExperienceLevel] = field(default_factory=lambda: [ExperienceLevel.MID, ExperienceLevel.SENIOR])
    company_sizes: List[str] = field(default_factory=list)
    industries: List[str] = field(default_factory=list)
    easy_apply_only: bool = False
    country: str = "US"
    careers_url: Optional[str] = None
    max_results: int = 100


@dataclass
class CampaignConfig:
    """Configuration for a job application campaign."""
    name: str
    profile: UserProfile
    search_config: SearchConfig
    max_applications: int = 10
    daily_limit: int = 10
    auto_submit: bool = False
    follow_up_enabled: bool = False
    
    # Filters
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    required_remote: bool = False
    exclude_contract: bool = False


# ============== Abstract Base Classes ==============

class JobPlatformAdapter(ABC):
    """
    Unified abstract base class for job platform adapters.
    
    This replaces both the old adapters/base.py JobPlatformAdapter
    and ats_automation/handlers/base_handler.py BaseATSHandler.
    """
    
    platform: PlatformType = PlatformType.UNKNOWN
    
    def __init__(
        self,
        user_profile: UserProfile,
        browser_manager=None,
        ai_client=None
    ):
        self.profile = user_profile
        self.browser = browser_manager
        self.ai_client = ai_client
        self._session = None
    
    @abstractmethod
    async def can_handle(self, url: str) -> bool:
        """Check if this adapter can handle the given URL."""
        pass
    
    @abstractmethod
    async def search_jobs(self, config: SearchConfig) -> List[JobPosting]:
        """Search for jobs matching the criteria."""
        pass
    
    @abstractmethod
    async def get_job_details(self, job_url: str) -> JobPosting:
        """Get full details for a specific job posting."""
        pass
    
    @abstractmethod
    async def apply(self, job: JobPosting, resume: Resume) -> ApplicationResult:
        """Apply to a specific job."""
        pass
    
    async def close(self):
        """Close the adapter and cleanup resources."""
        if self._session:
            if hasattr(self._session, 'close'):
                await self._session.close()
            self._session = None
    
    def _log(self, message: str, level: str = "info"):
        """Log a message with platform prefix."""
        prefix = self.platform.value.upper()
        print(f"[{prefix}] {message}")


# ============== Utility Functions ==============

def score_job_fit(job: JobPosting, config: SearchConfig) -> float:
    """
    Score how well a job matches search criteria.
    Returns 0-1 score.
    """
    score = 0.5  # Base score
    
    # Title match
    title_lower = job.title.lower()
    for role in config.roles:
        if role.lower() in title_lower:
            score += 0.2
            break
    
    # Location match
    loc_lower = job.location.lower()
    for location in config.locations:
        if location.lower() in loc_lower or (location.lower() == "remote" and job.remote):
            score += 0.1
            break
    
    # Required keywords in description
    if job.description:
        desc_lower = job.description.lower()
        matched_required = sum(1 for kw in config.required_keywords if kw.lower() in desc_lower)
        if config.required_keywords:
            score += 0.2 * (matched_required / len(config.required_keywords))
    
    # Exclude keywords
    if job.description:
        for kw in config.exclude_keywords:
            if kw.lower() in job.description.lower():
                score -= 0.3
    
    # Easy apply bonus
    if job.easy_apply:
        score += 0.1
    
    return max(0, min(1, score))


def detect_platform_from_url(url: str) -> PlatformType:
    """Detect platform type from URL."""
    url_lower = url.lower()
    
    patterns = {
        PlatformType.GREENHOUSE: ["greenhouse.io", "grnh.se"],
        PlatformType.LEVER: ["lever.co", "jobs.lever"],
        PlatformType.WORKDAY: ["workday", "myworkdayjobs"],
        PlatformType.ASHBY: ["ashbyhq"],
        PlatformType.SMARTRECRUITERS: ["smartrecruiters"],
        PlatformType.ICIMS: ["icims"],
        PlatformType.LINKEDIN: ["linkedin.com/jobs"],
        PlatformType.INDEED: ["indeed.com", "indeed.jobs"],
        PlatformType.DICE: ["dice.com"],
        PlatformType.ZIPRECRUITER: ["ziprecruiter.com"],
        PlatformType.CLEARANCEJOBS: ["clearancejobs.com"],
        PlatformType.USAJOBS: ["usajobs.gov"],
    }
    
    for platform, patterns_list in patterns.items():
        if any(p in url_lower for p in patterns_list):
            return platform
    
    return PlatformType.UNKNOWN
