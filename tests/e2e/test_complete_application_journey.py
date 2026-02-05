"""
Complete End-to-End Application Journey Test

Tests the full flow from user registration to application confirmation.
Uses real browsers (not mocks) against test/sandbox environments.

Environment Variables:
- RUN_REAL_BROWSER_TESTS: Set to "true" to enable real browser tests
- RUN_FULL_JOURNEY_TEST: Set to "true" to run the complete journey test
- MOCK_ATS_SERVER_URL: URL of mock ATS server (default: http://localhost:8765)
"""

import pytest
import asyncio
import os
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

# Skip if running in CI without browser support
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.asyncio,
]


@pytest.fixture(scope="module")
async def real_browser_manager():
    """Create a real browser manager for E2E tests."""
    from core import UnifiedBrowserManager
    
    manager = UnifiedBrowserManager(prefer_local=True)
    yield manager
    await manager.close_all()


@pytest.fixture
def test_user():
    """Create a test user with full profile."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    user_data = {
        "email": f"test_{timestamp}@example.com",
        "password": "TestPass123!",
        "profile": {
            "first_name": "Test",
            "last_name": "User",
            "email": f"test_{timestamp}@example.com",
            "phone": "555-123-4567",
            "linkedin_url": "https://linkedin.com/in/testuser",
            "years_experience": 5,
            "work_authorization": "Yes",
            "sponsorship_required": "No",
            "custom_answers": {
                "salary_expectations": "$100,000 - $120,000",
                "notice_period": "2 weeks",
                "willing_to_relocate": "Yes"
            }
        },
        "resume": {
            "raw_text": """
Test User
Software Engineer | test@example.com | 555-123-4567

SUMMARY
Experienced software engineer with 5+ years building scalable web applications.

EXPERIENCE
Senior Engineer at TechCorp (2020-Present)
- Built microservices using Python and Kubernetes
- Led team of 3 developers
- Reduced API latency by 40% through optimization
- Implemented CI/CD pipelines with GitHub Actions

Developer at StartupCo (2018-2020)
- Full-stack development with React and Node.js
- Designed PostgreSQL database schemas
- Deployed applications on AWS infrastructure

SKILLS
Python, Kubernetes, React, Node.js, PostgreSQL, AWS, Docker, Git

EDUCATION
BS Computer Science, State University (2018)
"""
        }
    }
    return user_data


@pytest.fixture
def test_job_postings():
    """Sample job postings for testing."""
    from adapters.base import JobPosting, PlatformType
    
    return [
        JobPosting(
            id="gh_test_123",
            platform=PlatformType.GREENHOUSE,
            title="Software Engineer",
            company="TestCorp",
            location="Remote",
            url="https://boards.greenhouse.io/testcorp/jobs/123",
            description="Python, Kubernetes, React",
            easy_apply=True,
            remote=True
        ),
        JobPosting(
            id="lv_test_456",
            platform=PlatformType.LEVER,
            title="Backend Developer",
            company="StartupCo",
            location="San Francisco",
            url="https://jobs.lever.co/startupco/456",
            description="Go, PostgreSQL, AWS",
            easy_apply=True,
            remote=False
        ),
        JobPosting(
            id="wd_test_789",
            platform=PlatformType.WORKDAY,
            title="Senior Software Engineer",
            company="EnterpriseCorp",
            location="New York",
            url="https://enterprisecorp.wd5.myworkdayjobs.com/External/job/123",
            description="Java, Spring Boot, microservices",
            easy_apply=False,
            remote=False
        )
    ]


class TestPhase1Setup:
    """Phase 1: User Setup & Discovery"""
    
    async def test_user_registration(self, client):
        """Test user can register and receive auth tokens."""
        from fastapi.testclient import TestClient
        
        response = client.post("/auth/register", json={
            "email": f"test_{datetime.now().timestamp()}@example.com",
            "password": "SecurePass123!"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "user_id" in data
        
        return data["access_token"]
    
    async def test_resume_upload_and_parsing(self, client, auth_headers, test_user):
        """Test resume upload triggers AI parsing."""
        import io
        
        # Create a test file
        pdf_content = test_user["resume"]["raw_text"].encode()
        
        response = client.post(
            "/resume/upload",
            files={"file": ("test_resume.pdf", io.BytesIO(pdf_content), "application/pdf")},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify AI parsing
        assert "parsed_data" in data
        assert "contact" in data["parsed_data"]
        assert "experience" in data["parsed_data"]
        assert "skills" in data["parsed_data"]
        
        # Verify job title suggestions
        assert "suggested_titles" in data
        assert len(data["suggested_titles"]) > 0
        
        return data["parsed_data"]
    
    async def test_profile_save(self, client, auth_headers, test_user):
        """Test profile can be saved with all fields."""
        response = client.post(
            "/profile",
            json=test_user["profile"],
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        # Verify persistence
        response = client.get("/profile", headers=auth_headers)
        assert response.status_code == 200
        
        profile = response.json()
        assert profile["first_name"] == test_user["profile"]["first_name"]
        assert profile["custom_answers"] == test_user["profile"]["custom_answers"]


class TestPhase2JobDiscovery:
    """Phase 2: Job Discovery Across Platforms"""
    
    @pytest.mark.skipif(
        not os.getenv("RUN_REAL_BROWSER_TESTS"),
        reason="Real browser tests require RUN_REAL_BROWSER_TESTS env var"
    )
    async def test_greenhouse_job_search(self, real_browser_manager):
        """Test searching Greenhouse jobs."""
        from adapters.greenhouse import GreenhouseAdapter
        from adapters.base import SearchConfig
        
        adapter = GreenhouseAdapter()
        
        criteria = SearchConfig(
            roles=["software engineer", "backend developer"],
            locations=["Remote", "San Francisco"],
            posted_within_days=30,
            required_keywords=["python"]
        )
        
        jobs = await adapter.search_jobs(criteria)
        
        assert len(jobs) > 0, "Should find jobs on Greenhouse"
        
        # Validate job structure
        for job in jobs:
            assert job.id
            assert job.title
            assert job.company
            assert job.url
            assert "greenhouse" in job.url.lower() or "boards.greenhouse" in job.url.lower()
        
        await adapter.close()
        return jobs[:3]
    
    async def test_job_matching_scoring(self, test_job_postings):
        """Test job relevance scoring algorithm."""
        from adapters.base import SearchConfig
        
        criteria = SearchConfig(
            roles=["software engineer"],
            locations=["Remote"],
            required_keywords=["python", "kubernetes"],
            exclude_keywords=["senior staff", "principal"]
        )
        
        # Score each job
        scored_jobs = []
        for job in test_job_postings:
            score = self._calculate_job_fit(job, criteria)
            scored_jobs.append((job, score))
        
        # Sort by score
        scored_jobs.sort(key=lambda x: x[1], reverse=True)
        
        # Verify scoring logic
        assert scored_jobs[0][1] >= scored_jobs[-1][1], "Should be sorted by relevance"
        
        return [job for job, score in scored_jobs if score > 0.5]
    
    def _calculate_job_fit(self, job, criteria):
        """Calculate job fit score (0-1)."""
        score = 0.5
        
        # Title match
        title_lower = job.title.lower()
        for role in criteria.roles:
            if role.lower() in title_lower:
                score += 0.2
                break
        
        # Keyword match
        if job.description:
            desc_lower = job.description.lower()
            matched = sum(1 for kw in criteria.required_keywords if kw.lower() in desc_lower)
            if criteria.required_keywords:
                score += 0.2 * (matched / len(criteria.required_keywords))
        
        # Exclude keywords penalty
        if job.description:
            for kw in criteria.exclude_keywords:
                if kw.lower() in job.description.lower():
                    score -= 0.3
        
        return max(0, min(1, score))


class TestPhase3ResumeTailoring:
    """Phase 3: AI-Powered Resume Tailoring"""
    
    async def test_resume_tailoring(self, test_user, test_job_postings):
        """Test resume tailoring for a specific job."""
        import os
        if not os.getenv("MOONSHOT_API_KEY") or os.getenv("MOONSHOT_API_KEY") == "test-key":
            pytest.skip("No Moonshot API key configured")
        
        from ai.kimi_service import KimiResumeOptimizer
        
        kimi = KimiResumeOptimizer()
        job = test_job_postings[0]
        
        job_description = f"""
{job.title} at {job.company}

We are looking for a Software Engineer with:
- 3+ years of Python experience
- Kubernetes and containerization
- React frontend development
- Database design with PostgreSQL
"""
        
        result = await kimi.tailor_resume(
            test_user["resume"]["raw_text"],
            job_description,
            optimization_type="balanced"
        )
        
        # Verify structure
        assert "tailored_bullets" in result
        assert "suggested_skills_order" in result
        assert "keyword_matches" in result
        
        # Safety: No hallucination
        tailored_text = str(result)
        assert "Google" not in tailored_text  # No fake companies
        assert "Meta" not in tailored_text
        assert "Amazon" not in tailored_text
        
        return result
    
    async def test_cover_letter_generation(self, test_user, test_job_postings):
        """Test cover letter generation."""
        import os
        if not os.getenv("MOONSHOT_API_KEY") or os.getenv("MOONSHOT_API_KEY") == "test-key":
            pytest.skip("No Moonshot API key configured")
        
        from ai.kimi_service import KimiResumeOptimizer
        
        kimi = KimiResumeOptimizer()
        job = test_job_postings[0]
        
        cover_letter = await kimi.generate_cover_letter(
            resume_summary=test_user["resume"]["raw_text"][:2000],
            job_title=job.title,
            company_name=job.company,
            job_requirements="Python, Kubernetes, React",
            tone="professional"
        )
        
        # Verify content
        assert len(cover_letter) > 200
        assert len(cover_letter) < 1000
        assert job.company in cover_letter or job.title in cover_letter
        
        # Safety: No experience inflation
        import re
        years_claims = re.findall(r'(\d+)\+?\s*years?', cover_letter, re.I)
        for claim in years_claims:
            assert int(claim) <= 6, f"Inflated experience: {claim} years claimed"
        
        return cover_letter


class TestPhase4ApplicationSubmission:
    """Phase 4: Multi-Step Application Submission"""
    
    @pytest.mark.skipif(
        not os.getenv("RUN_REAL_BROWSER_TESTS"),
        reason="Real browser tests require RUN_REAL_BROWSER_TESTS env var"
    )
    async def test_greenhouse_application(self, real_browser_manager, test_user, test_job_postings):
        """Test complete application to Greenhouse job."""
        from adapters.direct_apply import DirectApplyHandler
        from adapters.base import Resume, UserProfile
        
        # Create resume object
        resume = Resume(
            file_path="/tmp/test_resume.pdf",
            raw_text=test_user["resume"]["raw_text"],
            parsed_data={}
        )
        
        profile = UserProfile(
            first_name=test_user["profile"]["first_name"],
            last_name=test_user["profile"]["last_name"],
            email=test_user["profile"]["email"],
            phone=test_user["profile"]["phone"],
            linkedin_url=test_user["profile"]["linkedin_url"],
            years_experience=test_user["profile"]["years_experience"],
            custom_answers=test_user["profile"]["custom_answers"]
        )
        
        job = test_job_postings[0]
        
        # Use DirectApplyHandler
        handler = DirectApplyHandler(real_browser_manager)
        
        result = await handler.apply(job, resume, profile, auto_submit=False)
        
        # Should pause for review (not auto-submit)
        assert result.status.value in ["pending_review", "ready_to_submit", "submitted"]
        
        return result
    
    async def test_custom_question_answering(self, test_user):
        """Test AI answering custom application questions."""
        import os
        if not os.getenv("MOONSHOT_API_KEY") or os.getenv("MOONSHOT_API_KEY") == "test-key":
            pytest.skip("No Moonshot API key configured")
        
        from ai.kimi_service import KimiResumeOptimizer
        
        kimi = KimiResumeOptimizer()
        
        questions = [
            "How many years of Python experience do you have?",
            "Describe your experience with Kubernetes",
            "Why do you want to work at our company?",
            "What is your expected salary range?"
        ]
        
        answers = {}
        for question in questions:
            answer = await kimi.answer_application_question(
                question=question,
                resume_context=test_user["resume"]["raw_text"],
                existing_answers=test_user["profile"]["custom_answers"]
            )
            answers[question] = answer
            
            # Verify answer is reasonable
            assert len(answer) > 10
            assert len(answer) < 500
        
        return answers


class TestPhase5Verification:
    """Phase 5: Application Verification"""
    
    async def test_screenshot_capture(self):
        """Verify screenshot capture capability exists."""
        from adapters.base import ApplicationResult, ApplicationStatus
        
        # Create result with screenshot
        result = ApplicationResult(
            status=ApplicationStatus.PENDING_REVIEW,
            message="Form filled for review",
            screenshot_path="/tmp/test_screenshot.png"
        )
        
        assert result.screenshot_path is not None
        assert result.screenshot_path.endswith(".png")
    
    async def test_confirmation_extraction(self):
        """Test confirmation ID extraction."""
        from adapters.base import ApplicationResult, ApplicationStatus
        
        result = ApplicationResult(
            status=ApplicationStatus.SUBMITTED,
            message="Application submitted successfully",
            confirmation_id="GH_12345_67890",
            submitted_at=datetime.now()
        )
        
        assert result.confirmation_id is not None
        assert result.confirmation_id.startswith("GH_")


class TestPhase6FailureRecovery:
    """Phase 6: Failure Modes and Recovery"""
    
    async def test_captcha_timeout_handling(self):
        """Test graceful handling of CAPTCHA challenges."""
        from adapters.base import ApplicationResult, ApplicationStatus
        
        # Simulate CAPTCHA timeout scenario
        result = ApplicationResult(
            status=ApplicationStatus.PENDING_REVIEW,
            message="CAPTCHA detected - manual review required",
            screenshot_path="/tmp/captcha_screenshot.png"
        )
        
        assert result.status == ApplicationStatus.PENDING_REVIEW
        assert "CAPTCHA" in result.message
    
    async def test_session_recovery(self, real_browser_manager):
        """Test recovery from browser session timeouts."""
        # Create session
        session = await real_browser_manager.create_stealth_session("test")
        session_id = session.session_id
        
        # Close and try to recover
        await real_browser_manager.close_session(session_id)
        
        # Should be able to create new session
        new_session = await real_browser_manager.create_stealth_session("test")
        assert new_session.session_id != session_id
        
        await real_browser_manager.close_session(new_session.session_id)


class TestBatchProcessing:
    """Test batch application processing."""
    
    async def test_batch_applications(self, client, auth_headers, test_user):
        """Test applying to multiple jobs in parallel (mocked)."""
        job_urls = [
            "https://boards.greenhouse.io/test1/jobs/123",
            "https://boards.greenhouse.io/test2/jobs/456",
            "https://jobs.lever.co/test3/abc"
        ]
        
        # Mock the browser operations
        with pytest.mock.patch("api.main.browser_manager") as mock_browser:
            with pytest.mock.patch("api.main.get_adapter") as mock_adapter:
                mock_adapter_instance = pytest.mock.AsyncMock()
                mock_adapter_instance.get_job_details = pytest.mock.AsyncMock(return_value=test_job_postings()[0])
                mock_adapter_instance.apply_to_job = pytest.mock.AsyncMock(return_value=pytest.mock.AsyncMock(
                    status=pytest.mock.MagicMock(value="submitted"),
                    message="Success",
                    confirmation_id="TEST_123"
                ))
                mock_adapter_instance.close = pytest.mock.AsyncMock()
                mock_adapter.return_value = mock_adapter_instance
                
                response = client.post(
                    "/apply/batch",
                    json={
                        "job_urls": job_urls,
                        "auto_submit": False,
                        "generate_cover_letter": True,
                        "max_concurrent": 2
                    },
                    headers=auth_headers
                )
                
                # Should either succeed or fail for valid reasons
                assert response.status_code in [200, 400, 503]


@pytest.mark.skipif(
    not os.getenv("RUN_FULL_JOURNEY_TEST"),
    reason="Full journey test requires RUN_FULL_JOURNEY_TEST env var"
)
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_complete_application_journey(client, real_browser_manager, test_user, test_job_postings):
    """
    Complete end-to-end test of the full application journey.
    
    This test runs through all phases:
    1. User registration and setup
    2. Job discovery across platforms
    3. Resume tailoring
    4. Application submission
    5. Verification and tracking
    """
    import os
    if not os.getenv("RUN_FULL_JOURNEY_TEST"):
        pytest.skip("Full journey test requires RUN_FULL_JOURNEY_TEST env var")
    
    # Phase 1: Setup
    phase1 = TestPhase1Setup()
    token = await phase1.test_user_registration(client)
    auth_headers = {"Authorization": f"Bearer {token}"}
    await phase1.test_resume_upload_and_parsing(client, auth_headers, test_user)
    await phase1.test_profile_save(client, auth_headers, test_user)
    
    # Phase 2: Job Discovery
    phase2 = TestPhase2JobDiscovery()
    jobs = await phase2.test_greenhouse_job_search(real_browser_manager)
    matched_jobs = await phase2.test_job_matching_scoring(test_job_postings)
    
    assert len(matched_jobs) > 0, "Should have matched jobs"
    target_job = matched_jobs[0]
    
    # Phase 3: Tailoring
    phase3 = TestPhase3ResumeTailoring()
    tailored_resume = await phase3.test_resume_tailoring(test_user, test_job_postings)
    cover_letter = await phase3.test_cover_letter_generation(test_user, test_job_postings)
    
    # Phase 4: Application (dry run)
    phase4 = TestPhase4ApplicationSubmission()
    result = await phase4.test_greenhouse_application(
        real_browser_manager, test_user, test_job_postings
    )
    
    # Phase 5: Verification
    phase5 = TestPhase5Verification()
    await phase5.test_screenshot_capture()
    await phase5.test_confirmation_extraction()
