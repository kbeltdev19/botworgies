"""
Live Testing Framework for ATS Automation System
"""

import os
import sys
import asyncio
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ats_automation import ATSRouter, UserProfile, ApplicationResult, ATSPlatform
from ats_automation.browserbase_manager import BrowserBaseManager


@dataclass
class TestMetrics:
    job_url: str
    platform: ATSPlatform
    success: bool
    status: str
    duration_seconds: float
    fields_filled: int = 0
    total_fields: int = 0
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PlatformStats:
    platform: ATSPlatform
    total_attempts: int = 0
    successful: int = 0
    failed: int = 0
    avg_duration: float = 0.0
    
    @property
    def success_rate(self) -> float:
        if self.total_attempts == 0:
            return 0.0
        return (self.successful / self.total_attempts) * 100


@dataclass
class LiveTestReport:
    test_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    candidate_name: str = ""
    target_location: str = ""
    total_jobs: int = 0
    total_successful: int = 0
    total_failed: int = 0
    overall_success_rate: float = 0.0
    total_duration_seconds: float = 0.0
    avg_time_per_application: float = 0.0
    platform_stats: Dict[str, PlatformStats] = field(default_factory=dict)
    results: List[TestMetrics] = field(default_factory=list)
    error_categories: Dict[str, int] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "candidate_name": self.candidate_name,
            "target_location": self.target_location,
            "total_jobs": self.total_jobs,
            "total_successful": self.total_successful,
            "total_failed": self.total_failed,
            "overall_success_rate": self.overall_success_rate,
            "total_duration_minutes": self.total_duration_seconds / 60,
            "avg_time_per_application_seconds": self.avg_time_per_application,
            "platform_breakdown": {
                platform: {
                    "attempts": stats.total_attempts,
                    "successful": stats.successful,
                    "failed": stats.failed,
                    "success_rate": f"{stats.success_rate:.1f}%",
                }
                for platform, stats in self.platform_stats.items()
            },
            "error_categories": self.error_categories,
            "recommendations": self.recommendations
        }
    
    def save(self, filepath: str):
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


class LiveTestRunner:
    def __init__(self, user_profile: UserProfile, ai_client=None):
        self.profile = user_profile
        self.ai_client = ai_client
        self.browser = BrowserBaseManager()
        self.report: Optional[LiveTestReport] = None
        
    async def run_test_batch(
        self,
        job_urls: List[str],
        target_location: str = "",
        concurrent: int = 5,
        test_id: Optional[str] = None
    ) -> LiveTestReport:
        test_id = test_id or f"livetest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.report = LiveTestReport(
            test_id=test_id,
            start_time=datetime.now(),
            candidate_name=f"{self.profile.first_name} {self.profile.last_name}",
            target_location=target_location,
            total_jobs=len(job_urls)
        )
        
        print(f"\n{'='*70}")
        print(f"🧪 LIVE TEST BATCH: {test_id}")
        print(f"{'='*70}")
        print(f"Candidate: {self.report.candidate_name}")
        print(f"Location: {target_location}")
        print(f"Total Jobs: {len(job_urls)}")
        print(f"Concurrent: {concurrent}")
        print(f"{'='*70}\n")
        
        semaphore = asyncio.Semaphore(concurrent)
        
        async def process_job(url: str, index: int):
            async with semaphore:
                print(f"[{index+1}/{len(job_urls)}] Testing: {url[:60]}...")
                return await self._test_single_job(url)
        
        start_time = time.time()
        tasks = [process_job(url, i) for i, url in enumerate(job_urls)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        
        for result in results:
            if isinstance(result, TestMetrics):
                self.report.results.append(result)
                self._update_stats(result)
            elif isinstance(result, Exception):
                error_metric = TestMetrics(
                    job_url="unknown",
                    platform=ATSPlatform.UNKNOWN,
                    success=False,
                    status="exception",
                    duration_seconds=0,
                    error_message=str(result)
                )
                self.report.results.append(error_metric)
        
        self.report.end_time = datetime.now()
        self.report.total_duration_seconds = end_time - start_time
        self.report.overall_success_rate = (
            (self.report.total_successful / len(job_urls)) * 100 
            if job_urls else 0
        )
        self.report.avg_time_per_application = (
            self.report.total_duration_seconds / len(job_urls) 
            if job_urls else 0
        )
        
        self.report.recommendations = self._generate_recommendations()
        
        return self.report
    
    async def _test_single_job(self, job_url: str) -> TestMetrics:
        start_time = time.time()
        
        try:
            router = ATSRouter(self.profile, self.ai_client)
            result: ApplicationResult = await router.apply(job_url)
            
            duration = time.time() - start_time
            
            await router.cleanup()
            
            return TestMetrics(
                job_url=job_url,
                platform=result.platform,
                success=result.success,
                status=result.status,
                duration_seconds=duration,
                fields_filled=result.fields_filled,
                total_fields=result.total_fields,
                error_message=result.error_message,
                confirmation_number=result.confirmation_number
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return TestMetrics(
                job_url=job_url,
                platform=ATSPlatform.UNKNOWN,
                success=False,
                status="exception",
                duration_seconds=duration,
                error_message=str(e)
            )
    
    def _update_stats(self, metric: TestMetrics):
        platform_key = metric.platform.value
        
        if platform_key not in self.report.platform_stats:
            self.report.platform_stats[platform_key] = PlatformStats(
                platform=metric.platform
            )
        
        stats = self.report.platform_stats[platform_key]
        stats.total_attempts += 1
        
        if metric.success:
            stats.successful += 1
            self.report.total_successful += 1
        else:
            stats.failed += 1
            self.report.total_failed += 1
            
            error_cat = self._categorize_error(metric.error_message)
            self.report.error_categories[error_cat] = (
                self.report.error_categories.get(error_cat, 0) + 1
            )
        
        stats.avg_duration = (
            (stats.avg_duration * (stats.total_attempts - 1) + metric.duration_seconds)
            / stats.total_attempts
        )
    
    def _categorize_error(self, error_message: Optional[str]) -> str:
        if not error_message:
            return "unknown"
        
        error_lower = error_message.lower()
        
        if any(word in error_lower for word in ['timeout', 'timed out']):
            return "timeout"
        elif any(word in error_lower for word in ['element not found', 'selector']):
            return "element_not_found"
        elif any(word in error_lower for word in ['navigation', 'goto']):
            return "navigation_error"
        elif any(word in error_lower for word in ['captcha', 'robot', 'challenge']):
            return "anti_bot"
        else:
            return "other"
    
    def _generate_recommendations(self) -> List[str]:
        recommendations = []
        
        if self.report.overall_success_rate < 50:
            recommendations.append(
                f"⚠️ LOW SUCCESS RATE: {self.report.overall_success_rate:.1f}% - "
                "Consider increasing delays and improving stealth measures"
            )
        elif self.report.overall_success_rate > 80:
            recommendations.append(
                f"✅ EXCELLENT SUCCESS RATE: {self.report.overall_success_rate:.1f}% - "
                "System performing well"
            )
        
        for platform, stats in self.report.platform_stats.items():
            if stats.success_rate < 40 and stats.total_attempts > 5:
                recommendations.append(
                    f"❌ {platform.upper()}: Low success rate ({stats.success_rate:.1f}%) - "
                    "Needs handler optimization"
                )
        
        if not recommendations:
            recommendations.append("✅ No issues detected - System operating optimally")
        
        return recommendations
    
    def print_report(self):
        if not self.report:
            print("No report available")
            return
        
        r = self.report
        
        print(f"\n{'='*70}")
        print(f"📊 LIVE TEST REPORT: {r.test_id}")
        print(f"{'='*70}")
        
        print(f"\n📋 SUMMARY:")
        print(f"  Duration: {r.total_duration_seconds/60:.1f} minutes")
        print(f"  Total Jobs: {r.total_jobs}")
        print(f"  Successful: {r.total_successful}")
        print(f"  Failed: {r.total_failed}")
        print(f"  Success Rate: {r.overall_success_rate:.1f}%")
        print(f"  Avg Time/App: {r.avg_time_per_application:.1f}s")
        
        print(f"\n🏢 PLATFORM BREAKDOWN:")
        for platform, stats in sorted(
            r.platform_stats.items(), 
            key=lambda x: x[1].total_attempts, 
            reverse=True
        ):
            print(f"\n  {platform.upper()}:")
            print(f"    Attempts: {stats.total_attempts}")
            print(f"    Success: {stats.successful}/{stats.total_attempts} ({stats.success_rate:.1f}%)")
            print(f"    Avg Duration: {stats.avg_duration:.1f}s")
        
        print(f"\n❌ ERROR CATEGORIES:")
        for error, count in sorted(r.error_categories.items(), key=lambda x: -x[1]):
            print(f"  {error}: {count}")
        
        print(f"\n💡 RECOMMENDATIONS:")
        for rec in r.recommendations:
            print(f"  • {rec}")
        
        print(f"\n{'='*70}\n")


# Kent Le Test Configuration
KENT_LE_PROFILE = UserProfile(
    first_name="Kent",
    last_name="Le",
    email="kle4311@gmail.com",
    phone="404-934-0630",
    resume_path="Test Resumes/Kent_Le_Resume.pdf",
    resume_text="""KENT LE
Results-driven Client Success Manager with extensive experience in customer relationship management.
Skills: CRM, Salesforce, Data Analysis, Supply Chain, Bilingual (Vietnamese)""",
    linkedin_url="https://linkedin.com/in/kentle",
    salary_expectation="$75,000 - $95,000",
    years_experience=3,
    skills=[
        "Customer Success",
        "Account Management",
        "CRM",
        "Salesforce",
        "Data Analysis",
        "Supply Chain",
        "Bilingual (Vietnamese)",
        "Excel",
        "HubSpot"
    ],
    work_history=[
        {
            "company": "Estate Media House",
            "title": "Sales Representative / Client Success Manager",
            "dates": "June 2020 - December 2020",
            "description": "Managed full-cycle sales process, exceeded quotas by 25%"
        },
        {
            "company": "King of Pops",
            "title": "Bilingual Sales Team Manager",
            "dates": "May 2019 - August 2019",
            "description": "Led team of 8 sales representatives across 15+ venues"
        }
    ],
    education=[
        {
            "school": "Auburn University",
            "degree": "Bachelor of Science",
            "field": "Supply Chain Management",
            "dates": "Expected 2025"
        }
    ]
)


async def run_kent_le_500_test():
    """Run 500 job test for Kent Le in Auburn, AL area"""
    
    print("\n" + "="*70)
    print("🚀 KENT LE 500-JOB LIVE TEST")
    print("="*70)
    print("\nPhase 1: Collecting job URLs from multiple sources...")
    print("  • Searching Dice.com for Auburn/Remote jobs")
    print("  • Collecting Workday job postings")
    print("  • Gathering other ATS platform URLs\n")
    
    # Initialize tester
    tester = LiveTestRunner(KENT_LE_PROFILE)
    
    # Search for jobs on Dice first
    from ats_automation.handlers.dice import DiceHandler
    
    browser = BrowserBaseManager()
    dice = DiceHandler(browser, KENT_LE_PROFILE)
    
    # Search for 500+ jobs across different queries
    all_jobs = []
    
    search_queries = [
        ("Customer Success Manager", "Auburn, AL"),
        ("Account Manager", "Atlanta, GA"),
        ("Sales Representative", "Remote"),
        ("Client Success", "Birmingham, AL"),
        ("Business Development", "Montgomery, AL"),
    ]
    
    for query, location in search_queries:
        print(f"Searching: {query} in {location}...")
        try:
            jobs = await dice.search_jobs(
                query=query,
                location=location,
                remote=(location == "Remote"),
                max_results=100
            )
            all_jobs.extend(jobs)
            print(f"  Found {len(jobs)} jobs")
        except Exception as e:
            print(f"  Error: {e}")
    
    await browser.close_all_sessions()
    
    # Deduplicate by URL
    seen_urls = set()
    unique_jobs = []
    for job in all_jobs:
        if job.url not in seen_urls:
            seen_urls.add(job.url)
            unique_jobs.append(job)
    
    # Take first 500
    test_jobs = unique_jobs[:500]
    
    print(f"\n✅ Collected {len(test_jobs)} unique jobs for testing")
    print(f"  Easy Apply jobs: {sum(1 for j in test_jobs if j.easy_apply)}")
    print(f"  Remote jobs: {sum(1 for j in test_jobs if j.remote)}")
    
    # Run the test
    print(f"\n{'='*70}")
    print("Phase 2: Running live test batch...")
    print(f"{'='*70}\n")
    
    report = await tester.run_test_batch(
        job_urls=[j.url for j in test_jobs],
        target_location="Auburn, AL / Remote",
        concurrent=5,
        test_id="kent_le_500_auburn_al"
    )
    
    # Print and save
    tester.print_report()
    
    output_dir = Path("test_results")
    output_dir.mkdir(exist_ok=True)
    report.save(output_dir / f"{report.test_id}_report.json")
    
    print(f"✅ Full report saved to: test_results/{report.test_id}_report.json")
    
    return report


if __name__ == "__main__":
    asyncio.run(run_kent_le_500_test())
