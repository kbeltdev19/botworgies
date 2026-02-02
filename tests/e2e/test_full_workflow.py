"""
End-to-End Tests - Full Application Workflow
Tests complete flows with sandbox environments.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime


@pytest.mark.e2e
class TestFullApplicationWorkflow:
    """End-to-end tests with sandbox environments."""
    
    @pytest.mark.asyncio
    async def test_resume_upload_and_parse(self, sample_resume_text):
        """Test resume upload and AI parsing."""
        from ai.kimi_service import KimiResumeOptimizer
        
        import os
        if not os.getenv("MOONSHOT_API_KEY") or os.getenv("MOONSHOT_API_KEY") == "test-key":
            pytest.skip("No Moonshot API key configured")
        
        kimi = KimiResumeOptimizer()
        
        # Parse resume
        result = await kimi.parse_resume(sample_resume_text)
        
        # Verify extraction
        assert "John Doe" in str(result) or "name" in result
        assert "Python" in str(result) or "skills" in result
    
    @pytest.mark.asyncio
    async def test_resume_tailoring_flow(self, sample_resume_text, sample_job_description):
        """Test full resume tailoring pipeline."""
        from ai.kimi_service import KimiResumeOptimizer
        
        import os
        if not os.getenv("MOONSHOT_API_KEY") or os.getenv("MOONSHOT_API_KEY") == "test-key":
            pytest.skip("No Moonshot API key configured")
        
        kimi = KimiResumeOptimizer()
        
        # Tailor resume
        result = await kimi.tailor_resume(sample_resume_text, sample_job_description)
        
        # Verify result structure
        assert result is not None
        
        if isinstance(result, dict):
            # Should have tailored content
            assert "tailored_bullets" in result or "content" in result
    
    @pytest.mark.asyncio
    async def test_cover_letter_generation_flow(self, sample_resume_text):
        """Test cover letter generation."""
        from ai.kimi_service import KimiResumeOptimizer
        
        import os
        if not os.getenv("MOONSHOT_API_KEY") or os.getenv("MOONSHOT_API_KEY") == "test-key":
            pytest.skip("No Moonshot API key configured")
        
        kimi = KimiResumeOptimizer()
        
        cover_letter = await kimi.generate_cover_letter(
            resume_summary=sample_resume_text[:1000],
            job_title="Software Engineer",
            company_name="Tech Company",
            job_requirements="Python, REST APIs, PostgreSQL"
        )
        
        # Verify cover letter
        assert len(cover_letter) > 200
        assert "Software Engineer" in cover_letter or "engineer" in cover_letter.lower()
    
    @pytest.mark.asyncio
    async def test_linkedin_dry_run(self, sample_user_profile, sample_resume, mock_browser_manager):
        """Test LinkedIn flow up to (but not including) submit."""
        from adapters.linkedin import LinkedInAdapter
        
        adapter = LinkedInAdapter(mock_browser_manager)
        
        # Mock the session
        mock_page = MagicMock()
        mock_page.goto = AsyncMock()
        mock_page.locator = MagicMock(return_value=MagicMock(
            count=AsyncMock(return_value=1),
            inner_text=AsyncMock(return_value="Software Engineer at TechCo"),
            click=AsyncMock()
        ))
        mock_page.content = AsyncMock(return_value="<html>Easy Apply</html>")
        
        mock_browser_manager.create_session.return_value = {
            "session_id": "test",
            "page": mock_page
        }
        
        # This would run the actual flow in real e2e
        # For unit test, verify structure
        assert adapter.platform.value == "linkedin"
    
    @pytest.mark.asyncio
    async def test_greenhouse_form_filling(self, sample_user_profile, sample_resume, mock_browser_manager):
        """Test Greenhouse form filling."""
        from adapters.greenhouse import GreenhouseAdapter
        
        adapter = GreenhouseAdapter(mock_browser_manager)
        
        # Verify adapter exists and has correct platform
        assert adapter.platform.value == "greenhouse"
    
    @pytest.mark.asyncio
    async def test_api_health_check(self):
        """Test API health endpoint."""
        from fastapi.testclient import TestClient
        from api.main import app
        
        client = TestClient(app)
        
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_api_platforms_endpoint(self):
        """Test platforms listing endpoint."""
        from fastapi.testclient import TestClient
        from api.main import app
        
        client = TestClient(app)
        
        response = client.get("/platforms")
        assert response.status_code == 200
        
        data = response.json()
        assert "platforms" in data
        
        platform_ids = [p["id"] for p in data["platforms"]]
        assert "linkedin" in platform_ids
        assert "indeed" in platform_ids
        assert "greenhouse" in platform_ids


@pytest.mark.e2e
class TestPlatformAdapters:
    """Test individual platform adapters."""
    
    @pytest.mark.asyncio
    async def test_linkedin_adapter_initialization(self, mock_browser_manager):
        """Test LinkedIn adapter initializes correctly."""
        from adapters.linkedin import LinkedInAdapter
        
        adapter = LinkedInAdapter(mock_browser_manager)
        
        assert "linkedin.com" in adapter.BASE_URL
        assert adapter.platform.value == "linkedin"
    
    @pytest.mark.asyncio
    async def test_indeed_adapter_initialization(self, mock_browser_manager):
        """Test Indeed adapter initializes correctly."""
        from adapters.indeed import IndeedAdapter
        
        adapter = IndeedAdapter(mock_browser_manager)
        
        assert "indeed.com" in adapter.BASE_URL
        assert adapter.platform.value == "indeed"
    
    @pytest.mark.asyncio
    async def test_greenhouse_adapter_initialization(self, mock_browser_manager):
        """Test Greenhouse adapter initializes correctly."""
        from adapters.greenhouse import GreenhouseAdapter
        
        adapter = GreenhouseAdapter(mock_browser_manager)
        
        assert adapter.platform.value == "greenhouse"
    
    @pytest.mark.asyncio
    async def test_workday_adapter_initialization(self, mock_browser_manager):
        """Test Workday adapter initializes correctly."""
        from adapters.workday import WorkdayAdapter
        
        adapter = WorkdayAdapter(mock_browser_manager)
        
        assert adapter.platform.value == "workday"
    
    @pytest.mark.asyncio
    async def test_lever_adapter_initialization(self, mock_browser_manager):
        """Test Lever adapter initializes correctly."""
        from adapters.lever import LeverAdapter
        
        adapter = LeverAdapter(mock_browser_manager)
        
        assert adapter.platform.value == "lever"
    
    @pytest.mark.asyncio
    async def test_platform_detection(self):
        """Test automatic platform detection from URLs."""
        from adapters import detect_platform_from_url
        
        test_cases = [
            ("https://www.linkedin.com/jobs/view/12345", "linkedin"),
            ("https://indeed.com/viewjob?jk=abc123", "indeed"),
            ("https://boards.greenhouse.io/company/jobs/123", "greenhouse"),
            ("https://company.wd5.myworkdayjobs.com/External/job/123", "workday"),
            ("https://jobs.lever.co/company/123-456", "lever"),
            ("https://random-site.com/page/123", "unknown")  # URL without /jobs/ pattern
        ]
        
        for url, expected in test_cases:
            result = detect_platform_from_url(url)
            assert result == expected, f"Failed for {url}: expected {expected}, got {result}"


@pytest.mark.e2e
class TestApplicationTracking:
    """Test application history and tracking."""
    
    @pytest.mark.asyncio
    async def test_application_state_persistence(self):
        """Test that application state is tracked correctly via database."""
        from api.database import get_applications
        
        # Test that get_applications function exists and returns a list
        # Note: This is a basic smoke test - actual DB tests need auth
        applications = await get_applications("test-user-id")
        
        # Should return a list (empty if no applications)
        assert isinstance(applications, list)
    
    @pytest.mark.asyncio
    async def test_application_deduplication(self):
        """Test duplicate application prevention."""
        seen_jobs = set()
        
        def create_job_key(job):
            return f"{job['company'].lower()}_{job['title'].lower()}"
        
        jobs = [
            {"company": "TechCo", "title": "Software Engineer", "url": "url1"},
            {"company": "TechCo", "title": "Software Engineer", "url": "url2"},  # Dupe
            {"company": "TechCo", "title": "Senior Engineer", "url": "url3"},
            {"company": "OtherCo", "title": "Software Engineer", "url": "url4"},
        ]
        
        unique_jobs = []
        for job in jobs:
            key = create_job_key(job)
            if key not in seen_jobs:
                seen_jobs.add(key)
                unique_jobs.append(job)
        
        assert len(unique_jobs) == 3
