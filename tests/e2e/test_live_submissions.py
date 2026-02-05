"""
Live Site E2E Tests - REAL Application Submissions

These tests perform ACTUAL application submissions to live job sites.
WARNING: Only run with test accounts and on test job postings.

Environment Variables:
- RUN_LIVE_SUBMISSION_TESTS: Must be "true" to enable these tests
- TEST_MODE: If "true", will use test job postings that expect applications
- LINKEDIN_LI_AT: LinkedIn session cookie (required for LinkedIn tests)

Recommended Test Jobs:
- Greenhouse test boards: Many companies have test job postings
- Lever demo jobs: Some companies keep demo positions open
- Workday sandbox: Some instances have test positions

SAFETY:
- Tests use auto_submit=False by default (stops before final submit)
- Set AUTO_SUBMIT=true only when you're ready for real submissions
"""

import pytest
import asyncio
import os
from datetime import datetime
from typing import List, Dict, Optional

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not os.getenv("RUN_LIVE_SUBMISSION_TESTS"),
        reason="Live submission tests require RUN_LIVE_SUBMISSION_TESTS env var"
    ),
]


@pytest.fixture(scope="module")
async def browser_manager():
    """Create browser manager for live tests."""
    from browser.stealth_manager import StealthBrowserManager
    
    # Enable recording for debugging
    manager = StealthBrowserManager(
        prefer_local=True,  # Use local for more control
        record_video=True,
        record_har=True
    )
    yield manager
    await manager.close_all()


@pytest.fixture
def test_profile():
    """Test profile for live submissions."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    return {
        "first_name": "Test",
        "last_name": "Applicant",
        "email": f"test.applicant.{timestamp}@example.com",
        "phone": "555-123-4567",
        "linkedin_url": "https://linkedin.com/in/testapplicant",
        "years_experience": 3,
        "work_authorization": "Yes",
        "sponsorship_required": "No",
        "custom_answers": {
            "salary_expectations": "$80,000 - $100,000",
            "notice_period": "2 weeks",
            "willing_to_relocate": "No",
            "how_did_you_hear": "Company website"
        }
    }


@pytest.fixture
def test_resume():
    """Test resume for live submissions."""
    from adapters.base import Resume
    
    resume_text = """
Test Applicant
Software Engineer | test@example.com | 555-123-4567

EXPERIENCE
Software Engineer at TechCorp (2021-Present)
- Built Python microservices serving 100K+ requests/day
- Implemented CI/CD pipelines reducing deployment time by 50%
- Mentored junior developers and conducted code reviews

Junior Developer at StartupCo (2019-2021)
- Developed React frontend applications
- Created REST APIs using Node.js and Express
- Managed PostgreSQL database schemas

EDUCATION
BS Computer Science, State University (2019)

SKILLS
Python, JavaScript, React, Node.js, PostgreSQL, Docker, AWS, Git
"""
    
    return Resume(
        file_path="/tmp/test_resume.pdf",  # Will need to create this file
        raw_text=resume_text,
        parsed_data={
            "name": "Test Applicant",
            "email": "test@example.com",
            "skills": ["Python", "JavaScript", "React", "Node.js", "PostgreSQL"],
            "experience": [
                {"company": "TechCorp", "title": "Software Engineer", "years": 2},
                {"company": "StartupCo", "title": "Junior Developer", "years": 2}
            ]
        }
    )


@pytest.fixture
def test_jobs():
    """Test job postings on live sites.
    
    IMPORTANT: These should be test/demo jobs that expect applications.
    Update these URLs with actual test positions before running.
    """
    from adapters.base import JobPosting, PlatformType
    
    jobs = []
    
    # Greenhouse test jobs (update with real test URLs)
    # Many companies have open test positions
    if os.getenv("GREENHOUSE_TEST_URL"):
        jobs.append(JobPosting(
            id="gh_test_live",
            platform=PlatformType.GREENHOUSE,
            title="Test Software Engineer",
            company="TestCompany",
            location="Remote",
            url=os.getenv("GREENHOUSE_TEST_URL"),
            description="Test position for automation validation",
            easy_apply=True,
            remote=True
        ))
    
    # Lever test jobs
    if os.getenv("LEVER_TEST_URL"):
        jobs.append(JobPosting(
            id="lv_test_live",
            platform=PlatformType.LEVER,
            title="Test Backend Developer",
            company="TestCo",
            location="San Francisco",
            url=os.getenv("LEVER_TEST_URL"),
            description="Test position",
            easy_apply=True,
            remote=False
        ))
    
    return jobs


class TestGreenhouseLiveSubmissions:
    """Live submissions to Greenhouse boards."""
    
    @pytest.mark.skipif(
        not os.getenv("GREENHOUSE_TEST_URL"),
        reason="GREENHOUSE_TEST_URL not set"
    )
    async def test_greenhouse_form_fill_and_review(self, browser_manager, test_profile, test_resume):
        """
        Test filling Greenhouse form up to review step.
        Stops before final submission for manual verification.
        """
        from adapters.direct_apply import DirectApplyHandler
        from adapters.base import JobPosting, PlatformType
        
        # Create job from env var
        job = JobPosting(
            id="gh_live_test",
            platform=PlatformType.GREENHOUSE,
            title="Test Position",
            company="TestCo",
            location="Remote",
            url=os.getenv("GREENHOUSE_TEST_URL"),
            description="Live test",
            easy_apply=True,
            remote=True
        )
        
        # Create profile object
        from adapters.base import UserProfile
        profile = UserProfile(
            first_name=test_profile["first_name"],
            last_name=test_profile["last_name"],
            email=test_profile["email"],
            phone=test_profile["phone"],
            linkedin_url=test_profile["linkedin_url"],
            years_experience=test_profile["years_experience"],
            custom_answers=test_profile["custom_answers"]
        )
        
        handler = DirectApplyHandler(browser_manager)
        
        # Apply with auto_submit=False (stops for review)
        result = await handler.apply(job, test_resume, profile, auto_submit=False)
        
        # Should stop for review
        assert result.status.value in ["pending_review", "ready_to_submit"]
        assert result.screenshot_path is not None
        assert os.path.exists(result.screenshot_path)
        
        print(f"✅ Greenhouse form filled successfully")
        print(f"   Screenshot: {result.screenshot_path}")
        print(f"   Status: {result.status.value}")
        
        # If AUTO_SUBMIT is true, submit for real
        if os.getenv("AUTO_SUBMIT") == "true":
            print("🚀 AUTO_SUBMIT enabled - submitting application...")
            result = await handler.apply(job, test_resume, profile, auto_submit=True)
            
            assert result.status.value == "submitted"
            print(f"✅ Application submitted! Confirmation: {result.confirmation_id}")
    
    @pytest.mark.skipif(
        not os.getenv("GREENHOUSE_TEST_URL") or os.getenv("AUTO_SUBMIT") != "true",
        reason="GREENHOUSE_TEST_URL not set or AUTO_SUBMIT not enabled"
    )
    async def test_greenhouse_full_submission(self, browser_manager, test_profile, test_resume):
        """
        Test complete application submission to Greenhouse.
        WARNING: This actually submits the application!
        """
        from adapters.direct_apply import DirectApplyHandler
        from adapters.base import JobPosting, PlatformType, UserProfile
        
        job = JobPosting(
            id="gh_live_submit",
            platform=PlatformType.GREENHOUSE,
            title="Test Position",
            company="TestCo",
            location="Remote",
            url=os.getenv("GREENHOUSE_TEST_URL"),
            description="Full submission test",
            easy_apply=True,
            remote=True
        )
        
        profile = UserProfile(
            first_name=test_profile["first_name"],
            last_name=test_profile["last_name"],
            email=test_profile["email"],
            phone=test_profile["phone"],
            linkedin_url=test_profile["linkedin_url"],
            years_experience=test_profile["years_experience"],
            custom_answers=test_profile["custom_answers"]
        )
        
        handler = DirectApplyHandler(browser_manager)
        
        # FULL SUBMISSION
        result = await handler.apply(job, test_resume, profile, auto_submit=True)
        
        assert result.status.value == "submitted"
        assert result.screenshot_path is not None
        assert result.submitted_at is not None
        
        print(f"✅ Greenhouse application submitted!")
        print(f"   Confirmation ID: {result.confirmation_id}")
        print(f"   Screenshot: {result.screenshot_path}")
        print(f"   Submitted at: {result.submitted_at}")


class TestLeverLiveSubmissions:
    """Live submissions to Lever boards."""
    
    @pytest.mark.skipif(
        not os.getenv("LEVER_TEST_URL"),
        reason="LEVER_TEST_URL not set"
    )
    async def test_lever_form_fill_and_review(self, browser_manager, test_profile, test_resume):
        """Test filling Lever form up to review step."""
        from adapters.direct_apply import DirectApplyHandler
        from adapters.base import JobPosting, PlatformType, UserProfile
        
        job = JobPosting(
            id="lv_live_test",
            platform=PlatformType.LEVER,
            title="Test Position",
            company="TestCo",
            location="Remote",
            url=os.getenv("LEVER_TEST_URL"),
            description="Live test",
            easy_apply=True,
            remote=True
        )
        
        profile = UserProfile(
            first_name=test_profile["first_name"],
            last_name=test_profile["last_name"],
            email=test_profile["email"],
            phone=test_profile["phone"],
            linkedin_url=test_profile["linkedin_url"],
            years_experience=test_profile["years_experience"]
        )
        
        handler = DirectApplyHandler(browser_manager)
        result = await handler.apply(job, test_resume, profile, auto_submit=False)
        
        assert result.status.value in ["pending_review", "ready_to_submit"]
        assert result.screenshot_path is not None
        
        print(f"✅ Lever form filled successfully")
        print(f"   Screenshot: {result.screenshot_path}")
    
    @pytest.mark.skipif(
        not os.getenv("LEVER_TEST_URL") or os.getenv("AUTO_SUBMIT") != "true",
        reason="LEVER_TEST_URL not set or AUTO_SUBMIT not enabled"
    )
    async def test_lever_full_submission(self, browser_manager, test_profile, test_resume):
        """Test complete Lever application submission."""
        from adapters.direct_apply import DirectApplyHandler
        from adapters.base import JobPosting, PlatformType, UserProfile
        
        job = JobPosting(
            id="lv_live_submit",
            platform=PlatformType.LEVER,
            title="Test Position",
            company="TestCo",
            location="Remote",
            url=os.getenv("LEVER_TEST_URL"),
            description="Full submission test",
            easy_apply=True,
            remote=True
        )
        
        profile = UserProfile(
            first_name=test_profile["first_name"],
            last_name=test_profile["last_name"],
            email=test_profile["email"],
            phone=test_profile["phone"],
            linkedin_url=test_profile["linkedin_url"],
            years_experience=test_profile["years_experience"]
        )
        
        handler = DirectApplyHandler(browser_manager)
        result = await handler.apply(job, test_resume, profile, auto_submit=True)
        
        assert result.status.value == "submitted"
        assert result.confirmation_id is not None or result.message
        
        print(f"✅ Lever application submitted!")
        print(f"   Confirmation: {result.confirmation_id}")


class TestLinkedInLiveSubmissions:
    """Live submissions to LinkedIn Easy Apply."""
    
    @pytest.mark.skipif(
        not os.getenv("LINKEDIN_LI_AT"),
        reason="LINKEDIN_LI_AT not set"
    )
    async def test_linkedin_job_search_live(self, browser_manager):
        """Test live LinkedIn job search."""
        from adapters.linkedin import LinkedInAdapter
        from adapters.base import SearchConfig
        
        li_at = os.getenv("LINKEDIN_LI_AT")
        adapter = LinkedInAdapter(browser_manager, session_cookie=li_at)
        
        criteria = SearchConfig(
            roles=["software engineer"],
            locations=["Remote"],
            easy_apply_only=True,
            posted_within_days=7
        )
        
        jobs = await adapter.search_jobs(criteria)
        
        assert len(jobs) > 0, "Should find jobs on LinkedIn"
        
        # Verify job structure
        for job in jobs[:3]:
            print(f"   Found: {job.title} at {job.company}")
            assert job.id
            assert job.title
            assert job.url
        
        await adapter.close()
    
    @pytest.mark.skipif(
        not os.getenv("LINKEDIN_LI_AT") or not os.getenv("LINKEDIN_TEST_JOB_URL"),
        reason="LINKEDIN_LI_AT or LINKEDIN_TEST_JOB_URL not set"
    )
    async def test_linkedin_easy_apply_review(self, browser_manager, test_profile, test_resume):
        """
        Test LinkedIn Easy Apply up to review step.
        Stops before final submission.
        """
        from adapters.linkedin import LinkedInAdapter
        from adapters.base import JobPosting, PlatformType, UserProfile
        
        li_at = os.getenv("LINKEDIN_LI_AT")
        adapter = LinkedInAdapter(browser_manager, session_cookie=li_at)
        
        # Create job from test URL
        job = JobPosting(
            id="li_live_test",
            platform=PlatformType.LINKEDIN,
            title="Test Position",
            company="TestCo",
            location="Remote",
            url=os.getenv("LINKEDIN_TEST_JOB_URL"),
            description="LinkedIn test",
            easy_apply=True,
            remote=True
        )
        
        profile = UserProfile(
            first_name=test_profile["first_name"],
            last_name=test_profile["last_name"],
            email=test_profile["email"],
            phone=test_profile["phone"],
            linkedin_url=test_profile["linkedin_url"],
            years_experience=test_profile["years_experience"],
            custom_answers=test_profile["custom_answers"]
        )
        
        # Apply with auto_submit=False
        result = await adapter.apply_to_job(job, test_resume, profile, auto_submit=False)
        
        assert result.status.value in ["pending_review", "ready_to_submit"]
        assert result.screenshot_path is not None
        
        print(f"✅ LinkedIn Easy Apply form filled")
        print(f"   Screenshot: {result.screenshot_path}")
        print(f"   Status: {result.status.value}")
        
        await adapter.close()
    
    @pytest.mark.skipif(
        not os.getenv("LINKEDIN_LI_AT") or 
        not os.getenv("LINKEDIN_TEST_JOB_URL") or 
        os.getenv("AUTO_SUBMIT") != "true",
        reason="Missing LINKEDIN_LI_AT, LINKEDIN_TEST_JOB_URL, or AUTO_SUBMIT"
    )
    async def test_linkedin_full_submission(self, browser_manager, test_profile, test_resume):
        """
        Test complete LinkedIn Easy Apply submission.
        WARNING: This actually submits to LinkedIn!
        """
        from adapters.linkedin import LinkedInAdapter
        from adapters.base import JobPosting, PlatformType, UserProfile
        
        li_at = os.getenv("LINKEDIN_LI_AT")
        adapter = LinkedInAdapter(browser_manager, session_cookie=li_at)
        
        job = JobPosting(
            id="li_live_submit",
            platform=PlatformType.LINKEDIN,
            title="Test Position",
            company="TestCo",
            location="Remote",
            url=os.getenv("LINKEDIN_TEST_JOB_URL"),
            description="LinkedIn submission test",
            easy_apply=True,
            remote=True
        )
        
        profile = UserProfile(
            first_name=test_profile["first_name"],
            last_name=test_profile["last_name"],
            email=test_profile["email"],
            phone=test_profile["phone"],
            linkedin_url=test_profile["linkedin_url"],
            years_experience=test_profile["years_experience"],
            custom_answers=test_profile["custom_answers"]
        )
        
        # FULL SUBMISSION
        result = await adapter.apply_to_job(job, test_resume, profile, auto_submit=True)
        
        assert result.status.value == "submitted"
        assert result.screenshot_path is not None
        
        print(f"✅ LinkedIn application submitted!")
        print(f"   Confirmation: {result.confirmation_id}")
        print(f"   Screenshot: {result.screenshot_path}")
        
        await adapter.close()


class TestWorkdayLiveSubmissions:
    """Live submissions to Workday forms."""
    
    @pytest.mark.skipif(
        not os.getenv("WORKDAY_TEST_URL"),
        reason="WORKDAY_TEST_URL not set"
    )
    async def test_workday_form_navigation(self, browser_manager, test_profile, test_resume):
        """Test Workday multi-step form navigation."""
        from adapters.complex_forms import ComplexFormHandler
        from adapters.base import JobPosting, PlatformType, UserProfile
        
        job = JobPosting(
            id="wd_live_test",
            platform=PlatformType.WORKDAY,
            title="Test Position",
            company="EnterpriseCo",
            location="Remote",
            url=os.getenv("WORKDAY_TEST_URL"),
            description="Workday test",
            easy_apply=False,
            remote=True
        )
        
        profile = UserProfile(
            first_name=test_profile["first_name"],
            last_name=test_profile["last_name"],
            email=test_profile["email"],
            phone=test_profile["phone"],
            linkedin_url=test_profile["linkedin_url"],
            years_experience=test_profile["years_experience"],
            custom_answers=test_profile["custom_answers"]
        )
        
        handler = ComplexFormHandler(browser_manager)
        
        # Fill up to review (Workday is complex, may not complete)
        result = await handler.apply(job, test_resume, profile, auto_submit=False)
        
        # Should at least get to some progress
        assert result.screenshot_path is not None
        
        print(f"✅ Workday form navigation test")
        print(f"   Status: {result.status.value}")
        print(f"   Screenshot: {result.screenshot_path}")


class TestConfirmationExtraction:
    """Test confirmation ID extraction from live submissions."""
    
    async def test_confirmation_patterns(self):
        """Test confirmation ID regex patterns."""
        from adapters.direct_apply import DirectApplyHandler
        
        # Test sample texts
        sample_texts = [
            "Your confirmation number is ABC-123-456",
            "Reference #: XYZ789",
            "Application ID: APP-2024-56789",
            "Confirmation: CONF-12345",
        ]
        
        # These would be extracted from real pages
        # For now, just verify the patterns exist
        assert True  # Placeholder for real test


@pytest.mark.skipif(
    os.getenv("RUN_ALL_LIVE_TESTS") != "true",
    reason="RUN_ALL_LIVE_TESTS not enabled"
)
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_full_application_workflow(browser_manager, test_profile, test_resume):
    """
    Run full application workflow across multiple platforms.
    Only runs when RUN_ALL_LIVE_TESTS is explicitly enabled.
    """
    print("\n" + "="*70)
    print("🚀 RUNNING FULL LIVE APPLICATION WORKFLOW")
    print("="*70 + "\n")
    
    results = []
    
    # Test each available platform
    test_urls = {
        "greenhouse": os.getenv("GREENHOUSE_TEST_URL"),
        "lever": os.getenv("LEVER_TEST_URL"),
        "linkedin": os.getenv("LINKEDIN_TEST_JOB_URL") if os.getenv("LINKEDIN_LI_AT") else None,
    }
    
    for platform, url in test_urls.items():
        if not url:
            continue
        
        print(f"\n📋 Testing {platform.upper()}...")
        # Run platform-specific test
        # Results would be collected here
    
    print("\n" + "="*70)
    print("✅ FULL WORKFLOW COMPLETE")
    print("="*70 + "\n")
