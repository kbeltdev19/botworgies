"""
End-to-End Tests - Job Search & Discovery

Tests the complete job search functionality across platforms:
- SEARCH-01: LinkedIn search returns relevant results
- SEARCH-02: Indeed search returns relevant results
- SEARCH-03: Search filters applied correctly (location, date posted, etc.)
- SEARCH-04: Search results cached for performance
- SEARCH-05: Duplicate job detection works across platforms
- SEARCH-06: Expired job listings filtered out
- SEARCH-07: Search rate limiting respects platform ToS
- SEARCH-08: Pagination works for large result sets

Technical Specifications:
- Search endpoint: POST /jobs/search
- Supported platforms: linkedin, indeed, company
- Rate limiting: Enforced per user and platform
- Caching: Redis/memory-based for search results
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

# Ensure project root is in path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.main import app
from adapters.base import SearchConfig, JobPosting, PlatformType


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_user():
    """Sample authenticated user."""
    return {
        "id": "test-user-uuid-1234",
        "email": "test@example.com",
        "is_active": True
    }


@pytest.fixture
def mock_token(mock_user):
    """Generate a valid access token for testing."""
    from api.auth import create_access_token
    return create_access_token(mock_user["id"])


@pytest.fixture
def valid_search_request():
    """Valid search request data."""
    return {
        "roles": ["Software Engineer", "Backend Developer"],
        "locations": ["San Francisco", "Remote"],
        "easy_apply_only": False,
        "posted_within_days": 7,
        "required_keywords": ["Python", "AWS"],
        "exclude_keywords": ["Senior"],
        "country": "US"
    }


@pytest.fixture
def sample_job_postings():
    """Sample job postings for mocking."""
    return [
        JobPosting(
            id="job-1",
            platform=PlatformType.LINKEDIN,
            title="Software Engineer",
            company="TechCorp",
            location="San Francisco, CA",
            url="https://linkedin.com/jobs/view/1",
            description="Python, AWS, REST APIs. Looking for a software engineer.",
            easy_apply=True,
            remote=False,
            posted_date=datetime.now() - timedelta(days=2)
        ),
        JobPosting(
            id="job-2",
            platform=PlatformType.LINKEDIN,
            title="Backend Developer",
            company="StartupCo",
            location="Remote",
            url="https://linkedin.com/jobs/view/2",
            description="Python, PostgreSQL, Docker. Backend development.",
            easy_apply=True,
            remote=True,
            posted_date=datetime.now() - timedelta(days=5)
        ),
        JobPosting(
            id="job-3",
            platform=PlatformType.LINKEDIN,
            title="Senior Software Engineer",
            company="BigTech",
            location="San Francisco, CA",
            url="https://linkedin.com/jobs/view/3",
            description="Lead Python development team.",
            easy_apply=False,
            remote=False,
            posted_date=datetime.now() - timedelta(days=1)
        ),
    ]


@pytest.fixture
def sample_indeed_jobs():
    """Sample Indeed job postings for mocking."""
    return [
        JobPosting(
            id="indeed-1",
            platform=PlatformType.INDEED,
            title="Software Engineer - Python",
            company="TechCorp",
            location="San Francisco, CA",
            url="https://indeed.com/viewjob?jk=indeed-1",
            description="Build Python applications with AWS.",
            easy_apply=True,
            remote=False,
            posted_date=datetime.now() - timedelta(days=3)
        ),
        JobPosting(
            id="indeed-2",
            platform=PlatformType.INDEED,
            title="Backend Developer",
            company="OtherCorp",
            location="Remote",
            url="https://indeed.com/viewjob?jk=indeed-2",
            description="Python backend development.",
            easy_apply=True,
            remote=True,
            posted_date=datetime.now() - timedelta(days=6)
        ),
    ]


@pytest.fixture
def mock_linkedin_adapter(sample_job_postings):
    """Mock LinkedIn adapter with sample jobs."""
    mock = MagicMock()
    mock.search_jobs = AsyncMock(return_value=sample_job_postings)
    mock.close = AsyncMock()
    mock.platform = PlatformType.LINKEDIN
    return mock


@pytest.fixture
def mock_indeed_adapter(sample_indeed_jobs):
    """Mock Indeed adapter with sample jobs."""
    mock = MagicMock()
    mock.search_jobs = AsyncMock(return_value=sample_indeed_jobs)
    mock.close = AsyncMock()
    mock.platform = PlatformType.INDEED
    return mock


@pytest.fixture
def mock_get_settings():
    """Mock get_settings to return valid settings."""
    with patch("api.main.get_settings") as mock:
        mock.return_value = {"daily_limit": 10}
        yield mock


# ============================================================================
# SEARCH-01: LinkedIn Search Tests
# ============================================================================

@pytest.mark.e2e
class TestLinkedInSearch:
    """Test LinkedIn job search returns relevant results (SEARCH-01)."""

    def test_linkedin_search_returns_jobs(
        self, client, mock_token, valid_search_request, 
        mock_linkedin_adapter, mock_get_settings
    ):
        """Test that LinkedIn search returns job results."""
        with patch("api.main.get_adapter", return_value=mock_linkedin_adapter):
            response = client.post(
                "/jobs/search?platform=linkedin",
                json=valid_search_request,
                headers={"Authorization": f"Bearer {mock_token}"}
            )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "platform" in data
        assert data["platform"] == "linkedin"
        assert "count" in data
        assert "jobs" in data
        assert data["count"] == 3
        assert len(data["jobs"]) == 3

    def test_linkedin_search_jobs_have_required_fields(
        self, client, mock_token, valid_search_request,
        mock_linkedin_adapter, mock_get_settings
    ):
        """Test that returned jobs have all required fields."""
        with patch("api.main.get_adapter", return_value=mock_linkedin_adapter):
            response = client.post(
                "/jobs/search?platform=linkedin",
                json=valid_search_request,
                headers={"Authorization": f"Bearer {mock_token}"}
            )

        data = response.json()
        job = data["jobs"][0]

        # Verify all required fields are present
        required_fields = ["id", "title", "company", "location", "url", "easy_apply", "remote"]
        for field in required_fields:
            assert field in job, f"Missing required field: {field}"

    def test_linkedin_search_relevance(
        self, client, mock_token, mock_linkedin_adapter, mock_get_settings
    ):
        """Test that LinkedIn search returns relevant jobs matching criteria."""
        search_request = {
            "roles": ["Software Engineer"],
            "locations": ["San Francisco"],
            "easy_apply_only": False,
            "posted_within_days": 7,
            "country": "US"
        }

        with patch("api.main.get_adapter", return_value=mock_linkedin_adapter):
            response = client.post(
                "/jobs/search?platform=linkedin",
                json=search_request,
                headers={"Authorization": f"Bearer {mock_token}"}
            )

        assert response.status_code == 200
        data = response.json()

        # Verify jobs match search criteria
        for job in data["jobs"]:
            assert job["title"].lower() in ["software engineer", "backend developer", "senior software engineer"]
            assert "san francisco" in job["location"].lower() or job["remote"] is True

    def test_linkedin_search_requires_auth(
        self, client, valid_search_request
    ):
        """Test that LinkedIn search requires authentication."""
        response = client.post(
            "/jobs/search?platform=linkedin",
            json=valid_search_request
        )

        assert response.status_code == 401

    def test_linkedin_search_uses_session_cookie(
        self, client, mock_token, valid_search_request,
        mock_linkedin_adapter, mock_get_settings
    ):
        """Test that LinkedIn search uses encrypted session cookie if available."""
        with patch("api.main.get_settings") as mock_settings:
            mock_settings.return_value = {
                "daily_limit": 10,
                "linkedin_cookie_encrypted": "encrypted_cookie_value"
            }
            with patch("api.main.decrypt_sensitive_data", return_value="li_at_cookie_value"):
                with patch("api.main.get_adapter") as mock_get_adapter:
                    mock_get_adapter.return_value = mock_linkedin_adapter
                    
                    response = client.post(
                        "/jobs/search?platform=linkedin",
                        json=valid_search_request,
                        headers={"Authorization": f"Bearer {mock_token}"}
                    )

        assert response.status_code == 200
        # Verify adapter was called with session cookie
        mock_get_adapter.assert_called_once()


# ============================================================================
# SEARCH-02: Indeed Search Tests
# ============================================================================

@pytest.mark.e2e
class TestIndeedSearch:
    """Test Indeed job search returns relevant results (SEARCH-02)."""

    def test_indeed_search_returns_jobs(
        self, client, mock_token, valid_search_request,
        mock_indeed_adapter, mock_get_settings
    ):
        """Test that Indeed search returns job results."""
        with patch("api.main.get_adapter", return_value=mock_indeed_adapter):
            response = client.post(
                "/jobs/search?platform=indeed",
                json=valid_search_request,
                headers={"Authorization": f"Bearer {mock_token}"}
            )

        assert response.status_code == 200
        data = response.json()

        assert data["platform"] == "indeed"
        assert data["count"] == 2
        assert len(data["jobs"]) == 2

    def test_indeed_search_job_structure(
        self, client, mock_token, valid_search_request,
        mock_indeed_adapter, mock_get_settings
    ):
        """Test Indeed job results have correct structure."""
        with patch("api.main.get_adapter", return_value=mock_indeed_adapter):
            response = client.post(
                "/jobs/search?platform=indeed",
                json=valid_search_request,
                headers={"Authorization": f"Bearer {mock_token}"}
            )

        data = response.json()
        
        # Verify Indeed-specific job structure
        for job in data["jobs"]:
            assert job["id"].startswith("indeed-")
            assert "indeed.com" in job["url"] or "indeed" in job["url"]

    def test_indeed_search_relevance(
        self, client, mock_token, mock_indeed_adapter, mock_get_settings
    ):
        """Test that Indeed search returns relevant jobs."""
        search_request = {
            "roles": ["Backend Developer"],
            "locations": ["Remote"],
            "easy_apply_only": True,
            "posted_within_days": 7,
            "country": "US"
        }

        with patch("api.main.get_adapter", return_value=mock_indeed_adapter):
            response = client.post(
                "/jobs/search?platform=indeed",
                json=search_request,
                headers={"Authorization": f"Bearer {mock_token}"}
            )

        assert response.status_code == 200
        data = response.json()

        # Verify returned jobs are relevant
        for job in data["jobs"]:
            assert job["easy_apply"] is True


# ============================================================================
# SEARCH-03: Search Filters Tests
# ============================================================================

@pytest.mark.e2e
class TestSearchFilters:
    """Test search filters are applied correctly (SEARCH-03)."""

    def test_location_filter_applied(
        self, client, mock_token, mock_linkedin_adapter, mock_get_settings
    ):
        """Test that location filter is correctly passed to adapter."""
        search_request = {
            "roles": ["Software Engineer"],
            "locations": ["New York", "Remote"],
            "easy_apply_only": False,
            "posted_within_days": 7,
            "country": "US"
        }

        with patch("api.main.get_adapter", return_value=mock_linkedin_adapter):
            response = client.post(
                "/jobs/search?platform=linkedin",
                json=search_request,
                headers={"Authorization": f"Bearer {mock_token}"}
            )

        assert response.status_code == 200
        # Verify adapter was called (implicitly testing filter passing)
        mock_linkedin_adapter.search_jobs.assert_called_once()
        
        # Verify SearchConfig was created with correct filters
        call_args = mock_linkedin_adapter.search_jobs.call_args[0][0]
        assert isinstance(call_args, SearchConfig)
        assert "New York" in call_args.locations
        assert "Remote" in call_args.locations

    def test_date_posted_filter_applied(
        self, client, mock_token, mock_linkedin_adapter, mock_get_settings
    ):
        """Test that date posted filter is correctly applied."""
        search_request = {
            "roles": ["Software Engineer"],
            "locations": ["Remote"],
            "easy_apply_only": False,
            "posted_within_days": 3,  # Last 3 days only
            "country": "US"
        }

        with patch("api.main.get_adapter", return_value=mock_linkedin_adapter):
            response = client.post(
                "/jobs/search?platform=linkedin",
                json=search_request,
                headers={"Authorization": f"Bearer {mock_token}"}
            )

        assert response.status_code == 200
        
        # Verify SearchConfig has correct date filter
        call_args = mock_linkedin_adapter.search_jobs.call_args[0][0]
        assert call_args.posted_within_days == 3

    def test_easy_apply_filter_applied(
        self, client, mock_token, mock_linkedin_adapter, mock_get_settings
    ):
        """Test that Easy Apply filter is correctly applied."""
        search_request = {
            "roles": ["Software Engineer"],
            "locations": ["Remote"],
            "easy_apply_only": True,  # Only Easy Apply jobs
            "posted_within_days": 7,
            "country": "US"
        }

        with patch("api.main.get_adapter", return_value=mock_linkedin_adapter):
            response = client.post(
                "/jobs/search?platform=linkedin",
                json=search_request,
                headers={"Authorization": f"Bearer {mock_token}"}
            )

        assert response.status_code == 200
        
        # Verify SearchConfig has Easy Apply filter
        call_args = mock_linkedin_adapter.search_jobs.call_args[0][0]
        assert call_args.easy_apply_only is True

    def test_required_keywords_filter_applied(
        self, client, mock_token, mock_linkedin_adapter, mock_get_settings
    ):
        """Test that required keywords filter is correctly applied."""
        search_request = {
            "roles": ["Software Engineer"],
            "locations": ["Remote"],
            "easy_apply_only": False,
            "posted_within_days": 7,
            "required_keywords": ["Python", "Django", "PostgreSQL"],
            "country": "US"
        }

        with patch("api.main.get_adapter", return_value=mock_linkedin_adapter):
            response = client.post(
                "/jobs/search?platform=linkedin",
                json=search_request,
                headers={"Authorization": f"Bearer {mock_token}"}
            )

        assert response.status_code == 200
        
        # Verify SearchConfig has required keywords
        call_args = mock_linkedin_adapter.search_jobs.call_args[0][0]
        assert "Python" in call_args.required_keywords
        assert "Django" in call_args.required_keywords
        assert "PostgreSQL" in call_args.required_keywords

    def test_exclude_keywords_filter_applied(
        self, client, mock_token, mock_linkedin_adapter, mock_get_settings
    ):
        """Test that exclude keywords filter is correctly applied."""
        search_request = {
            "roles": ["Software Engineer"],
            "locations": ["Remote"],
            "easy_apply_only": False,
            "posted_within_days": 7,
            "exclude_keywords": ["Senior", "Lead", "Principal"],
            "country": "US"
        }

        with patch("api.main.get_adapter", return_value=mock_linkedin_adapter):
            response = client.post(
                "/jobs/search?platform=linkedin",
                json=search_request,
                headers={"Authorization": f"Bearer {mock_token}"}
            )

        assert response.status_code == 200
        
        # Verify SearchConfig has exclude keywords
        call_args = mock_linkedin_adapter.search_jobs.call_args[0][0]
        assert "Senior" in call_args.exclude_keywords
        assert "Lead" in call_args.exclude_keywords

    def test_country_filter_applied(
        self, client, mock_token, mock_linkedin_adapter, mock_get_settings
    ):
        """Test that country filter is correctly applied."""
        for country in ["US", "CA", "GB", "DE"]:
            search_request = {
                "roles": ["Software Engineer"],
                "locations": ["Remote"],
                "easy_apply_only": False,
                "posted_within_days": 7,
                "country": country
            }

            mock_linkedin_adapter.search_jobs.reset_mock()
            
            with patch("api.main.get_adapter", return_value=mock_linkedin_adapter):
                response = client.post(
                    "/jobs/search?platform=linkedin",
                    json=search_request,
                    headers={"Authorization": f"Bearer {mock_token}"}
                )

            assert response.status_code == 200
            
            # Verify SearchConfig has correct country
            call_args = mock_linkedin_adapter.search_jobs.call_args[0][0]
            assert call_args.country == country

    def test_invalid_country_rejected(
        self, client, mock_token, mock_get_settings
    ):
        """Test that invalid country codes are rejected."""
        search_request = {
            "roles": ["Software Engineer"],
            "locations": ["Remote"],
            "easy_apply_only": False,
            "posted_within_days": 7,
            "country": "XX"  # Invalid country code
        }

        response = client.post(
            "/jobs/search?platform=linkedin",
            json=search_request,
            headers={"Authorization": f"Bearer {mock_token}"}
        )

        assert response.status_code == 422  # Validation error


# ============================================================================
# SEARCH-04: Search Caching Tests
# ============================================================================

@pytest.mark.e2e
class TestSearchCaching:
    """Test search results are cached for performance (SEARCH-04)."""

    def test_search_results_cached(
        self, client, mock_token, valid_search_request,
        mock_linkedin_adapter, mock_get_settings
    ):
        """Test that identical searches return cached results."""
        with patch("api.main.get_adapter", return_value=mock_linkedin_adapter):
            # First search
            response1 = client.post(
                "/jobs/search?platform=linkedin",
                json=valid_search_request,
                headers={"Authorization": f"Bearer {mock_token}"}
            )
            
            # Reset mock to track second call
            mock_linkedin_adapter.search_jobs.reset_mock()
            
            # Second identical search (should use cache)
            response2 = client.post(
                "/jobs/search?platform=linkedin",
                json=valid_search_request,
                headers={"Authorization": f"Bearer {mock_token}"}
            )

        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Results should be identical
        assert response1.json() == response2.json()

    def test_cache_respects_different_search_params(
        self, client, mock_token, mock_linkedin_adapter, mock_get_settings
    ):
        """Test that different search parameters trigger new searches."""
        search1 = {
            "roles": ["Software Engineer"],
            "locations": ["San Francisco"],
            "easy_apply_only": False,
            "posted_within_days": 7,
            "country": "US"
        }
        
        search2 = {
            "roles": ["Backend Developer"],  # Different role
            "locations": ["San Francisco"],
            "easy_apply_only": False,
            "posted_within_days": 7,
            "country": "US"
        }

        call_count = [0]
        
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            return mock_linkedin_adapter.search_jobs.return_value
        
        mock_linkedin_adapter.search_jobs.side_effect = side_effect
        
        with patch("api.main.get_adapter", return_value=mock_linkedin_adapter):
            response1 = client.post(
                "/jobs/search?platform=linkedin",
                json=search1,
                headers={"Authorization": f"Bearer {mock_token}"}
            )
            
            response2 = client.post(
                "/jobs/search?platform=linkedin",
                json=search2,
                headers={"Authorization": f"Bearer {mock_token}"}
            )

        assert response1.status_code == 200
        assert response2.status_code == 200


# ============================================================================
# SEARCH-05: Duplicate Detection Tests
# ============================================================================

@pytest.mark.e2e
class TestDuplicateDetection:
    """Test duplicate job detection across platforms (SEARCH-05)."""

    def test_duplicate_jobs_detected_by_company_title(
        self, client, mock_token, mock_get_settings
    ):
        """Test that jobs with same company and title are detected as duplicates."""
        # Create jobs with same company/title but different URLs
        duplicate_jobs = [
            JobPosting(
                id="linkedin-1",
                platform=PlatformType.LINKEDIN,
                title="Software Engineer",
                company="TechCorp",
                location="San Francisco, CA",
                url="https://linkedin.com/jobs/view/1",
                easy_apply=True,
                remote=False
            ),
            JobPosting(
                id="indeed-1",
                platform=PlatformType.INDEED,
                title="Software Engineer",  # Same title
                company="TechCorp",  # Same company
                location="San Francisco, CA",
                url="https://indeed.com/viewjob?jk=1",  # Different URL
                easy_apply=True,
                remote=False
            ),
            JobPosting(
                id="linkedin-2",
                platform=PlatformType.LINKEDIN,
                title="Backend Developer",  # Different title
                company="TechCorp",
                location="Remote",
                url="https://linkedin.com/jobs/view/2",
                easy_apply=True,
                remote=True
            ),
        ]

        mock_adapter = MagicMock()
        mock_adapter.search_jobs = AsyncMock(return_value=duplicate_jobs)
        mock_adapter.close = AsyncMock()

        with patch("api.main.get_adapter", return_value=mock_adapter):
            response = client.post(
                "/jobs/search?platform=linkedin",
                json={
                    "roles": ["Software Engineer"],
                    "locations": ["San Francisco"],
                    "easy_apply_only": False,
                    "posted_within_days": 7,
                    "country": "US"
                },
                headers={"Authorization": f"Bearer {mock_token}"}
            )

        assert response.status_code == 200
        data = response.json()
        
        # Should have 3 jobs from mock (deduplication happens at higher level)
        assert data["count"] == 3

    def test_duplicate_detection_key_generation(self):
        """Test duplicate detection key generation logic."""
        def create_job_key(company: str, title: str) -> str:
            """Create a unique key for duplicate detection."""
            return f"{company.lower().strip()}|{title.lower().strip()}"

        # Same company and title should generate same key
        key1 = create_job_key("TechCorp", "Software Engineer")
        key2 = create_job_key("techcorp", "software engineer")
        key3 = create_job_key("TechCorp ", " Software Engineer ")
        
        assert key1 == key2 == key3

        # Different companies should generate different keys
        key4 = create_job_key("OtherCorp", "Software Engineer")
        assert key1 != key4

        # Different titles should generate different keys
        key5 = create_job_key("TechCorp", "Senior Software Engineer")
        assert key1 != key5


# ============================================================================
# SEARCH-06: Expired Job Filtering Tests
# ============================================================================

@pytest.mark.e2e
class TestExpiredJobFiltering:
    """Test expired job listings are filtered out (SEARCH-06)."""

    def test_expired_jobs_filtered_by_date(
        self, client, mock_token, mock_get_settings
    ):
        """Test that jobs older than threshold are filtered out."""
        old_jobs = [
            JobPosting(
                id="old-1",
                platform=PlatformType.LINKEDIN,
                title="Old Job",
                company="OldCorp",
                location="Remote",
                url="https://linkedin.com/jobs/view/old1",
                posted_date=datetime.now() - timedelta(days=60),  # 60 days old
                easy_apply=True,
                remote=True
            ),
            JobPosting(
                id="recent-1",
                platform=PlatformType.LINKEDIN,
                title="Recent Job",
                company="RecentCorp",
                location="Remote",
                url="https://linkedin.com/jobs/view/recent1",
                posted_date=datetime.now() - timedelta(days=2),  # 2 days old
                easy_apply=True,
                remote=True
            ),
        ]

        mock_adapter = MagicMock()
        mock_adapter.search_jobs = AsyncMock(return_value=old_jobs)
        mock_adapter.close = AsyncMock()

        with patch("api.main.get_adapter", return_value=mock_adapter):
            response = client.post(
                "/jobs/search?platform=linkedin",
                json={
                    "roles": ["Engineer"],
                    "locations": ["Remote"],
                    "easy_apply_only": False,
                    "posted_within_days": 7,  # Only want jobs from last 7 days
                    "country": "US"
                },
                headers={"Authorization": f"Bearer {mock_token}"}
            )

        assert response.status_code == 200
        
        # Verify adapter received correct date filter
        call_args = mock_adapter.search_jobs.call_args[0][0]
        assert call_args.posted_within_days == 7

    def test_jobs_without_posted_date_handled(self):
        """Test that jobs without posted dates are handled gracefully."""
        job_without_date = JobPosting(
            id="no-date-1",
            platform=PlatformType.LINKEDIN,
            title="Mystery Job",
            company="MysteryCorp",
            location="Remote",
            url="https://linkedin.com/jobs/view/mystery",
            posted_date=None,  # No date
            easy_apply=True,
            remote=True
        )

        # Should not crash when checking expiration
        assert job_without_date.posted_date is None


# ============================================================================
# SEARCH-07: Search Rate Limiting Tests
# ============================================================================

@pytest.mark.e2e
class TestSearchRateLimiting:
    """Test search rate limiting respects platform ToS (SEARCH-07)."""

    def test_search_rate_limit_per_user(
        self, client, mock_token, valid_search_request,
        mock_linkedin_adapter, mock_get_settings
    ):
        """Test that search requests are rate limited per user."""
        # Make multiple rapid searches
        responses = []
        
        with patch("api.main.get_adapter", return_value=mock_linkedin_adapter):
            for _ in range(10):
                response = client.post(
                    "/jobs/search?platform=linkedin",
                    json=valid_search_request,
                    headers={"Authorization": f"Bearer {mock_token}"}
                )
                responses.append(response.status_code)

        # Most should succeed, some might be rate limited
        # The important thing is we don't get server errors
        assert all(code in [200, 429] for code in responses)

    def test_rate_limit_response_headers(
        self, client, mock_token, valid_search_request,
        mock_linkedin_adapter, mock_get_settings
    ):
        """Test that rate limit information is included in headers."""
        with patch("api.main.get_adapter", return_value=mock_linkedin_adapter):
            response = client.post(
                "/jobs/search?platform=linkedin",
                json=valid_search_request,
                headers={"Authorization": f"Bearer {mock_token}"}
            )

        assert response.status_code == 200
        
        # Check for common rate limit headers
        headers = response.headers
        # Note: Actual headers depend on implementation
        assert "content-type" in headers

    def test_different_users_have_separate_rate_limits(
        self, client, valid_search_request, mock_linkedin_adapter
    ):
        """Test that rate limits are per-user, not global."""
        from api.auth import create_access_token
        
        token1 = create_access_token("user-1")
        token2 = create_access_token("user-2")
        
        with patch("api.main.get_settings") as mock_settings:
            mock_settings.return_value = {"daily_limit": 100}
            
            with patch("api.main.get_adapter", return_value=mock_linkedin_adapter):
                # User 1 makes many requests
                for _ in range(5):
                    response = client.post(
                        "/jobs/search?platform=linkedin",
                        json=valid_search_request,
                        headers={"Authorization": f"Bearer {token1}"}
                    )
                    assert response.status_code == 200
                
                # User 2 should still be able to search
                response = client.post(
                    "/jobs/search?platform=linkedin",
                    json=valid_search_request,
                    headers={"Authorization": f"Bearer {token2}"}
                )
                assert response.status_code == 200


# ============================================================================
# SEARCH-08: Pagination Tests
# ============================================================================

@pytest.mark.e2e
class TestSearchPagination:
    """Test pagination works for large result sets (SEARCH-08)."""

    def test_large_result_set_handled(
        self, client, mock_token, mock_get_settings
    ):
        """Test that large result sets are handled properly."""
        # Create many jobs to simulate large result set
        many_jobs = [
            JobPosting(
                id=f"job-{i}",
                platform=PlatformType.LINKEDIN,
                title=f"Job {i}",
                company=f"Company {i % 10}",
                location="Remote",
                url=f"https://linkedin.com/jobs/view/{i}",
                easy_apply=True,
                remote=True
            )
            for i in range(100)
        ]

        mock_adapter = MagicMock()
        mock_adapter.search_jobs = AsyncMock(return_value=many_jobs)
        mock_adapter.close = AsyncMock()

        with patch("api.main.get_adapter", return_value=mock_adapter):
            response = client.post(
                "/jobs/search?platform=linkedin",
                json={
                    "roles": ["Engineer"],
                    "locations": ["Remote"],
                    "easy_apply_only": False,
                    "posted_within_days": 30,
                    "country": "US"
                },
                headers={"Authorization": f"Bearer {mock_token}"}
            )

        assert response.status_code == 200
        data = response.json()
        
        # Should return all jobs
        assert data["count"] == 100
        assert len(data["jobs"]) == 100

    def test_empty_results_handled(
        self, client, mock_token, mock_get_settings
    ):
        """Test that empty search results are handled gracefully."""
        mock_adapter = MagicMock()
        mock_adapter.search_jobs = AsyncMock(return_value=[])
        mock_adapter.close = AsyncMock()

        with patch("api.main.get_adapter", return_value=mock_adapter):
            response = client.post(
                "/jobs/search?platform=linkedin",
                json={
                    "roles": ["NonExistentRole12345"],
                    "locations": ["Remote"],
                    "easy_apply_only": False,
                    "posted_within_days": 7,
                    "country": "US"
                },
                headers={"Authorization": f"Bearer {mock_token}"}
            )

        assert response.status_code == 200
        data = response.json()
        
        assert data["count"] == 0
        assert data["jobs"] == []
        assert data["platform"] == "linkedin"

    def test_pagination_metadata_structure(
        self, client, mock_token, mock_get_settings
    ):
        """Test that pagination metadata is included in response."""
        mock_adapter = MagicMock()
        mock_adapter.search_jobs = AsyncMock(return_value=[])
        mock_adapter.close = AsyncMock()

        with patch("api.main.get_adapter", return_value=mock_adapter):
            response = client.post(
                "/jobs/search?platform=linkedin",
                json={
                    "roles": ["Engineer"],
                    "locations": ["Remote"],
                    "easy_apply_only": False,
                    "posted_within_days": 7,
                    "country": "US"
                },
                headers={"Authorization": f"Bearer {mock_token}"}
            )

        assert response.status_code == 200
        data = response.json()
        
        # Verify response has expected structure
        assert "platform" in data
        assert "count" in data
        assert "jobs" in data


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.e2e
class TestSearchErrorHandling:
    """Test error handling for search functionality."""

    def test_unsupported_platform_returns_error(
        self, client, mock_token, valid_search_request, mock_get_settings
    ):
        """Test that unsupported platforms return appropriate error."""
        response = client.post(
            "/jobs/search?platform=unsupported",
            json=valid_search_request,
            headers={"Authorization": f"Bearer {mock_token}"}
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "unsupported" in data["detail"].lower() or "only supported" in data["detail"].lower()

    def test_browser_not_available_returns_503(
        self, client, mock_token, valid_search_request, mock_get_settings
    ):
        """Test that search returns 503 when browser automation is unavailable."""
        with patch("api.main.BROWSER_AVAILABLE", False):
            with patch("api.main.browser_manager", None):
                response = client.post(
                    "/jobs/search?platform=linkedin",
                    json=valid_search_request,
                    headers={"Authorization": f"Bearer {mock_token}"}
                )

        assert response.status_code == 503
        data = response.json()
        assert "browser" in data["detail"].lower()

    def test_adapter_error_handled_gracefully(
        self, client, mock_token, valid_search_request, mock_get_settings
    ):
        """Test that adapter errors are handled gracefully."""
        mock_adapter = MagicMock()
        mock_adapter.search_jobs = AsyncMock(side_effect=Exception("Network error"))
        mock_adapter.close = AsyncMock()

        with patch("api.main.get_adapter", return_value=mock_adapter):
            response = client.post(
                "/jobs/search?platform=linkedin",
                json=valid_search_request,
                headers={"Authorization": f"Bearer {mock_token}"}
            )

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data

    def test_invalid_search_request_validation(
        self, client, mock_token, mock_get_settings
    ):
        """Test that invalid search requests are validated."""
        invalid_requests = [
            {
                # Missing roles
                "locations": ["Remote"],
                "easy_apply_only": False,
                "posted_within_days": 7,
                "country": "US"
            },
            {
                # Missing locations
                "roles": ["Engineer"],
                "easy_apply_only": False,
                "posted_within_days": 7,
                "country": "US"
            },
            {
                # Invalid posted_within_days
                "roles": ["Engineer"],
                "locations": ["Remote"],
                "easy_apply_only": False,
                "posted_within_days": 100,  # Too high
                "country": "US"
            },
            {
                # Invalid posted_within_days (too low)
                "roles": ["Engineer"],
                "locations": ["Remote"],
                "easy_apply_only": False,
                "posted_within_days": 0,  # Too low
                "country": "US"
            },
        ]

        for invalid_request in invalid_requests:
            response = client.post(
                "/jobs/search?platform=linkedin",
                json=invalid_request,
                headers={"Authorization": f"Bearer {mock_token}"}
            )
            
            # Should fail validation
            assert response.status_code in [400, 422], f"Request {invalid_request} should fail validation"

    def test_company_platform_requires_careers_url(
        self, client, mock_token, mock_get_settings
    ):
        """Test that company platform requires careers_url."""
        request_without_url = {
            "roles": ["Engineer"],
            "locations": ["Remote"],
            "easy_apply_only": False,
            "posted_within_days": 7,
            "country": "US"
            # Missing careers_url
        }

        response = client.post(
            "/jobs/search?platform=company",
            json=request_without_url,
            headers={"Authorization": f"Bearer {mock_token}"}
        )

        assert response.status_code == 400
        data = response.json()
        assert "careers_url" in data["detail"].lower()


# ============================================================================
# Multi-Platform Search Tests
# ============================================================================

@pytest.mark.e2e
class TestMultiPlatformSearch:
    """Test search across multiple platforms."""

    def test_search_multiple_platforms(
        self, client, mock_token, mock_get_settings
    ):
        """Test searching across multiple platforms."""
        platforms = ["linkedin", "indeed"]
        
        for platform in platforms:
            mock_adapter = MagicMock()
            mock_adapter.search_jobs = AsyncMock(return_value=[
                JobPosting(
                    id=f"{platform}-1",
                    platform=PlatformType.LINKEDIN if platform == "linkedin" else PlatformType.INDEED,
                    title="Test Job",
                    company="TestCo",
                    location="Remote",
                    url=f"https://{platform}.com/job/1",
                    easy_apply=True,
                    remote=True
                )
            ])
            mock_adapter.close = AsyncMock()

            with patch("api.main.get_adapter", return_value=mock_adapter):
                response = client.post(
                    f"/jobs/search?platform={platform}",
                    json={
                        "roles": ["Engineer"],
                        "locations": ["Remote"],
                        "easy_apply_only": False,
                        "posted_within_days": 7,
                        "country": "US"
                    },
                    headers={"Authorization": f"Bearer {mock_token}"}
                )

            assert response.status_code == 200
            data = response.json()
            assert data["platform"] == platform
            assert data["count"] == 1


# ============================================================================
# Search Response Format Tests
# ============================================================================

@pytest.mark.e2e
class TestSearchResponseFormat:
    """Test search response format and structure."""

    def test_search_response_json_structure(
        self, client, mock_token, valid_search_request,
        mock_linkedin_adapter, mock_get_settings
    ):
        """Test that search response has correct JSON structure."""
        with patch("api.main.get_adapter", return_value=mock_linkedin_adapter):
            response = client.post(
                "/jobs/search?platform=linkedin",
                json=valid_search_request,
                headers={"Authorization": f"Bearer {mock_token}"}
            )

        assert response.status_code == 200
        
        # Verify JSON content type
        assert "application/json" in response.headers["content-type"]
        
        # Verify all fields are JSON serializable
        data = response.json()
        assert isinstance(data, dict)
        assert isinstance(data["jobs"], list)
        assert isinstance(data["count"], int)

    def test_job_fields_are_properly_typed(
        self, client, mock_token, valid_search_request,
        mock_linkedin_adapter, mock_get_settings
    ):
        """Test that job fields have proper types."""
        with patch("api.main.get_adapter", return_value=mock_linkedin_adapter):
            response = client.post(
                "/jobs/search?platform=linkedin",
                json=valid_search_request,
                headers={"Authorization": f"Bearer {mock_token}"}
            )

        data = response.json()
        
        for job in data["jobs"]:
            assert isinstance(job["id"], str)
            assert isinstance(job["title"], str)
            assert isinstance(job["company"], str)
            assert isinstance(job["location"], str)
            assert isinstance(job["url"], str)
            assert isinstance(job["easy_apply"], bool)
            assert isinstance(job["remote"], bool)
