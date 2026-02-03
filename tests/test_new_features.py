"""
Tests for new features:
1. Job title suggestions from resume
2. API key security verification
3. Internal testing mode
"""
import pytest
import os
from unittest.mock import AsyncMock, patch, MagicMock

# Test 1: API Key Security
class TestAPIKeySecurity:
    """Verify API keys are not exposed in code."""
    
    def test_no_hardcoded_moonshot_key(self):
        """Ensure MOONSHOT_API_KEY is loaded from env only."""
        # Read the main API file
        with open("api/main.py", "r") as f:
            content = f.read()
        
        # Check no hardcoded key pattern (sk-xxx or actual key values)
        import re
        # Look for sk- prefix which is common for API keys
        matches = re.findall(r'sk-[a-zA-Z0-9]{20,}', content)
        assert len(matches) == 0, f"Found potential hardcoded API key: {matches}"
        
        # Check it's using env vars
        assert "os.environ.get" in content or "os.getenv" in content, \
            "API key should be loaded from environment variables"
    
    def test_no_hardcoded_browserbase_key(self):
        """Ensure BROWSERBASE_API_KEY is loaded from env only."""
        with open("api/main.py", "r") as f:
            content = f.read()
        
        with open("browser/stealth_manager.py", "r") as f:
            stealth_content = f.read()
        
        # Check for bb_ prefix which is BrowserBase key format
        import re
        matches = re.findall(r'bb_(live|test)_[a-zA-Z0-9]{20,}', content + stealth_content)
        assert len(matches) == 0, f"Found potential hardcoded BrowserBase key: {matches}"


# Test 2: Job Title Suggestion
class TestJobTitleSuggestion:
    """Test job title suggestion feature."""
    
    @pytest.fixture
    def sample_resume_text(self):
        return """
        MATT EDWARDS
        Customer Success Manager | matt@example.com | Seattle, WA
        
        EXPERIENCE
        Senior Customer Success Manager at AWS (2019-Present)
        - Managed $50M portfolio of enterprise cloud customers
        - Achieved 95% retention rate through proactive engagement
        - Led migration of 200+ customers to new cloud platforms
        
        Cloud Solutions Consultant at TechCorp (2016-2019)
        - Implemented AWS infrastructure for Fortune 500 clients
        - Provided technical guidance on cloud architecture
        - Trained 50+ customers on cloud best practices
        
        SKILLS
        AWS, Cloud Computing, Customer Success, Account Management,
        Enterprise Sales, Technical Consulting, Project Management
        
        CERTIFICATIONS
        AWS Solutions Architect, Cloud Practitioner
        """
    
    @pytest.mark.asyncio
    async def test_suggest_job_titles(self, sample_resume_text):
        """Test job title suggestion returns relevant titles."""
        from ai.kimi_service import KimiResumeOptimizer
        
        kimi = KimiResumeOptimizer()
        
        # Mock the API response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '''[
            {
                "title": "Customer Success Manager",
                "relevance_score": 95,
                "reason": "Direct experience in CSM role at AWS",
                "experience_level": "senior",
                "keywords": ["customer success", "account management"]
            },
            {
                "title": "Cloud Solutions Architect",
                "relevance_score": 85,
                "reason": "AWS certification and cloud experience",
                "experience_level": "senior",
                "keywords": ["aws", "cloud", "architecture"]
            }
        ]'''
        
        with patch.object(kimi, '_chat_completion', return_value=mock_response):
            result = await kimi.suggest_job_titles(sample_resume_text, count=5)
        
        assert isinstance(result, list)
        assert len(result) > 0
        assert "title" in result[0]
        assert "relevance_score" in result[0]
        
        # Check that Customer Success Manager is suggested
        titles = [r["title"].lower() for r in result]
        assert any("customer success" in t for t in titles)
    
    @pytest.mark.asyncio
    async def test_suggest_job_search_config(self, sample_resume_text):
        """Test complete search config generation."""
        from ai.kimi_service import KimiResumeOptimizer
        
        kimi = KimiResumeOptimizer()
        
        # Mock responses
        mock_title_response = MagicMock()
        mock_title_response.choices = [MagicMock()]
        mock_title_response.choices[0].message.content = '''[
            {"title": "Customer Success Manager", "relevance_score": 95, 
             "reason": "Experience", "experience_level": "senior", "keywords": ["csm"]}
        ]'''
        
        mock_parse_response = MagicMock()
        mock_parse_response.choices = [MagicMock()]
        mock_parse_response.choices[0].message.content = '''{
            "contact": {"name": "Matt Edwards"},
            "skills": ["AWS", "Customer Success"],
            "experience": [{"dates": "2019-Present"}]
        }'''
        
        with patch.object(kimi, '_chat_completion', side_effect=[
            mock_title_response, mock_parse_response
        ]):
            config = await kimi.suggest_job_search_config(sample_resume_text)
        
        assert "suggested_roles" in config
        assert "experience_level" in config
        assert "salary_range" in config
        assert isinstance(config["suggested_roles"], list)


# Test 3: Internal Testing Mode
class TestInternalTestingMode:
    """Test internal testing features."""
    
    def test_test_jobs_folder_exists(self):
        """Ensure test jobs folder is defined."""
        from api.main import TEST_JOBS_FOLDER
        assert TEST_JOBS_FOLDER is not None
    
    def test_test_request_models(self):
        """Test request models for testing endpoints."""
        from api.main import TestApplicationRequest, TestCampaignResponse
        
        # Valid request
        request = TestApplicationRequest(
            job_folder_path="/data/test_jobs/sample",
            auto_submit=False,
            log_activity=True
        )
        assert request.job_folder_path == "/data/test_jobs/sample"
        assert request.auto_submit is False
        
        # Response model
        result = TestCampaignResponse(
            test_id="test_20240101_120000",
            folder_path="/data/test_jobs/sample",
            total_jobs=5,
            processed=5,
            successful=4,
            failed=1,
            results=[],
            summary="Test complete"
        )
        assert result.test_id == "test_20240101_120000"


# Test 4: User Activity Logging
class TestUserActivityLogging:
    """Test user activity logging features."""
    
    @pytest.mark.asyncio
    async def test_log_user_activity(self):
        """Test activity logging function."""
        from api.main import _log_user_activity, activity_log
        
        initial_count = len(activity_log)
        
        await _log_user_activity(
            user_id="user_123",
            action="TEST_ACTION",
            details={"key": "value"}
        )
        
        # Check activity was logged
        assert len(activity_log) > initial_count
        assert activity_log[0]["user_id"] == "user_123"
        assert activity_log[0]["action"] == "TEST_ACTION"


# Test 5: Endpoint Availability
class TestEndpointAvailability:
    """Test that new endpoints are registered."""
    
    def test_title_suggestion_endpoint(self):
        """Test /resume/suggest-titles endpoint exists."""
        from api.main import app
        
        routes = [r.path for r in app.routes]
        assert "/resume/suggest-titles" in routes
    
    def test_testing_mode_endpoint(self):
        """Test /test/apply-folder endpoint exists."""
        from api.main import app
        
        routes = [r.path for r in app.routes]
        assert "/test/apply-folder" in routes
    
    def test_user_activity_endpoint(self):
        """Test /user/activity endpoint exists."""
        from api.main import app
        
        routes = [r.path for r in app.routes]
        assert "/user/activity" in routes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
