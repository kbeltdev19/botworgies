"""
Data models for ATS automation system
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from enum import Enum


class ATSPlatform(Enum):
    """Supported ATS platforms"""
    WORKDAY = "workday"
    TALEO = "taleo"
    ICIMS = "icims"
    SUCCESSFACTORS = "successfactors"
    ADP = "adp"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ANGELLIST = "angellist"
    WELLFOUND = "wellfound"
    DICE = "dice"
    INDEED = "indeed"
    LINKEDIN = "linkedin"
    UNKNOWN = "unknown"


@dataclass
class UserProfile:
    """User profile for job applications"""
    first_name: str
    last_name: str
    email: str
    phone: str
    resume_path: str
    resume_text: str = ""
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    github_url: Optional[str] = None
    salary_expectation: Optional[str] = None
    years_experience: Optional[int] = None
    skills: List[str] = field(default_factory=list)
    work_history: List[Dict] = field(default_factory=list)
    education: List[Dict] = field(default_factory=list)
    custom_answers: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
            'phone': self.phone,
            'resume_path': self.resume_path,
            'resume_text': self.resume_text,
            'linkedin_url': self.linkedin_url,
            'portfolio_url': self.portfolio_url,
            'github_url': self.github_url,
            'salary_expectation': self.salary_expectation,
            'years_experience': self.years_experience,
            'skills': self.skills,
            'work_history': self.work_history,
            'education': self.education,
            'custom_answers': self.custom_answers
        }


@dataclass
class FieldMapping:
    """Mapping of form field to user data"""
    field_type: str
    selector: str
    fill_strategy: str  # 'type', 'select', 'upload', 'checkbox', 'radio', 'ai_generate'
    value: Any
    confidence: float
    required: bool = False
    question_text: str = ""
    platform_specific: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApplicationResult:
    """Result of job application attempt"""
    success: bool
    platform: ATSPlatform
    job_id: str
    job_url: str = ""
    status: str = ""  # 'submitted', 'pending_verification', 'external_redirect', 'failed', 'incomplete'
    confirmation_number: Optional[str] = None
    screenshot_path: Optional[str] = None
    error_message: Optional[str] = None
    fields_filled: int = 0
    total_fields: int = 0
    session_id: Optional[str] = None
    duration_seconds: float = 0.0
    redirect_url: Optional[str] = None  # For job board redirects to external ATS
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'platform': self.platform.value,
            'job_id': self.job_id,
            'job_url': self.job_url,
            'status': self.status,
            'confirmation_number': self.confirmation_number,
            'error_message': self.error_message,
            'fields_filled': self.fields_filled,
            'total_fields': self.total_fields,
            'duration_seconds': self.duration_seconds,
            'redirect_url': self.redirect_url
        }


@dataclass
class DiceJob:
    """Dice.com specific job structure"""
    id: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    salary: Optional[str] = None
    job_type: Optional[str] = None  # Contract, Full-time, etc.
    remote: bool = False
    easy_apply: bool = False  # Dice has Easy Apply vs External Apply
    skills_required: List[str] = field(default_factory=list)
    posted_date: Optional[str] = None
