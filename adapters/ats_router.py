"""
ATS Router - Unified Application Handler

Routes jobs to appropriate handlers based on platform type:
- Direct Apply: Greenhouse, Lever, Ashby (immediate submission)
- Native Flow: Indeed, LinkedIn (search + click + apply)
- Complex Forms: Workday, Taleo (queued for last)
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import time

from .base import JobPosting, ApplicationResult, ApplicationStatus, UserProfile, Resume

logger = logging.getLogger(__name__)


class PlatformCategory(Enum):
    """Categories of job platforms by application method."""
    DIRECT_APPLY = "direct_apply"      # Greenhouse, Lever, Ashby
    NATIVE_FLOW = "native_flow"        # Indeed, LinkedIn
    COMPLEX_FORM = "complex_form"      # Workday, Taleo, SAP
    UNKNOWN = "unknown"


@dataclass
class PlatformHandler:
    """Configuration for a platform handler."""
    name: str
    category: PlatformCategory
    handler_class: Any
    priority: int  # Lower = process first
    avg_success_rate: float
    avg_time_seconds: int


class ATSRouter:
    """
    Routes job applications to appropriate handlers based on platform.
    
    Usage:
        router = ATSRouter(browser_manager)
        result = await router.apply_to_job(job, resume, profile)
    """
    
    # Platform detection patterns
    PLATFORM_PATTERNS = {
        # Direct Apply Platforms
        'greenhouse': {
            'category': PlatformCategory.DIRECT_APPLY,
            'priority': 1,
            'success_rate': 0.75,
            'avg_time': 30,
        },
        'lever': {
            'category': PlatformCategory.DIRECT_APPLY,
            'priority': 2,
            'success_rate': 0.70,
            'avg_time': 35,
        },
        'ashby': {
            'category': PlatformCategory.DIRECT_APPLY,
            'priority': 3,
            'success_rate': 0.65,
            'avg_time': 40,
        },
        'smartrecruiters': {
            'category': PlatformCategory.DIRECT_APPLY,
            'priority': 4,
            'success_rate': 0.60,
            'avg_time': 45,
        },
        'bamboohr': {
            'category': PlatformCategory.DIRECT_APPLY,
            'priority': 5,
            'success_rate': 0.55,
            'avg_time': 50,
        },
        
        # Native Flow Platforms
        'indeed': {
            'category': PlatformCategory.NATIVE_FLOW,
            'priority': 10,
            'success_rate': 0.45,
            'avg_time': 60,
        },
        'linkedin': {
            'category': PlatformCategory.NATIVE_FLOW,
            'priority': 11,
            'success_rate': 0.40,
            'avg_time': 90,
        },
        'ziprecruiter': {
            'category': PlatformCategory.NATIVE_FLOW,
            'priority': 12,
            'success_rate': 0.35,
            'avg_time': 75,
        },
        
        # Complex Form Platforms
        'workday': {
            'category': PlatformCategory.COMPLEX_FORM,
            'priority': 20,
            'success_rate': 0.25,
            'avg_time': 120,
        },
        'taleo': {
            'category': PlatformCategory.COMPLEX_FORM,
            'priority': 21,
            'success_rate': 0.20,
            'avg_time': 150,
        },
        'sap': {
            'category': PlatformCategory.COMPLEX_FORM,
            'priority': 22,
            'success_rate': 0.15,
            'avg_time': 180,
        },
        'icims': {
            'category': PlatformCategory.COMPLEX_FORM,
            'priority': 23,
            'success_rate': 0.15,
            'avg_time': 180,
        },
    }
    
    def __init__(self, browser_manager=None):
        self.browser_manager = browser_manager
        self.handlers: Dict[str, Any] = {}
        self.stats = {
            'total_attempted': 0,
            'by_platform': {},
            'by_category': {},
        }
        
    def detect_platform(self, url: str) -> str:
        """Detect platform from job URL."""
        url_lower = url.lower()
        
        for platform, config in self.PLATFORM_PATTERNS.items():
            if platform in url_lower:
                return platform
                
        return 'unknown'
        
    def get_platform_config(self, platform: str) -> Dict:
        """Get configuration for a platform."""
        return self.PLATFORM_PATTERNS.get(platform, {
            'category': PlatformCategory.UNKNOWN,
            'priority': 99,
            'success_rate': 0.10,
            'avg_time': 120,
        })
        
    def categorize_job(self, job: JobPosting) -> PlatformCategory:
        """Categorize a job by platform type."""
        platform = self.detect_platform(job.url)
        config = self.get_platform_config(platform)
        return config['category']
        
    def sort_jobs_by_priority(self, jobs: List[JobPosting]) -> List[JobPosting]:
        """Sort jobs by platform priority (high success rate first)."""
        def get_priority(job):
            platform = self.detect_platform(job.url)
            config = self.get_platform_config(platform)
            return config['priority']
            
        return sorted(jobs, key=get_priority)
        
    async def apply_to_job(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        auto_submit: bool = False
    ) -> ApplicationResult:
        """
        Route job to appropriate handler and apply.
        
        Args:
            job: Job posting to apply to
            resume: Resume to use
            profile: User profile information
            auto_submit: Whether to auto-submit or stop for review
            
        Returns:
            ApplicationResult with status and details
        """
        platform = self.detect_platform(job.url)
        config = self.get_platform_config(platform)
        category = config['category']
        
        logger.info(f"🎯 Routing {job.title} at {job.company} to {platform} ({category.value})")
        
        start_time = time.time()
        
        try:
            # Route to appropriate handler
            if category == PlatformCategory.DIRECT_APPLY:
                result = await self._handle_direct_apply(job, resume, profile, auto_submit)
            elif category == PlatformCategory.NATIVE_FLOW:
                result = await self._handle_native_flow(job, resume, profile, auto_submit)
            elif category == PlatformCategory.COMPLEX_FORM:
                result = await self._handle_complex_form(job, resume, profile, auto_submit)
            else:
                result = ApplicationResult(
                    status=ApplicationStatus.ERROR,
                    message=f"Unknown platform: {platform}"
                )
                
        except Exception as e:
            logger.error(f"❌ Error applying to {job.title}: {e}")
            result = ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=str(e)
            )
            
        # Update stats
        duration = time.time() - start_time
        self._update_stats(platform, category, result, duration)
        
        return result
        
    async def _handle_direct_apply(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        auto_submit: bool
    ) -> ApplicationResult:
        """Handle direct apply platforms (Greenhouse, Lever, etc.)."""
        from .direct_apply import DirectApplyHandler
        
        handler = DirectApplyHandler(self.browser_manager)
        return await handler.apply(job, resume, profile, auto_submit)
        
    async def _handle_native_flow(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        auto_submit: bool
    ) -> ApplicationResult:
        """Handle native flow platforms (Indeed, LinkedIn)."""
        platform = self.detect_platform(job.url)
        
        if platform == 'indeed':
            from .indeed import IndeedAdapter
            handler = IndeedAdapter(self.browser_manager)
        elif platform == 'linkedin':
            from .linkedin import LinkedInAdapter
            handler = LinkedInAdapter(self.browser_manager)
        else:
            return ApplicationResult(
                status=ApplicationStatus.ERROR,
                message=f"No native flow handler for {platform}"
            )
            
        return await handler.apply_to_job(job, resume, profile, auto_submit=auto_submit)
        
    async def _handle_complex_form(
        self,
        job: JobPosting,
        resume: Resume,
        profile: UserProfile,
        auto_submit: bool
    ) -> ApplicationResult:
        """Handle complex form platforms (Workday, Taleo)."""
        from .complex_forms import ComplexFormHandler
        
        handler = ComplexFormHandler(self.browser_manager)
        return await handler.apply(job, resume, profile, auto_submit)
        
    def _update_stats(self, platform: str, category: PlatformCategory, result: ApplicationResult, duration: float):
        """Update application statistics."""
        self.stats['total_attempted'] += 1
        
        # By platform
        if platform not in self.stats['by_platform']:
            self.stats['by_platform'][platform] = {'success': 0, 'failed': 0, 'total': 0}
        self.stats['by_platform'][platform]['total'] += 1
        if result.status == ApplicationStatus.SUBMITTED:
            self.stats['by_platform'][platform]['success'] += 1
        else:
            self.stats['by_platform'][platform]['failed'] += 1
            
        # By category
        cat_key = category.value
        if cat_key not in self.stats['by_category']:
            self.stats['by_category'][cat_key] = {'success': 0, 'failed': 0, 'total': 0, 'avg_time': 0}
        self.stats['by_category'][cat_key]['total'] += 1
        if result.status == ApplicationStatus.SUBMITTED:
            self.stats['by_category'][cat_key]['success'] += 1
            
        # Update avg time
        current_avg = self.stats['by_category'][cat_key].get('avg_time', 0)
        total = self.stats['by_category'][cat_key]['total']
        self.stats['by_category'][cat_key]['avg_time'] = (current_avg * (total - 1) + duration) / total
        
    def get_stats(self) -> Dict:
        """Get application statistics."""
        return {
            'total_attempted': self.stats['total_attempted'],
            'by_platform': self.stats['by_platform'],
            'by_category': self.stats['by_category'],
            'overall_success_rate': self._calculate_overall_success_rate(),
        }
        
    def _calculate_overall_success_rate(self) -> float:
        """Calculate overall success rate."""
        if self.stats['total_attempted'] == 0:
            return 0.0
            
        total_success = sum(
            p['success'] for p in self.stats['by_platform'].values()
        )
        return total_success / self.stats['total_attempted']
        
    def print_stats(self):
        """Print statistics summary."""
        print("\n" + "="*70)
        print("📊 ATS ROUTER STATISTICS")
        print("="*70)
        print(f"Total Attempted: {self.stats['total_attempted']}")
        print(f"Overall Success Rate: {self._calculate_overall_success_rate():.1%}")
        
        print("\nBy Category:")
        for cat, stats in sorted(self.stats['by_category'].items()):
            success_rate = stats['success'] / max(stats['total'], 1)
            print(f"  {cat:15s}: {stats['success']}/{stats['total']} ({success_rate:.1%}) avg {stats.get('avg_time', 0):.0f}s")
            
        print("\nBy Platform:")
        for platform, stats in sorted(
            self.stats['by_platform'].items(),
            key=lambda x: x[1]['success'],
            reverse=True
        ):
            success_rate = stats['success'] / max(stats['total'], 1)
            print(f"  {platform:15s}: {stats['success']}/{stats['total']} ({success_rate:.1%})")
            
        print("="*70)
