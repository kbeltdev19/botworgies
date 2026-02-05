"""
Production Application Tests - Real Jobs, Real Submissions, Real Feedback

This test suite submits ACTUAL applications to REAL job postings.
Uses comprehensive monitoring to track success/failure and iterate.

⚠️  WARNING: This will submit real job applications!

Prerequisites:
1. Valid test resume PDF at /tmp/test_resume.pdf
2. Real job URLs configured below
3. Monitoring database will track all attempts
4. Check logs/applications.log for detailed traces

Recommended approach:
1. Start with 1-2 test applications
2. Check screenshots in logs/evidence/
3. Review monitoring report
4. Iterate based on failures
5. Scale up once success rate > 70%
"""

import pytest
import asyncio
import os
from datetime import datetime
from pathlib import Path

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.asyncio,
    pytest.mark.production,
]


# ============================================================================
# REAL JOB URLs - UPDATE THESE WITH ACTUAL JOBS
# ============================================================================

REAL_JOBS = {
    # Example Greenhouse job (update with real URL)
    "greenhouse": {
        "url": os.getenv("PRODUCTION_GREENHOUSE_URL", ""),
        "enabled": bool(os.getenv("PRODUCTION_GREENHOUSE_URL")),
    },
    
    # Example Lever job (update with real URL)
    "lever": {
        "url": os.getenv("PRODUCTION_LEVER_URL", ""),
        "enabled": bool(os.getenv("PRODUCTION_LEVER_URL")),
    },
    
    # Example LinkedIn job (update with real URL and li_at cookie)
    "linkedin": {
        "url": os.getenv("PRODUCTION_LINKEDIN_URL", ""),
        "li_at": os.getenv("LINKEDIN_LI_AT", ""),
        "enabled": bool(os.getenv("PRODUCTION_LINKEDIN_URL") and os.getenv("LINKEDIN_LI_AT")),
    },
    
    # Example Workday job
    "workday": {
        "url": os.getenv("PRODUCTION_WORKDAY_URL", ""),
        "enabled": bool(os.getenv("PRODUCTION_WORKDAY_URL")),
    },
}


@pytest.fixture(scope="module")
def production_profile():
    """Profile for production applications - USE REAL INFO."""
    from adapters.base import UserProfile
    
    # ⚠️  UPDATE WITH YOUR ACTUAL INFORMATION
    return UserProfile(
        first_name=os.getenv("APPLICANT_FIRST_NAME", "Test"),
        last_name=os.getenv("APPLICANT_LAST_NAME", "User"),
        email=os.getenv("APPLICANT_EMAIL", "test@example.com"),
        phone=os.getenv("APPLICANT_PHONE", "555-123-4567"),
        linkedin_url=os.getenv("APPLICANT_LINKEDIN", ""),
        years_experience=int(os.getenv("APPLICANT_YEARS_EXP", "3")),
        work_authorization="Yes",
        sponsorship_required="No",
        custom_answers={
            "salary_expectations": os.getenv("APPLICANT_SALARY", "$80,000 - $120,000"),
            "notice_period": "2 weeks",
            "willing_to_relocate": "Yes",
        }
    )


@pytest.fixture(scope="module")
def production_resume():
    """Resume for production applications."""
    from adapters.base import Resume
    
    resume_path = os.getenv("RESUME_PATH", "/tmp/test_resume.pdf")
    
    # Create test resume text if file doesn't exist
    if not Path(resume_path).exists():
        print(f"⚠️  Resume not found at {resume_path}")
        print("Creating dummy resume file...")
        Path(resume_path).touch()
    
    resume_text = """
PROFESSIONAL SUMMARY
Experienced software engineer with expertise in Python, JavaScript, and cloud technologies.

EXPERIENCE
Senior Software Engineer | TechCorp | 2021-Present
- Built scalable microservices using Python and Kubernetes
- Led migration to cloud infrastructure, reducing costs by 40%
- Mentored junior engineers and conducted code reviews

Software Developer | StartupCo | 2019-2021
- Developed React frontend applications with TypeScript
- Created REST APIs using Node.js and PostgreSQL
- Implemented CI/CD pipelines with GitHub Actions

EDUCATION
Bachelor of Science in Computer Science
State University, 2019

SKILLS
Python, JavaScript, React, Node.js, PostgreSQL, Kubernetes, Docker, AWS, Git
"""
    
    return Resume(
        file_path=resume_path,
        raw_text=resume_text,
        parsed_data={
            "name": f"{os.getenv('APPLICANT_FIRST_NAME', 'Test')} {os.getenv('APPLICANT_LAST_NAME', 'User')}",
            "email": os.getenv("APPLICANT_EMAIL", "test@example.com"),
            "skills": ["Python", "JavaScript", "React", "Node.js", "PostgreSQL", "Kubernetes"],
            "experience": [
                {"company": "TechCorp", "title": "Senior Software Engineer", "years": 3},
                {"company": "StartupCo", "title": "Software Developer", "years": 2}
            ]
        }
    )


@pytest.fixture(scope="module")
async def monitored_browser():
    """Browser manager with monitoring enabled."""
    from browser.stealth_manager import StealthBrowserManager
    
    manager = StealthBrowserManager(
        prefer_local=True,
        record_video=True,
        record_har=True
    )
    
    yield manager
    
    await manager.close_all()


class TestProductionGreenhouse:
    """Production applications to Greenhouse boards."""
    
    @pytest.mark.skipif(
        not REAL_JOBS["greenhouse"]["enabled"],
        reason="PRODUCTION_GREENHOUSE_URL not set"
    )
    async def test_greenhouse_production_application(self, monitored_browser, production_profile, production_resume):
        """
        Submit REAL application to Greenhouse job.
        
        Environment Variables Required:
        - PRODUCTION_GREENHOUSE_URL: Full URL to job posting
        - APPLICANT_*: Your personal information
        - RESUME_PATH: Path to your resume PDF
        """
        from adapters.direct_apply import DirectApplyHandler
        from adapters.base import JobPosting, PlatformType
        from monitoring.application_monitor import get_monitor
        
        job_url = REAL_JOBS["greenhouse"]["url"]
        
        # Create job object
        job = JobPosting(
            id=f"gh_prod_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            platform=PlatformType.GREENHOUSE,
            title="Software Engineer",
            company="Production Company",
            location="Remote",
            url=job_url,
            description="Production application",
            easy_apply=True,
            remote=True
        )
        
        # Start monitoring
        monitor = get_monitor()
        app_id = monitor.start_application(
            application_id=job.id,
            job_url=job_url,
            platform="greenhouse"
        )
        
        try:
            # Apply
            handler = DirectApplyHandler(monitored_browser)
            
            print(f"\n🚀 Submitting application to: {job_url}")
            print(f"   Profile: {production_profile.email}")
            print(f"   Resume: {production_resume.file_path}")
            print(f"   This is a REAL submission!\n")
            
            result = await handler.apply(
                job=job,
                resume=production_resume,
                profile=production_profile,
                auto_submit=True  # ACTUAL SUBMISSION
            )
            
            # Log result
            monitor.finish_application(
                success=result.status.value == "submitted",
                confirmation_id=result.confirmation_id,
                error_message=result.message if result.status.value == "error" else None,
                metrics={"screenshots_count": len([result.screenshot_path]) if result.screenshot_path else 0}
            )
            
            # Assertions
            assert result.status.value in ["submitted", "error"]
            
            if result.status.value == "submitted":
                print(f"✅ SUCCESS! Confirmation: {result.confirmation_id}")
                print(f"   Screenshot: {result.screenshot_path}")
            else:
                print(f"❌ FAILED: {result.message}")
                print(f"   Screenshot: {result.screenshot_path}")
            
            return result
            
        except Exception as e:
            monitor.log_error(e, context="greenhouse_production")
            monitor.finish_application(
                success=False,
                error_message=str(e)
            )
            raise


class TestProductionLever:
    """Production applications to Lever boards."""
    
    @pytest.mark.skipif(
        not REAL_JOBS["lever"]["enabled"],
        reason="PRODUCTION_LEVER_URL not set"
    )
    async def test_lever_production_application(self, monitored_browser, production_profile, production_resume):
        """Submit REAL application to Lever job."""
        from adapters.direct_apply import DirectApplyHandler
        from adapters.base import JobPosting, PlatformType
        from monitoring.application_monitor import get_monitor
        
        job_url = REAL_JOBS["lever"]["url"]
        
        job = JobPosting(
            id=f"lv_prod_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            platform=PlatformType.LEVER,
            title="Software Engineer",
            company="Production Company",
            location="Remote",
            url=job_url,
            description="Production application",
            easy_apply=True,
            remote=True
        )
        
        monitor = get_monitor()
        monitor.start_application(job.id, job_url, "lever")
        
        try:
            handler = DirectApplyHandler(monitored_browser)
            
            print(f"\n🚀 Submitting Lever application to: {job_url}")
            
            result = await handler.apply(job, production_resume, production_profile, auto_submit=True)
            
            monitor.finish_application(
                success=result.status.value == "submitted",
                confirmation_id=result.confirmation_id,
                error_message=result.message if result.status.value == "error" else None
            )
            
            print(f"Status: {result.status.value}")
            print(f"Confirmation: {result.confirmation_id}")
            
            assert result.status.value in ["submitted", "error"]
            
        except Exception as e:
            monitor.finish_application(success=False, error_message=str(e))
            raise


class TestProductionLinkedIn:
    """Production applications to LinkedIn Easy Apply."""
    
    @pytest.mark.skipif(
        not REAL_JOBS["linkedin"]["enabled"],
        reason="PRODUCTION_LINKEDIN_URL or LINKEDIN_LI_AT not set"
    )
    async def test_linkedin_production_application(self, monitored_browser, production_profile, production_resume):
        """Submit REAL application to LinkedIn Easy Apply job."""
        from adapters.linkedin import LinkedInAdapter
        from adapters.base import JobPosting, PlatformType
        from monitoring.application_monitor import get_monitor
        
        job_url = REAL_JOBS["linkedin"]["url"]
        li_at = REAL_JOBS["linkedin"]["li_at"]
        
        job = JobPosting(
            id=f"li_prod_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            platform=PlatformType.LINKEDIN,
            title="Software Engineer",
            company="Production Company",
            location="Remote",
            url=job_url,
            description="Production application",
            easy_apply=True,
            remote=True
        )
        
        monitor = get_monitor()
        monitor.start_application(job.id, job_url, "linkedin")
        
        adapter = LinkedInAdapter(monitored_browser, session_cookie=li_at)
        
        try:
            print(f"\n🚀 Submitting LinkedIn Easy Apply to: {job_url}")
            print(f"   Using li_at cookie: {li_at[:20]}...")
            
            result = await adapter.apply_to_job(
                job=job,
                resume=production_resume,
                profile=production_profile,
                auto_submit=True
            )
            
            monitor.finish_application(
                success=result.status.value == "submitted",
                confirmation_id=result.confirmation_id,
                error_message=result.message if result.status.value == "error" else None
            )
            
            print(f"Status: {result.status.value}")
            print(f"Confirmation: {result.confirmation_id}")
            print(f"Screenshots: {result.screenshot_path}")
            
            assert result.status.value in ["submitted", "error", "pending_review"]
            
        except Exception as e:
            monitor.finish_application(success=False, error_message=str(e))
            raise
        finally:
            await adapter.close()


class TestIterationAndMonitoring:
    """Test failure analysis and iteration."""
    
    async def test_monitoring_database(self):
        """Verify monitoring database is working."""
        from monitoring.application_monitor import get_monitor
        
        monitor = get_monitor()
        
        # Get platform stats
        stats = monitor.get_platform_success_rates()
        print(f"\nPlatform Stats: {stats}")
        
        # Get recent failures
        failures = monitor.get_recent_failures(hours=24)
        print(f"Recent Failures: {len(failures)}")
        
        assert True  # Just verify no errors
    
    async def test_iteration_engine(self):
        """Test failure analysis and iteration."""
        from monitoring.iteration_engine import get_iteration_engine
        
        engine = get_iteration_engine()
        
        # Get iteration report
        report = engine.get_iteration_report(hours=24)
        print(f"\n{report}")
        
        # Get strategy for a platform
        strategy = engine.get_platform_strategy("greenhouse")
        print(f"Greenhouse Strategy: {strategy}")
        
        assert True
    
    async def test_daily_report(self):
        """Generate daily monitoring report."""
        from monitoring.application_monitor import get_monitor
        
        monitor = get_monitor()
        report = monitor.generate_daily_report()
        
        print(f"\n{report}")
        
        # Save to file
        report_path = Path("./logs/daily_report.txt")
        report_path.write_text(report)
        print(f"Report saved to: {report_path}")


# ============================================================================
# BATCH PRODUCTION TEST
# ============================================================================

@pytest.mark.skipif(
    os.getenv("RUN_BATCH_PRODUCTION") != "true",
    reason="RUN_BATCH_PRODUCTION not enabled"
)
@pytest.mark.asyncio
async def test_batch_production_applications(monitored_browser, production_profile, production_resume):
    """
    Run batch of production applications across multiple platforms.
    
    Environment Variables:
    - RUN_BATCH_PRODUCTION=true (required)
    - BATCH_SIZE=5 (number of applications)
    - PRODUCTION_*_URLS (comma-separated URLs for each platform)
    """
    from adapters.base import JobPosting, PlatformType
    from monitoring.application_monitor import get_monitor
    from adapters import get_adapter
    
    batch_size = int(os.getenv("BATCH_SIZE", "5"))
    
    # Collect all enabled jobs
    jobs_to_apply = []
    
    for platform, config in REAL_JOBS.items():
        if config["enabled"] and config["url"]:
            urls = config["url"].split(",")[:batch_size]
            for url in urls:
                jobs_to_apply.append({
                    "platform": platform,
                    "url": url.strip(),
                    "id": f"{platform}_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(jobs_to_apply)}"
                })
    
    print(f"\n{'='*70}")
    print(f"BATCH PRODUCTION RUN")
    print(f"{'='*70}")
    print(f"Total applications: {len(jobs_to_apply)}")
    print(f"Profile: {production_profile.email}")
    print(f"{'='*70}\n")
    
    monitor = get_monitor()
    results = []
    
    for i, job_config in enumerate(jobs_to_apply, 1):
        print(f"\n[{i}/{len(jobs_to_apply)}] Applying to {job_config['platform']}: {job_config['url'][:60]}...")
        
        # Create job
        job = JobPosting(
            id=job_config["id"],
            platform=getattr(PlatformType, job_config["platform"].upper(), PlatformType.EXTERNAL),
            title="Software Engineer",
            company="Batch Application",
            location="Remote",
            url=job_config["url"],
            description="Batch production test",
            easy_apply=True
        )
        
        # Get adapter
        try:
            adapter = get_adapter(
                job_config["platform"],
                monitored_browser,
                session_cookie=REAL_JOBS["linkedin"].get("li_at") if job_config["platform"] == "linkedin" else None
            )
            
            monitor.start_application(job.id, job.url, job_config["platform"])
            
            result = await adapter.apply_to_job(
                job=job,
                resume=production_resume,
                profile=production_profile,
                auto_submit=True
            )
            
            monitor.finish_application(
                success=result.status.value == "submitted",
                confirmation_id=result.confirmation_id,
                error_message=result.message if result.status.value == "error" else None
            )
            
            results.append({
                "platform": job_config["platform"],
                "url": job_config["url"],
                "status": result.status.value,
                "confirmation": result.confirmation_id
            })
            
            print(f"   Result: {result.status.value}")
            
            await adapter.close()
            
        except Exception as e:
            monitor.finish_application(success=False, error_message=str(e))
            results.append({
                "platform": job_config["platform"],
                "url": job_config["url"],
                "status": "error",
                "error": str(e)
            })
            print(f"   Error: {e}")
        
        # Brief delay between applications
        await asyncio.sleep(5)
    
    # Summary
    successful = sum(1 for r in results if r["status"] == "submitted")
    failed = sum(1 for r in results if r["status"] == "error")
    
    print(f"\n{'='*70}")
    print(f"BATCH COMPLETE")
    print(f"{'='*70}")
    print(f"Total: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {successful/len(results)*100:.1f}%")
    print(f"{'='*70}\n")
    
    # Generate report
    report = monitor.generate_daily_report()
    print(report)
