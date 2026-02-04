"""
Unified Job Board Scraping Framework

Supports 40+ job boards with intelligent deduplication and ATS routing.
"""

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Any
import asyncio
import aiohttp
import ssl
from urllib.parse import urljoin, urlparse
import logging

logger = logging.getLogger(__name__)


@dataclass
class JobPosting:
    """Unified job posting model across all boards."""
    id: str
    title: str
    company: str
    location: str
    description: str
    url: str
    source: str  # Which board it came from
    posted_date: Optional[datetime] = None
    employment_type: Optional[str] = None  # Full-time, Contract, etc.
    salary_range: Optional[str] = None
    clearance_required: Optional[str] = None  # Secret, TS, TS/SCI, etc.
    remote: bool = False
    easy_apply: bool = False  # Has one-click apply
    apply_url: Optional[str] = None  # Direct application URL
    skills: List[str] = field(default_factory=list)
    raw_data: Dict = field(default_factory=dict)  # Original board-specific data
    
    def generate_key(self) -> str:
        """Generate deduplication key."""
        # Normalize company name
        company = re.sub(r'\s+(inc|llc|corp|ltd|company)\.?$', '', 
                        self.company.lower(), flags=re.IGNORECASE).strip()
        
        # Normalize title
        title = self.title.lower()
        title = title.replace('sr.', 'senior').replace('jr.', 'junior')
        title = title.replace('software engineer', 'software developer')
        title = re.sub(r'[^\w\s]', '', title).strip()
        
        # Normalize location (remove remote indicators for comparison)
        location = self.location.lower().replace('remote', '').replace(',', '').strip()
        
        # Create content hash
        content = f"{title}|{company}"
        content_hash = hashlib.md5(content.encode()).hexdigest()[:10]
        
        return f"{company}|{content_hash}|{location}"


@dataclass
class SearchCriteria:
    """Search parameters for job boards."""
    query: str
    location: Optional[str] = None
    radius: int = 25  # miles
    posted_within_days: int = 7
    employment_type: Optional[str] = None  # fulltime, contract, etc.
    remote_only: bool = False
    clearance_levels: List[str] = field(default_factory=list)  # For clearance jobs
    experience_level: Optional[str] = None  # entry, mid, senior
    min_salary: Optional[int] = None
    max_results: int = 100


class BaseJobBoardScraper(ABC):
    """Abstract base class for all job board scrapers."""
    
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self.session = session
        self._owned_session = session is None
        self.name = self.__class__.__name__.replace('Scraper', '').lower()
        
    async def __aenter__(self):
        if self._owned_session:
            # Create SSL context that doesn't verify certificates (for systems with cert issues)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            self.session = aiohttp.ClientSession(
                headers=self.get_default_headers(),
                connector=aiohttp.TCPConnector(ssl=ssl_context)
            )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._owned_session and self.session:
            await self.session.close()
            
    @abstractmethod
    def get_default_headers(self) -> Dict[str, str]:
        """Return default HTTP headers for this board."""
        pass
        
    @abstractmethod
    async def search(self, criteria: SearchCriteria) -> List[JobPosting]:
        """Search for jobs matching criteria."""
        pass
        
    @abstractmethod
    def get_ats_type(self, url: str) -> Optional[str]:
        """Detect ATS type from job URL for routing."""
        pass
        
    async def fetch_json(self, url: str, **kwargs) -> Dict:
        """Fetch and parse JSON from URL."""
        async with self.session.get(url, **kwargs) as response:
            response.raise_for_status()
            return await response.json()
            
    async def fetch_text(self, url: str, **kwargs) -> str:
        """Fetch text content from URL."""
        async with self.session.get(url, **kwargs) as response:
            response.raise_for_status()
            return await response.text()


class DeduplicationEngine:
    """Cross-board job deduplication."""
    
    def __init__(self):
        self.seen_keys: Set[str] = set()
        self.duplicate_count = 0
        
    def is_duplicate(self, job: JobPosting) -> bool:
        """Check if job is a duplicate."""
        key = job.generate_key()
        if key in self.seen_keys:
            self.duplicate_count += 1
            return True
        self.seen_keys.add(key)
        return False
        
    def filter_unique(self, jobs: List[JobPosting]) -> List[JobPosting]:
        """Filter to unique jobs only."""
        unique = []
        for job in jobs:
            if not self.is_duplicate(job):
                unique.append(job)
        return unique
        
    def get_stats(self) -> Dict[str, int]:
        """Get deduplication statistics."""
        return {
            'unique_jobs': len(self.seen_keys),
            'duplicates_filtered': self.duplicate_count,
            'total_seen': len(self.seen_keys) + self.duplicate_count
        }


class ATSRouter:
    """Routes job URLs to appropriate ATS handlers."""
    
    # URL pattern to ATS type mapping
    ATS_PATTERNS = {
        'greenhouse': [
            r'boards\.greenhouse\.io',
            r'greenhouse\.io',
        ],
        'lever': [
            r'jobs\.lever\.co',
            r'lever\.co',
        ],
        'workday': [
            r'\.workday\.com',
            r'wd\d+\.myworkdayjobs\.com',
        ],
        'ashby': [
            r'jobs\.ashbyhq\.com',
        ],
        'smartrecruiters': [
            r'jobs\.smartrecruiters\.com',
        ],
        'bamboohr': [
            r'\.bamboohr\.com/careers',
        ],
        'jazzhr': [
            r'\.applytojob\.com',
            r'jazzhr\.com',
        ],
        'icims': [
            r'\.icims\.com',
        ],
        'taleo': [
            r'\.taleo\.net',
        ],
        'clearancejobs': [
            r'clearancejobs\.com',
        ],
        'dice': [
            r'dice\.com/job-detail',
        ],
        'indeed': [
            r'indeed\.com',
            r'indeed\.com/viewjob',
        ],
        'linkedin': [
            r'linkedin\.com/jobs',
        ],
    }
    
    @classmethod
    def detect_ats(cls, url: str) -> Optional[str]:
        """Detect ATS type from job URL."""
        url_lower = url.lower()
        
        for ats_type, patterns in cls.ATS_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, url_lower):
                    return ats_type
                    
        return None
        
    @classmethod
    def is_direct_application_url(cls, url: str) -> bool:
        """Check if URL is a direct application form vs career page."""
        ats = cls.detect_ats(url)
        
        # Known direct application patterns
        direct_patterns = [
            r'greenhouse\.io/[^/]+/jobs/\d+',
            r'jobs\.lever\.co/[^/]+/[^/]+',
            r'jobs\.ashbyhq\.com/[^/]+',
            r'clearancejobs\.com/job/\d+',
            r'dice\.com/job-detail',
        ]
        
        for pattern in direct_patterns:
            if re.search(pattern, url.lower()):
                return True
                
        # Known career page patterns (not direct apply)
        career_patterns = [
            r'careers\..+\?',
            r'/careers\?search=',
            r'/jobs\?keywords=',
            r'/search\?',
        ]
        
        for pattern in career_patterns:
            if re.search(pattern, url.lower()):
                return False
                
        # Default: assume direct if we can detect an ATS
        return ats is not None


class UnifiedJobPipeline:
    """Orchestrates scraping from multiple boards with deduplication."""
    
    def __init__(self):
        self.scrapers: List[BaseJobBoardScraper] = []
        self.dedup_engine = DeduplicationEngine()
        self.router = ATSRouter()
        self.results: List[JobPosting] = []
        
    def add_scraper(self, scraper: BaseJobBoardScraper):
        """Add a job board scraper to the pipeline."""
        self.scrapers.append(scraper)
        
    async def search_all(self, criteria: SearchCriteria) -> List[JobPosting]:
        """Search all configured boards and deduplicate results."""
        all_jobs: List[JobPosting] = []
        
        # Search all boards concurrently
        tasks = [scraper.search(criteria) for scraper in self.scrapers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for scraper, result in zip(self.scrapers, results):
            if isinstance(result, Exception):
                logger.error(f"{scraper.name} scraper failed: {result}")
                continue
            logger.info(f"{scraper.name}: Found {len(result)} jobs")
            all_jobs.extend(result)
            
        # Deduplicate
        unique_jobs = self.dedup_engine.filter_unique(all_jobs)
        
        # Enrich with ATS detection
        for job in unique_jobs:
            job.apply_url = job.url  # Default to job page
            
        self.results = unique_jobs
        return unique_jobs
        
    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        stats = self.dedup_engine.get_stats()
        
        # Count by source
        source_counts = {}
        for job in self.results:
            source_counts[job.source] = source_counts.get(job.source, 0) + 1
            
        # Count by ATS type
        ats_counts = {}
        for job in self.results:
            ats = self.router.detect_ats(job.url)
            ats_type = ats or 'unknown'
            ats_counts[ats_type] = ats_counts.get(ats_type, 0) + 1
            
        stats['by_source'] = source_counts
        stats['by_ats'] = ats_counts
        
        return stats


# Import all scrapers for easy access
from .dice import DiceScraper
from .clearancejobs import ClearanceJobsScraper
from .indeed_rss import IndeedRssScraper
from .greenhouse_api import GreenhouseAPIScraper
from .lever_api import LeverAPIScraper

__all__ = [
    'JobPosting',
    'SearchCriteria', 
    'BaseJobBoardScraper',
    'DeduplicationEngine',
    'ATSRouter',
    'UnifiedJobPipeline',
    'DiceScraper',
    'ClearanceJobsScraper',
    'IndeedRssScraper',
    'GreenhouseAPIScraper',
    'LeverAPIScraper',
]
