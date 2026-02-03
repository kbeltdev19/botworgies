"""
Evaluation Criteria System for 1000-Job Test Campaign

This module provides comprehensive metrics and analysis for evaluating
job application automation performance at scale.

Target Configuration:
- 1000 jobs to apply
- 100 concurrent browser sessions
- Kent Le profile (Auburn, AL, remote/hybrid/in-person, $75k+)
"""

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from enum import Enum
import statistics


class ApplicationStatus(Enum):
    """Status of a job application."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    ERROR = "error"


class FailureCategory(Enum):
    """Categories of application failures."""
    CAPTCHA = "captcha"
    LOGIN_REQUIRED = "login_required"
    FORM_ERROR = "form_error"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    PLATFORM_BLOCK = "platform_block"
    RESUME_UPLOAD_FAILED = "resume_upload_failed"
    MISSING_FIELDS = "missing_fields"
    UNKNOWN = "unknown"


@dataclass
class ApplicationMetrics:
    """Metrics for a single job application."""
    job_id: str
    job_title: str
    company: str
    platform: str
    url: str
    
    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # Status
    status: ApplicationStatus = ApplicationStatus.PENDING
    failure_category: Optional[FailureCategory] = None
    error_message: Optional[str] = None
    
    # Form filling details
    form_fields_total: int = 0
    form_fields_filled: int = 0
    questions_answered: int = 0
    questions_total: int = 0
    
    # Automation details
    browser_session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    # Screenshots/logs
    screenshot_path: Optional[str] = None
    page_html_path: Optional[str] = None
    log_entries: List[Dict[str, Any]] = field(default_factory=list)
    
    # Retries
    retry_count: int = 0
    retry_history: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CampaignSnapshot:
    """Snapshot of campaign performance at a point in time."""
    timestamp: datetime
    total_jobs: int
    completed: int
    successful: int
    failed: int
    in_progress: int
    pending: int
    rate_limited: int
    blocked: int
    
    # Performance metrics
    apps_per_minute: float = 0.0
    avg_duration_seconds: float = 0.0
    success_rate: float = 0.0
    
    # Resource usage
    active_sessions: int = 0
    queue_depth: int = 0
    memory_usage_mb: float = 0.0
    cpu_percent: float = 0.0


@dataclass
class PlatformPerformance:
    """Performance metrics by platform."""
    platform: str
    total_attempts: int = 0
    successful: int = 0
    failed: int = 0
    rate_limited: int = 0
    blocked: int = 0
    
    avg_duration_seconds: float = 0.0
    min_duration_seconds: float = 0.0
    max_duration_seconds: float = 0.0
    
    success_rate: float = 0.0
    common_errors: List[Dict[str, int]] = field(default_factory=list)
    
    def update_success_rate(self):
        """Calculate success rate."""
        if self.total_attempts > 0:
            self.success_rate = (self.successful / self.total_attempts) * 100


@dataclass
class EvaluationReport:
    """Complete evaluation report for a campaign."""
    # Campaign info
    campaign_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    target_jobs: int = 1000
    target_sessions: int = 100
    
    # Overall results
    total_attempted: int = 0
    total_successful: int = 0
    total_failed: int = 0
    total_rate_limited: int = 0
    total_blocked: int = 0
    total_skipped: int = 0
    
    # Performance
    duration_seconds: float = 0.0
    apps_per_minute: float = 0.0
    peak_apps_per_minute: float = 0.0
    avg_duration_per_app: float = 0.0
    
    # Breakdowns
    by_platform: Dict[str, PlatformPerformance] = field(default_factory=dict)
    by_failure_category: Dict[str, int] = field(default_factory=dict)
    by_job_title: Dict[str, Dict[str, int]] = field(default_factory=dict)
    by_time_period: List[CampaignSnapshot] = field(default_factory=list)
    
    # Detailed metrics
    applications: List[ApplicationMetrics] = field(default_factory=list)
    
    # Analysis
    what_worked: List[str] = field(default_factory=list)
    what_didnt_work: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    def calculate_overall_success_rate(self) -> float:
        """Calculate overall success rate."""
        if self.total_attempted == 0:
            return 0.0
        return (self.total_successful / self.total_attempted) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "campaign_id": self.campaign_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "target_jobs": self.target_jobs,
            "target_sessions": self.target_sessions,
            "overall_success_rate": self.calculate_overall_success_rate(),
            "total_attempted": self.total_attempted,
            "total_successful": self.total_successful,
            "total_failed": self.total_failed,
            "duration_seconds": self.duration_seconds,
            "apps_per_minute": self.apps_per_minute,
            "by_platform": {k: asdict(v) for k, v in self.by_platform.items()},
            "by_failure_category": self.by_failure_category,
            "what_worked": self.what_worked,
            "what_didnt_work": self.what_didnt_work,
            "recommendations": self.recommendations
        }
    
    def save_to_file(self, filepath: str):
        """Save report to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, default=str)


class CampaignEvaluator:
    """
    Evaluates job application campaigns at scale.
    
    Usage:
        evaluator = CampaignEvaluator(campaign_id="kent_le_1000", target_jobs=1000)
        
        # During campaign
        evaluator.record_application_start(app_metrics)
        evaluator.record_application_complete(app_metrics, status=ApplicationStatus.SUCCESS)
        evaluator.take_snapshot()
        
        # After campaign
        report = evaluator.generate_report()
        report.save_to_file("evaluation_report.json")
    """
    
    def __init__(self, campaign_id: str, target_jobs: int = 1000, target_sessions: int = 100):
        self.campaign_id = campaign_id
        self.target_jobs = target_jobs
        self.target_sessions = target_sessions
        self.start_time = datetime.now()
        
        # Storage
        self.applications: Dict[str, ApplicationMetrics] = {}
        self.snapshots: List[CampaignSnapshot] = []
        self.platform_stats: Dict[str, PlatformPerformance] = {}
        
        # Running counters
        self.completed = 0
        self.successful = 0
        self.failed = 0
        self.rate_limited = 0
        self.blocked = 0
        
        # Performance tracking
        self.durations: List[float] = []
        self.completion_times: List[datetime] = []
    
    def record_application_start(self, metrics: ApplicationMetrics):
        """Record the start of an application."""
        metrics.start_time = datetime.now()
        metrics.status = ApplicationStatus.IN_PROGRESS
        self.applications[metrics.job_id] = metrics
    
    def record_application_complete(
        self,
        job_id: str,
        status: ApplicationStatus,
        failure_category: Optional[FailureCategory] = None,
        error_message: Optional[str] = None
    ):
        """Record the completion of an application."""
        if job_id not in self.applications:
            return
        
        metrics = self.applications[job_id]
        metrics.end_time = datetime.now()
        metrics.status = status
        metrics.failure_category = failure_category
        metrics.error_message = error_message
        
        # Calculate duration
        if metrics.start_time:
            metrics.duration_seconds = (metrics.end_time - metrics.start_time).total_seconds()
            self.durations.append(metrics.duration_seconds)
        
        # Update counters
        self.completed += 1
        self.completion_times.append(datetime.now())
        
        if status == ApplicationStatus.SUCCESS:
            self.successful += 1
        elif status == ApplicationStatus.FAILED:
            self.failed += 1
        elif status == ApplicationStatus.RATE_LIMITED:
            self.rate_limited += 1
        elif status == ApplicationStatus.BLOCKED:
            self.blocked += 1
        
        # Update platform stats
        platform = metrics.platform
        if platform not in self.platform_stats:
            self.platform_stats[platform] = PlatformPerformance(platform=platform)
        
        platform_perf = self.platform_stats[platform]
        platform_perf.total_attempts += 1
        
        if status == ApplicationStatus.SUCCESS:
            platform_perf.successful += 1
        elif status == ApplicationStatus.FAILED:
            platform_perf.failed += 1
        elif status == ApplicationStatus.RATE_LIMITED:
            platform_perf.rate_limited += 1
        elif status == ApplicationStatus.BLOCKED:
            platform_perf.blocked += 1
        
        platform_perf.update_success_rate()
    
    def take_snapshot(
        self,
        active_sessions: int = 0,
        queue_depth: int = 0,
        memory_usage_mb: float = 0.0,
        cpu_percent: float = 0.0
    ) -> CampaignSnapshot:
        """Take a snapshot of current campaign performance."""
        now = datetime.now()
        
        # Calculate apps per minute (last 5 minutes)
        recent_completions = [
            t for t in self.completion_times
            if (now - t).total_seconds() <= 300
        ]
        apps_per_minute = len(recent_completions) / 5.0 if recent_completions else 0.0
        
        # Calculate average duration
        avg_duration = statistics.mean(self.durations) if self.durations else 0.0
        
        # Calculate success rate
        success_rate = (self.successful / self.completed * 100) if self.completed > 0 else 0.0
        
        snapshot = CampaignSnapshot(
            timestamp=now,
            total_jobs=self.target_jobs,
            completed=self.completed,
            successful=self.successful,
            failed=self.failed,
            in_progress=sum(1 for a in self.applications.values() if a.status == ApplicationStatus.IN_PROGRESS),
            pending=self.target_jobs - self.completed,
            rate_limited=self.rate_limited,
            blocked=self.blocked,
            apps_per_minute=apps_per_minute,
            avg_duration_seconds=avg_duration,
            success_rate=success_rate,
            active_sessions=active_sessions,
            queue_depth=queue_depth,
            memory_usage_mb=memory_usage_mb,
            cpu_percent=cpu_percent
        )
        
        self.snapshots.append(snapshot)
        return snapshot
    
    def generate_report(self) -> EvaluationReport:
        """Generate the final evaluation report."""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        # Calculate peak apps per minute from snapshots
        peak_apps_per_minute = max(
            (s.apps_per_minute for s in self.snapshots),
            default=0.0
        )
        
        # Build failure category breakdown
        failure_categories = {}
        for app in self.applications.values():
            if app.failure_category:
                cat = app.failure_category.value
                failure_categories[cat] = failure_categories.get(cat, 0) + 1
        
        # Build job title breakdown
        job_title_stats = {}
        for app in self.applications.values():
            title = app.job_title
            if title not in job_title_stats:
                job_title_stats[title] = {"attempted": 0, "successful": 0, "failed": 0}
            job_title_stats[title]["attempted"] += 1
            if app.status == ApplicationStatus.SUCCESS:
                job_title_stats[title]["successful"] += 1
            elif app.status == ApplicationStatus.FAILED:
                job_title_stats[title]["failed"] += 1
        
        # Generate analysis
        what_worked, what_didnt, recommendations = self._generate_analysis()
        
        report = EvaluationReport(
            campaign_id=self.campaign_id,
            start_time=self.start_time,
            end_time=end_time,
            target_jobs=self.target_jobs,
            target_sessions=self.target_sessions,
            total_attempted=self.completed,
            total_successful=self.successful,
            total_failed=self.failed,
            total_rate_limited=self.rate_limited,
            total_blocked=self.blocked,
            duration_seconds=duration,
            apps_per_minute=(self.completed / duration * 60) if duration > 0 else 0.0,
            peak_apps_per_minute=peak_apps_per_minute,
            avg_duration_per_app=statistics.mean(self.durations) if self.durations else 0.0,
            by_platform=self.platform_stats,
            by_failure_category=failure_categories,
            by_job_title=job_title_stats,
            by_time_period=self.snapshots,
            applications=list(self.applications.values()),
            what_worked=what_worked,
            what_didnt_work=what_didnt,
            recommendations=recommendations
        )
        
        return report
    
    def _generate_analysis(self) -> tuple:
        """Generate what worked, what didn't, and recommendations."""
        what_worked = []
        what_didnt = []
        recommendations = []
        
        # Analyze by platform
        best_platform = None
        worst_platform = None
        best_rate = 0.0
        worst_rate = 100.0
        
        for platform, stats in self.platform_stats.items():
            if stats.success_rate > best_rate:
                best_rate = stats.success_rate
                best_platform = platform
            if stats.success_rate < worst_rate and stats.total_attempts > 10:
                worst_rate = stats.success_rate
                worst_platform = platform
        
        if best_platform and best_rate > 70:
            what_worked.append(f"{best_platform} showed highest success rate at {best_rate:.1f}%")
        
        if worst_platform and worst_rate < 30:
            what_didnt.append(f"{worst_platform} had poor success rate at {worst_rate:.1f}%")
            recommendations.append(f"Investigate {worst_platform} blocking patterns and adjust delays")
        
        # Analyze overall success rate
        overall_rate = (self.successful / self.completed * 100) if self.completed > 0 else 0.0
        
        if overall_rate > 80:
            what_worked.append(f"Excellent overall success rate of {overall_rate:.1f}%")
        elif overall_rate < 50:
            what_didnt.append(f"Low overall success rate of {overall_rate:.1f}%")
            recommendations.append("Review anti-detection measures and form-filling accuracy")
        
        # Analyze speed
        avg_apps_per_min = (self.completed / ((datetime.now() - self.start_time).total_seconds() / 60)) if self.completed > 0 else 0
        
        if avg_apps_per_min > 20:
            what_worked.append(f"High throughput achieved: {avg_apps_per_min:.1f} apps/minute")
        elif avg_apps_per_min < 5:
            what_didnt.append(f"Low throughput: {avg_apps_per_min:.1f} apps/minute")
            recommendations.append("Optimize parallel session management and reduce wait times")
        
        # Analyze rate limiting
        if self.rate_limited > self.completed * 0.2:  # More than 20% rate limited
            what_didnt.append(f"High rate limiting: {self.rate_limited} applications ({self.rate_limited/self.completed*100:.1f}%)")
            recommendations.append("Implement more aggressive rate limiting and IP rotation")
        elif self.rate_limited < self.completed * 0.05:  # Less than 5% rate limited
            what_worked.append(f"Good rate limit avoidance: only {self.rate_limited/self.completed*100:.1f}% rate limited")
        
        # Analyze blocking
        if self.blocked > 10:
            what_didnt.append(f"Significant blocking detected: {self.blocked} applications")
            recommendations.append("Update browser fingerprinting and review detection patterns")
        
        # Default recommendations if list is short
        if len(recommendations) < 3:
            recommendations.extend([
                "Continue monitoring platform-specific success rates",
                "A/B test different application speeds",
                "Implement dynamic retry logic for transient failures"
            ])
        
        return what_worked, what_didnt, recommendations[:5]  # Top 5 recommendations
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """Get a quick progress summary during campaign."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        return {
            "campaign_id": self.campaign_id,
            "elapsed_minutes": elapsed / 60,
            "completed": self.completed,
            "successful": self.successful,
            "failed": self.failed,
            "progress_percent": (self.completed / self.target_jobs * 100) if self.target_jobs > 0 else 0,
            "estimated_remaining_minutes": (
                (self.target_jobs - self.completed) / (self.completed / elapsed * 60)
                if self.completed > 0 and elapsed > 0 else None
            ),
            "current_success_rate": (self.successful / self.completed * 100) if self.completed > 0 else 0
        }


# Pre-defined evaluation criteria for Kent Le's campaign
KENT_LE_EVALUATION_CRITERIA = {
    "campaign_name": "Kent Le - 1000 Job Application Test",
    "target_jobs": 1000,
    "target_concurrent_sessions": 100,
    "candidate_profile": {
        "name": "Kent Le",
        "location": "Auburn, AL",
        "open_to": ["remote", "hybrid", "in_person"],
        "min_salary": 75000,
        "target_roles": [
            "Client Success Manager",
            "Customer Success Manager", 
            "Account Manager",
            "Sales Representative",
            "Business Development Representative",
            "Account Executive"
        ],
        "experience_years": 3,
        "key_skills": ["CRM", "Salesforce", "Data Analysis", "Supply Chain", "Bilingual (Vietnamese)"]
    },
    "success_criteria": {
        "minimum_success_rate": 70,  # 70% minimum
        "target_success_rate": 85,   # 85% target
        "minimum_apps_per_minute": 10,
        "target_apps_per_minute": 30,
        "max_rate_limited_percent": 15,
        "max_blocked_percent": 5
    },
    "platforms_to_test": ["linkedin", "indeed", "zip_recruiter", "glassdoor"],
    "metrics_to_collect": [
        "application_success_rate_by_platform",
        "average_time_per_application",
        "form_completion_rate",
        "captcha_encounter_rate",
        "login_requirement_rate",
        "resume_upload_success_rate",
        "cover_letter_generation_success_rate",
        "error_breakdown_by_category",
        "peak_throughput_achieved",
        "session_stability_metrics"
    ]
}


def create_kent_le_evaluator() -> CampaignEvaluator:
    """Create a pre-configured evaluator for Kent Le's campaign."""
    return CampaignEvaluator(
        campaign_id="kent_le_1000_test",
        target_jobs=1000,
        target_sessions=100
    )


if __name__ == "__main__":
    # Test the evaluation system
    evaluator = create_kent_le_evaluator()
    
    # Simulate some applications
    for i in range(10):
        metrics = ApplicationMetrics(
            job_id=f"job_{i}",
            job_title="Customer Success Manager",
            company=f"Company {i}",
            platform="linkedin" if i % 2 == 0 else "indeed",
            url=f"https://example.com/job/{i}"
        )
        evaluator.record_application_start(metrics)
        
        # Simulate completion
        import random
        status = ApplicationStatus.SUCCESS if random.random() > 0.3 else ApplicationStatus.FAILED
        evaluator.record_application_complete(
            f"job_{i}",
            status=status,
            failure_category=FailureCategory.FORM_ERROR if status == ApplicationStatus.FAILED else None
        )
    
    # Generate report
    report = evaluator.generate_report()
    
    print(f"Campaign: {report.campaign_id}")
    print(f"Success Rate: {report.calculate_overall_success_rate():.1f}%")
    print(f"What Worked: {report.what_worked}")
    print(f"What Didn't: {report.what_didnt_work}")
    print(f"Recommendations: {report.recommendations}")
