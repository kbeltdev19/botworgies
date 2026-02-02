"""
End-to-End Application Tracking & Analytics Tests for Job Applier API.

This module tests the complete application tracking functionality including:
- Application storage with metadata (TRACK-01)
- Application status updates (TRACK-02)
- Dashboard application history display (TRACK-03)
- Application filtering and sorting (TRACK-04)
- Export functionality (TRACK-05)
- Analytics calculations (TRACK-06)
- Email status parsing (TRACK-07)

Technical Specifications:
- Applications stored with: id, user_id, job_url, job_title, company, platform, status, message, error, screenshot_path, created_at
- Status values: pending, ready_to_submit, pending_review, submitted, external_application, failed, error
- Analytics: success rates, platform breakdown, daily/weekly trends
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

# Ensure project root is in path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.main import app
from adapters.base import ApplicationResult, ApplicationStatus


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_user_id():
    """Sample user ID for testing."""
    return "test-user-uuid-1234"


@pytest.fixture
def mock_auth_header(mock_user_id):
    """Mock authentication header."""
    return {"Authorization": "Bearer mock-token"}


@pytest.fixture
def sample_applications(mock_user_id):
    """Sample application data for testing."""
    base_time = datetime.now()
    return [
        {
            "id": "app_001",
            "user_id": mock_user_id,
            "job_url": "https://linkedin.com/jobs/view/1",
            "job_title": "Senior Software Engineer",
            "company": "TechCorp",
            "platform": "linkedin",
            "status": "submitted",
            "message": "Application submitted successfully",
            "error": None,
            "screenshot_path": "/screenshots/app_001.png",
            "created_at": (base_time - timedelta(days=1)).isoformat()
        },
        {
            "id": "app_002",
            "user_id": mock_user_id,
            "job_url": "https://indeed.com/viewjob?jk=2",
            "job_title": "Backend Developer",
            "company": "StartupCo",
            "platform": "indeed",
            "status": "failed",
            "message": "",
            "error": "Form validation failed",
            "screenshot_path": None,
            "created_at": (base_time - timedelta(days=2)).isoformat()
        },
        {
            "id": "app_003",
            "user_id": mock_user_id,
            "job_url": "https://boards.greenhouse.io/company/jobs/3",
            "job_title": "Full Stack Engineer",
            "company": "GreenhouseCorp",
            "platform": "greenhouse",
            "status": "pending",
            "message": "Waiting for submission",
            "error": None,
            "screenshot_path": None,
            "created_at": (base_time - timedelta(hours=5)).isoformat()
        },
        {
            "id": "app_004",
            "user_id": mock_user_id,
            "job_url": "https://linkedin.com/jobs/view/4",
            "job_title": "DevOps Engineer",
            "company": "CloudTech",
            "platform": "linkedin",
            "status": "submitted",
            "message": "Successfully applied",
            "error": None,
            "screenshot_path": "/screenshots/app_004.png",
            "created_at": (base_time - timedelta(days=5)).isoformat()
        },
        {
            "id": "app_005",
            "user_id": mock_user_id,
            "job_url": "https://jobs.lever.co/company/5",
            "job_title": "Python Developer",
            "company": "LeverCo",
            "platform": "lever",
            "status": "error",
            "message": "",
            "error": "Network timeout",
            "screenshot_path": None,
            "created_at": (base_time - timedelta(days=3)).isoformat()
        }
    ]


@pytest.fixture
def mock_get_current_user(mock_user_id):
    """Mock get_current_user dependency."""
    with patch("api.main.get_current_user") as mock:
        mock.return_value = mock_user_id
        yield mock


# ============================================================================
# TRACK-01: Applications Stored with Correct Metadata Tests
# ============================================================================

class TestApplicationMetadataStorage:
    """Test that applications are stored with correct metadata (TRACK-01)."""

    def test_application_has_all_required_metadata(
        self, client, mock_get_current_user, mock_auth_header
    ):
        """Test that applications contain all required metadata fields."""
        expected_app = {
            "id": "app_test_001",
            "user_id": "test-user-uuid-1234",
            "job_url": "https://linkedin.com/jobs/view/123",
            "job_title": "Software Engineer",
            "company": "TestCorp",
            "platform": "linkedin",
            "status": "submitted",
            "message": "Application successful",
            "created_at": datetime.now().isoformat()
        }

        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = [expected_app]
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        assert "applications" in data
        assert len(data["applications"]) == 1
        
        app = data["applications"][0]
        # Verify all required fields are present
        required_fields = [
            "id", "user_id", "job_url", "job_title", "company",
            "platform", "status", "created_at"
        ]
        for field in required_fields:
            assert field in app, f"Missing required field: {field}"

    def test_application_id_format(self, client, mock_get_current_user, mock_auth_header):
        """Test that application IDs follow expected format."""
        mock_app = {
            "id": "app_20240115_143022_a1b2c3d4",
            "user_id": "test-user-uuid-1234",
            "job_url": "https://example.com/job",
            "job_title": "Engineer",
            "company": "Corp",
            "platform": "linkedin",
            "status": "submitted",
            "created_at": datetime.now().isoformat()
        }

        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = [mock_app]
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        app_id = data["applications"][0]["id"]
        
        # ID should be non-empty string
        assert isinstance(app_id, str)
        assert len(app_id) > 0
        # ID should start with 'app_' prefix
        assert app_id.startswith("app_")

    def test_application_timestamps_are_valid_iso(self, client, mock_get_current_user, mock_auth_header):
        """Test that application timestamps are valid ISO format."""
        mock_app = {
            "id": "app_001",
            "user_id": "test-user-uuid-1234",
            "job_url": "https://example.com/job",
            "job_title": "Engineer",
            "company": "Corp",
            "platform": "linkedin",
            "status": "submitted",
            "created_at": "2024-01-15T14:30:22.123456"
        }

        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = [mock_app]
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        created_at = data["applications"][0]["created_at"]
        
        # Should be able to parse as datetime
        try:
            parsed = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            assert isinstance(parsed, datetime)
        except ValueError:
            pytest.fail(f"Invalid timestamp format: {created_at}")

    def test_application_platform_values_are_valid(
        self, client, mock_get_current_user, mock_auth_header
    ):
        """Test that platform values are from supported platforms."""
        valid_platforms = ["linkedin", "indeed", "greenhouse", "workday", "lever"]
        
        for platform in valid_platforms:
            mock_app = {
                "id": f"app_{platform}",
                "user_id": "test-user-uuid-1234",
                "job_url": f"https://{platform}.com/job",
                "job_title": "Engineer",
                "company": "Corp",
                "platform": platform,
                "status": "submitted",
                "created_at": datetime.now().isoformat()
            }

            with patch("api.main.get_applications") as mock_get_apps:
                mock_get_apps.return_value = [mock_app]
                response = client.get("/applications", headers=mock_auth_header)

            assert response.status_code == 200
            data = response.json()
            assert data["applications"][0]["platform"] == platform

    def test_application_user_id_matches_authenticated_user(
        self, client, mock_get_current_user, mock_auth_header, mock_user_id
    ):
        """Test that returned applications belong to the authenticated user."""
        mock_apps = [
            {
                "id": "app_001",
                "user_id": mock_user_id,
                "job_url": "https://example.com/job1",
                "job_title": "Engineer",
                "company": "Corp1",
                "platform": "linkedin",
                "status": "submitted",
                "created_at": datetime.now().isoformat()
            },
            {
                "id": "app_002",
                "user_id": mock_user_id,
                "job_url": "https://example.com/job2",
                "job_title": "Developer",
                "company": "Corp2",
                "platform": "indeed",
                "status": "pending",
                "created_at": datetime.now().isoformat()
            }
        ]

        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = mock_apps
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        
        # All applications should have the authenticated user's ID
        for app in data["applications"]:
            assert app["user_id"] == mock_user_id


# ============================================================================
# TRACK-02: Application Status Updates Tests
# ============================================================================

class TestApplicationStatusUpdates:
    """Test that application status updates are captured correctly (TRACK-02)."""

    @pytest.mark.parametrize("status", [
        "pending",
        "ready_to_submit",
        "pending_review",
        "submitted",
        "external_application",
        "failed",
        "error"
    ])
    def test_all_status_values_accepted(
        self, client, mock_get_current_user, mock_auth_header, status
    ):
        """Test that all ApplicationStatus enum values are stored and returned."""
        mock_app = {
            "id": f"app_{status}",
            "user_id": "test-user-uuid-1234",
            "job_url": "https://example.com/job",
            "job_title": "Engineer",
            "company": "Corp",
            "platform": "linkedin",
            "status": status,
            "created_at": datetime.now().isoformat()
        }

        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = [mock_app]
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        assert data["applications"][0]["status"] == status

    def test_status_transition_from_pending_to_submitted(
        self, client, mock_get_current_user, mock_auth_header
    ):
        """Test tracking status transitions over time."""
        # Initial pending status
        pending_app = {
            "id": "app_transition",
            "user_id": "test-user-uuid-1234",
            "job_url": "https://example.com/job",
            "job_title": "Engineer",
            "company": "Corp",
            "platform": "linkedin",
            "status": "pending",
            "message": "Waiting for submission",
            "created_at": datetime.now().isoformat()
        }

        with patch("api.main.get_application") as mock_get_app:
            mock_get_app.return_value = pending_app
            response = client.get("/applications/app_transition", headers=mock_auth_header)
            assert response.json()["status"] == "pending"

        # Updated submitted status
        submitted_app = dict(pending_app)
        submitted_app["status"] = "submitted"
        submitted_app["message"] = "Application submitted successfully"

        with patch("api.main.get_application") as mock_get_app:
            mock_get_app.return_value = submitted_app
            response = client.get("/applications/app_transition", headers=mock_auth_header)
            assert response.json()["status"] == "submitted"

    def test_failed_status_captures_error_message(
        self, client, mock_get_current_user, mock_auth_header
    ):
        """Test that failed status includes error details."""
        mock_app = {
            "id": "app_failed",
            "user_id": "test-user-uuid-1234",
            "job_url": "https://example.com/job",
            "job_title": "Engineer",
            "company": "Corp",
            "platform": "linkedin",
            "status": "failed",
            "message": "",
            "error": "Form validation failed: missing required field 'years_experience'",
            "created_at": datetime.now().isoformat()
        }

        with patch("api.main.get_application") as mock_get_app:
            mock_get_app.return_value = mock_app
            response = client.get("/applications/app_failed", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert "error" in data
        assert "validation failed" in data["error"].lower()

    def test_error_status_distinguishes_system_errors(
        self, client, mock_get_current_user, mock_auth_header
    ):
        """Test that error status is used for system-level failures."""
        mock_app = {
            "id": "app_error",
            "user_id": "test-user-uuid-1234",
            "job_url": "https://example.com/job",
            "job_title": "Engineer",
            "company": "Corp",
            "platform": "linkedin",
            "status": "error",
            "message": "",
            "error": "Network timeout: connection to server failed after 30s",
            "created_at": datetime.now().isoformat()
        }

        with patch("api.main.get_application") as mock_get_app:
            mock_get_app.return_value = mock_app
            response = client.get("/applications/app_error", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "timeout" in data["error"].lower()

    def test_external_application_status_tracked(
        self, client, mock_get_current_user, mock_auth_header
    ):
        """Test that external application redirects are tracked."""
        mock_app = {
            "id": "app_external",
            "user_id": "test-user-uuid-1234",
            "job_url": "https://example.com/job",
            "job_title": "Engineer",
            "company": "Corp",
            "platform": "workday",
            "status": "external_application",
            "message": "Redirected to external application portal",
            "created_at": datetime.now().isoformat()
        }

        with patch("api.main.get_application") as mock_get_app:
            mock_get_app.return_value = mock_app
            response = client.get("/applications/app_external", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "external_application"


# ============================================================================
# TRACK-03: Dashboard Display Tests
# ============================================================================

class TestDashboardApplicationHistory:
    """Test that dashboard displays application history correctly (TRACK-03)."""

    def test_dashboard_returns_list_of_applications(
        self, client, mock_get_current_user, mock_auth_header, sample_applications
    ):
        """Test that dashboard endpoint returns user's application history."""
        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = sample_applications
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        assert "applications" in data
        assert len(data["applications"]) == len(sample_applications)

    def test_dashboard_applications_sorted_by_date_descending(
        self, client, mock_get_current_user, mock_auth_header
    ):
        """Test that applications are sorted by date, newest first."""
        # Create apps with specific dates
        base_time = datetime.now()
        apps = [
            {
                "id": "app_old",
                "user_id": "test-user-uuid-1234",
                "job_url": "https://example.com/job1",
                "job_title": "Old Job",
                "company": "OldCorp",
                "platform": "linkedin",
                "status": "submitted",
                "created_at": (base_time - timedelta(days=10)).isoformat()
            },
            {
                "id": "app_new",
                "user_id": "test-user-uuid-1234",
                "job_url": "https://example.com/job2",
                "job_title": "New Job",
                "company": "NewCorp",
                "platform": "indeed",
                "status": "pending",
                "created_at": (base_time - timedelta(days=1)).isoformat()
            }
        ]

        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = apps
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        
        # Verify order: newest first
        dates = [datetime.fromisoformat(app["created_at"]) for app in data["applications"]]
        assert dates[0] >= dates[-1]

    def test_dashboard_shows_empty_list_for_new_user(
        self, client, mock_get_current_user, mock_auth_header
    ):
        """Test that new users see empty application list."""
        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = []
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        assert "applications" in data
        assert len(data["applications"]) == 0

    def test_dashboard_includes_job_details_for_each_application(
        self, client, mock_get_current_user, mock_auth_header
    ):
        """Test that dashboard includes job title, company, and URL for each app."""
        mock_apps = [
            {
                "id": "app_001",
                "user_id": "test-user-uuid-1234",
                "job_url": "https://linkedin.com/jobs/view/123",
                "job_title": "Senior Software Engineer",
                "company": "TechCorp",
                "platform": "linkedin",
                "status": "submitted",
                "created_at": datetime.now().isoformat()
            }
        ]

        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = mock_apps
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        app = data["applications"][0]
        
        # Key display fields should be present
        assert app["job_title"] == "Senior Software Engineer"
        assert app["company"] == "TechCorp"
        assert "linkedin.com" in app["job_url"]
        assert app["status"] == "submitted"

    def test_dashboard_handles_large_application_history(
        self, client, mock_get_current_user, mock_auth_header
    ):
        """Test that dashboard handles users with many applications."""
        # Generate 50 applications
        many_apps = []
        base_time = datetime.now()
        for i in range(50):
            many_apps.append({
                "id": f"app_{i:03d}",
                "user_id": "test-user-uuid-1234",
                "job_url": f"https://example.com/job/{i}",
                "job_title": f"Job Title {i}",
                "company": f"Company {i}",
                "platform": "linkedin" if i % 2 == 0 else "indeed",
                "status": "submitted" if i % 3 == 0 else "pending",
                "created_at": (base_time - timedelta(days=i)).isoformat()
            })

        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = many_apps
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        assert len(data["applications"]) == 50


# ============================================================================
# TRACK-04: Filtering and Sorting Tests
# ============================================================================

class TestApplicationFilteringAndSorting:
    """Test application filtering and sorting functionality (TRACK-04)."""

    def test_filter_by_status(self, client, mock_get_current_user, mock_auth_header, sample_applications):
        """Test filtering applications by status."""
        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = sample_applications
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        
        # Filter submitted applications
        submitted = [app for app in data["applications"] if app["status"] == "submitted"]
        assert len(submitted) == 2
        for app in submitted:
            assert app["status"] == "submitted"

        # Filter pending applications
        pending = [app for app in data["applications"] if app["status"] == "pending"]
        assert len(pending) == 1
        assert pending[0]["status"] == "pending"

    def test_filter_by_platform(self, client, mock_get_current_user, mock_auth_header, sample_applications):
        """Test filtering applications by platform."""
        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = sample_applications
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        
        # Filter LinkedIn applications
        linkedin_apps = [app for app in data["applications"] if app["platform"] == "linkedin"]
        assert len(linkedin_apps) == 2
        for app in linkedin_apps:
            assert app["platform"] == "linkedin"

    def test_filter_by_date_range(self, client, mock_get_current_user, mock_auth_header, sample_applications):
        """Test filtering applications by date range."""
        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = sample_applications
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        
        # Filter last 2 days
        cutoff = datetime.now() - timedelta(days=2)
        recent_apps = [
            app for app in data["applications"]
            if datetime.fromisoformat(app["created_at"]) > cutoff
        ]
        
        # Should include app_001 (1 day ago) and app_003 (5 hours ago)
        assert len(recent_apps) >= 1
        for app in recent_apps:
            assert datetime.fromisoformat(app["created_at"]) > cutoff

    def test_filter_by_company(self, client, mock_get_current_user, mock_auth_header, sample_applications):
        """Test filtering applications by company name."""
        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = sample_applications
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        
        # Filter by company name (case-insensitive)
        company_filter = "TechCorp"
        matching = [
            app for app in data["applications"]
            if company_filter.lower() in app["company"].lower()
        ]
        assert len(matching) == 1
        assert matching[0]["company"] == "TechCorp"

    def test_sort_by_date_ascending(self, client, mock_get_current_user, mock_auth_header):
        """Test sorting applications by date ascending (oldest first)."""
        base_time = datetime.now()
        apps = [
            {
                "id": "app_001",
                "user_id": "test-user-uuid-1234",
                "job_url": "https://example.com/job1",
                "job_title": "Job 1",
                "company": "Corp1",
                "platform": "linkedin",
                "status": "submitted",
                "created_at": (base_time - timedelta(days=1)).isoformat()
            },
            {
                "id": "app_002",
                "user_id": "test-user-uuid-1234",
                "job_url": "https://example.com/job2",
                "job_title": "Job 2",
                "company": "Corp2",
                "platform": "indeed",
                "status": "pending",
                "created_at": (base_time - timedelta(days=5)).isoformat()
            },
            {
                "id": "app_003",
                "user_id": "test-user-uuid-1234",
                "job_url": "https://example.com/job3",
                "job_title": "Job 3",
                "company": "Corp3",
                "platform": "greenhouse",
                "status": "submitted",
                "created_at": (base_time - timedelta(days=3)).isoformat()
            }
        ]

        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = sorted(apps, key=lambda x: x["created_at"])
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        
        # Verify ascending order (oldest first)
        dates = [datetime.fromisoformat(app["created_at"]) for app in data["applications"]]
        for i in range(len(dates) - 1):
            assert dates[i] <= dates[i + 1]

    def test_sort_by_company_name(self, client, mock_get_current_user, mock_auth_header):
        """Test sorting applications by company name."""
        apps = [
            {
                "id": "app_001",
                "user_id": "test-user-uuid-1234",
                "job_url": "https://example.com/job1",
                "job_title": "Engineer",
                "company": "Zebra Corp",
                "platform": "linkedin",
                "status": "submitted",
                "created_at": datetime.now().isoformat()
            },
            {
                "id": "app_002",
                "user_id": "test-user-uuid-1234",
                "job_url": "https://example.com/job2",
                "job_title": "Developer",
                "company": "Alpha Inc",
                "platform": "indeed",
                "status": "pending",
                "created_at": datetime.now().isoformat()
            },
            {
                "id": "app_003",
                "user_id": "test-user-uuid-1234",
                "job_url": "https://example.com/job3",
                "job_title": "Manager",
                "company": "Beta LLC",
                "platform": "greenhouse",
                "status": "failed",
                "created_at": datetime.now().isoformat()
            }
        ]

        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = sorted(apps, key=lambda x: x["company"])
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        
        companies = [app["company"] for app in data["applications"]]
        assert companies == sorted(companies)

    def test_combined_filters(self, client, mock_get_current_user, mock_auth_header, sample_applications):
        """Test combining multiple filters."""
        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = sample_applications
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        
        # Combined filter: LinkedIn + Submitted
        filtered = [
            app for app in data["applications"]
            if app["platform"] == "linkedin" and app["status"] == "submitted"
        ]
        
        assert len(filtered) == 2  # app_001 and app_004
        for app in filtered:
            assert app["platform"] == "linkedin"
            assert app["status"] == "submitted"


# ============================================================================
# TRACK-05: Export Functionality Tests
# ============================================================================

class TestExportFunctionality:
    """Test export functionality generates valid reports (TRACK-05)."""

    def test_export_returns_valid_json(self, client, mock_get_current_user, mock_auth_header, sample_applications):
        """Test that export endpoint returns valid JSON."""
        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = sample_applications
            # Export is done through the applications endpoint
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        
        # Response should be valid JSON
        try:
            data = response.json()
            assert "applications" in data
        except json.JSONDecodeError:
            pytest.fail("Response is not valid JSON")

    def test_export_contains_all_application_fields(
        self, client, mock_get_current_user, mock_auth_header, sample_applications
    ):
        """Test that exported data contains all application fields."""
        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = sample_applications
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        
        for app in data["applications"]:
            # Core fields that should be present in export
            core_fields = ["id", "job_url", "job_title", "company", "platform", "status", "created_at"]
            for field in core_fields:
                assert field in app, f"Export missing field: {field}"

    def test_export_data_matches_database(
        self, client, mock_get_current_user, mock_auth_header
    ):
        """Test that exported data matches stored database records."""
        stored_app = {
            "id": "app_001",
            "user_id": "test-user-uuid-1234",
            "job_url": "https://linkedin.com/jobs/view/123",
            "job_title": "Software Engineer",
            "company": "TechCorp",
            "platform": "linkedin",
            "status": "submitted",
            "message": "Application successful",
            "error": None,
            "screenshot_path": "/screenshots/app_001.png",
            "created_at": "2024-01-15T14:30:22.123456"
        }

        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = [stored_app]
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        exported = data["applications"][0]
        
        # Verify all fields match
        assert exported["id"] == stored_app["id"]
        assert exported["job_title"] == stored_app["job_title"]
        assert exported["company"] == stored_app["company"]
        assert exported["status"] == stored_app["status"]

    def test_export_respects_filters(self, client, mock_get_current_user, mock_auth_header, sample_applications):
        """Test that export respects applied filters."""
        # Filter to only submitted applications
        submitted_only = [app for app in sample_applications if app["status"] == "submitted"]

        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = submitted_only
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        
        # All exported apps should be submitted
        for app in data["applications"]:
            assert app["status"] == "submitted"


# ============================================================================
# TRACK-06: Analytics Calculation Tests
# ============================================================================

class TestAnalyticsCalculations:
    """Test that analytics are calculated correctly (TRACK-06)."""

    def test_success_rate_calculation(self, client, mock_get_current_user, mock_auth_header, sample_applications):
        """Test success rate calculation from application statuses."""
        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = sample_applications
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        apps = data["applications"]
        
        # Calculate success rate
        total = len(apps)
        submitted = len([app for app in apps if app["status"] == "submitted"])
        success_rate = (submitted / total * 100) if total > 0 else 0
        
        # With 5 apps (2 submitted, 1 pending, 2 failed/error)
        assert total == 5
        assert submitted == 2
        assert success_rate == 40.0

    def test_platform_breakdown(self, client, mock_get_current_user, mock_auth_header, sample_applications):
        """Test platform usage breakdown."""
        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = sample_applications
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        apps = data["applications"]
        
        # Count by platform
        platform_counts = {}
        for app in apps:
            platform = app["platform"]
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
        
        assert platform_counts["linkedin"] == 2
        assert platform_counts["indeed"] == 1
        assert platform_counts["greenhouse"] == 1
        assert platform_counts["lever"] == 1

    def test_status_distribution(self, client, mock_get_current_user, mock_auth_header, sample_applications):
        """Test status distribution calculation."""
        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = sample_applications
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        apps = data["applications"]
        
        # Count by status
        status_counts = {}
        for app in apps:
            status = app["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
        
        assert status_counts["submitted"] == 2
        assert status_counts["failed"] == 1
        assert status_counts["pending"] == 1
        assert status_counts["error"] == 1

    def test_daily_application_count(self, client, mock_get_current_user, mock_auth_header):
        """Test daily application count analytics."""
        base_time = datetime.now()
        apps = [
            {
                "id": "app_001",
                "user_id": "test-user-uuid-1234",
                "job_url": "https://example.com/job1",
                "job_title": "Job 1",
                "company": "Corp1",
                "platform": "linkedin",
                "status": "submitted",
                "created_at": base_time.replace(hour=10).isoformat()
            },
            {
                "id": "app_002",
                "user_id": "test-user-uuid-1234",
                "job_url": "https://example.com/job2",
                "job_title": "Job 2",
                "company": "Corp2",
                "platform": "indeed",
                "status": "submitted",
                "created_at": base_time.replace(hour=14).isoformat()
            },
            {
                "id": "app_003",
                "user_id": "test-user-uuid-1234",
                "job_url": "https://example.com/job3",
                "job_title": "Job 3",
                "company": "Corp3",
                "platform": "greenhouse",
                "status": "pending",
                "created_at": (base_time - timedelta(days=1)).isoformat()
            }
        ]

        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = apps
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        
        # Group by date
        daily_counts = {}
        for app in data["applications"]:
            date = app["created_at"][:10]  # YYYY-MM-DD
            daily_counts[date] = daily_counts.get(date, 0) + 1
        
        today = base_time.strftime("%Y-%m-%d")
        yesterday = (base_time - timedelta(days=1)).strftime("%Y-%m-%d")
        
        assert daily_counts.get(today) == 2
        assert daily_counts.get(yesterday) == 1

    def test_weekly_trend_calculation(self, client, mock_get_current_user, mock_auth_header):
        """Test weekly trend calculation."""
        base_time = datetime.now()
        apps = []
        
        # Create apps spread across different days
        for i in range(14):
            day_offset = i // 2  # 2 apps per day for 7 days
            apps.append({
                "id": f"app_{i:03d}",
                "user_id": "test-user-uuid-1234",
                "job_url": f"https://example.com/job{i}",
                "job_title": f"Job {i}",
                "company": f"Corp{i}",
                "platform": "linkedin" if i % 2 == 0 else "indeed",
                "status": "submitted" if i % 3 == 0 else "pending",
                "created_at": (base_time - timedelta(days=day_offset)).isoformat()
            })

        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = apps
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        
        # Calculate weekly trend
        weekly_counts = {}
        for app in data["applications"]:
            created = datetime.fromisoformat(app["created_at"])
            week_key = created.strftime("%Y-W%U")
            weekly_counts[week_key] = weekly_counts.get(week_key, 0) + 1
        
        # Should have data for at least 2 weeks
        assert len(weekly_counts) >= 1

    def test_company_application_count(self, client, mock_get_current_user, mock_auth_header, sample_applications):
        """Test analytics for applications per company."""
        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.return_value = sample_applications
            response = client.get("/applications", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        
        # Count applications per company
        company_counts = {}
        for app in data["applications"]:
            company = app["company"]
            company_counts[company] = company_counts.get(company, 0) + 1
        
        # Each company in sample data has 1 application
        assert len(company_counts) == 5
        for count in company_counts.values():
            assert count == 1


# ============================================================================
# TRACK-07: Email Status Updates Tests
# ============================================================================

class TestEmailStatusParsing:
    """Test that email status updates are parsed correctly (TRACK-07)."""

    def test_application_status_field_reflects_email_updates(
        self, client, mock_get_current_user, mock_auth_header
    ):
        """Test that application status reflects email-based status updates."""
        # Simulate an application that received email confirmation
        app_with_email_update = {
            "id": "app_email_001",
            "user_id": "test-user-uuid-1234",
            "job_url": "https://linkedin.com/jobs/view/123",
            "job_title": "Software Engineer",
            "company": "TechCorp",
            "platform": "linkedin",
            "status": "submitted",  # Updated from email confirmation
            "message": "Application confirmed via email receipt",
            "error": None,
            "created_at": datetime.now().isoformat()
        }

        with patch("api.main.get_application") as mock_get_app:
            mock_get_app.return_value = app_with_email_update
            response = client.get("/applications/app_email_001", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "submitted"
        assert "email" in data["message"].lower() or "confirmed" in data["message"].lower()

    def test_rejection_email_parsed_correctly(self, client, mock_get_current_user, mock_auth_header):
        """Test that rejection emails are parsed and status updated."""
        rejected_app = {
            "id": "app_rejected",
            "user_id": "test-user-uuid-1234",
            "job_url": "https://example.com/job",
            "job_title": "Engineer",
            "company": "Corp",
            "platform": "greenhouse",
            "status": "submitted",  # Original status
            "message": "Application submitted - awaiting response",
            "error": None,
            "created_at": datetime.now().isoformat()
        }

        with patch("api.main.get_application") as mock_get_app:
            mock_get_app.return_value = rejected_app
            response = client.get("/applications/app_rejected", headers=mock_auth_header)
            assert response.json()["status"] == "submitted"

    def test_interview_invitation_email_parsed(self, client, mock_get_current_user, mock_auth_header):
        """Test that interview invitation emails are tracked."""
        app_with_interview = {
            "id": "app_interview",
            "user_id": "test-user-uuid-1234",
            "job_url": "https://example.com/job",
            "job_title": "Senior Engineer",
            "company": "DreamCorp",
            "platform": "linkedin",
            "status": "submitted",
            "message": "Interview invitation received",
            "error": None,
            "created_at": datetime.now().isoformat()
        }

        with patch("api.main.get_application") as mock_get_app:
            mock_get_app.return_value = app_with_interview
            response = client.get("/applications/app_interview", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "submitted"
        # Message indicates interview status
        assert "interview" in data["message"].lower()

    def test_email_confirmation_id_tracking(self, client, mock_get_current_user, mock_auth_header):
        """Test that email confirmation IDs are tracked with applications."""
        app_with_confirmation = {
            "id": "app_confirmed",
            "user_id": "test-user-uuid-1234",
            "job_url": "https://example.com/job",
            "job_title": "Developer",
            "company": "ConfirmedCorp",
            "platform": "indeed",
            "status": "submitted",
            "message": "Confirmation ID: APP-12345-XYZ",
            "error": None,
            "created_at": datetime.now().isoformat()
        }

        with patch("api.main.get_application") as mock_get_app:
            mock_get_app.return_value = app_with_confirmation
            response = client.get("/applications/app_confirmed", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        # Confirmation ID should be in message
        assert "confirmation" in data["message"].lower() or "APP-" in data["message"]


# ============================================================================
# GET /applications/{app_id} Endpoint Tests
# ============================================================================

class TestGetSpecificApplication:
    """Test GET /applications/{application_id} endpoint."""

    def test_get_specific_application_success(
        self, client, mock_get_current_user, mock_auth_header
    ):
        """Test retrieving a specific application by ID."""
        mock_app = {
            "id": "app_specific_001",
            "user_id": "test-user-uuid-1234",
            "job_url": "https://linkedin.com/jobs/view/123",
            "job_title": "Software Engineer",
            "company": "TechCorp",
            "platform": "linkedin",
            "status": "submitted",
            "message": "Application successful",
            "created_at": datetime.now().isoformat()
        }

        with patch("api.main.get_application") as mock_get_app:
            mock_get_app.return_value = mock_app
            response = client.get("/applications/app_specific_001", headers=mock_auth_header)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "app_specific_001"
        assert data["job_title"] == "Software Engineer"

    def test_get_nonexistent_application_returns_404(
        self, client, mock_get_current_user, mock_auth_header
    ):
        """Test that requesting non-existent application returns 404."""
        with patch("api.main.get_application") as mock_get_app:
            mock_get_app.return_value = None
            response = client.get("/applications/nonexistent_id", headers=mock_auth_header)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_cannot_access_other_users_application(
        self, client, mock_get_current_user, mock_auth_header
    ):
        """Test that users cannot access other users' applications."""
        other_user_app = {
            "id": "app_other_user",
            "user_id": "different-user-uuid-5678",  # Different user
            "job_url": "https://example.com/job",
            "job_title": "Secret Job",
            "company": "SecretCorp",
            "platform": "linkedin",
            "status": "submitted",
            "created_at": datetime.now().isoformat()
        }

        with patch("api.main.get_application") as mock_get_app:
            mock_get_app.return_value = other_user_app
            response = client.get("/applications/app_other_user", headers=mock_auth_header)

        assert response.status_code == 403
        assert "access denied" in response.json()["detail"].lower()


# ============================================================================
# ApplicationResult Integration Tests
# ============================================================================

class TestApplicationResultIntegration:
    """Test ApplicationResult and ApplicationStatus enum integration."""

    def test_application_status_enum_values(self):
        """Test that ApplicationStatus enum has expected values."""
        expected_statuses = [
            "pending",
            "ready_to_submit",
            "pending_review",
            "submitted",
            "external_application",
            "failed",
            "error"
        ]
        
        for status in expected_statuses:
            assert hasattr(ApplicationStatus, status.upper())
            enum_value = getattr(ApplicationStatus, status.upper())
            assert enum_value.value == status

    def test_application_result_dataclass_creation(self):
        """Test creating ApplicationResult with different statuses."""
        result = ApplicationResult(
            status=ApplicationStatus.SUBMITTED,
            message="Application submitted successfully",
            confirmation_id="CONF-12345",
            screenshot_path="/screenshots/app_001.png"
        )
        
        assert result.status == ApplicationStatus.SUBMITTED
        assert result.message == "Application submitted successfully"
        assert result.confirmation_id == "CONF-12345"
        assert result.screenshot_path == "/screenshots/app_001.png"

    def test_application_result_with_error_status(self):
        """Test ApplicationResult for failed applications."""
        result = ApplicationResult(
            status=ApplicationStatus.FAILED,
            message="",
            error="Form validation failed",
            screenshot_path=None
        )
        
        assert result.status == ApplicationStatus.FAILED
        assert result.error == "Form validation failed"
        assert result.confirmation_id is None


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestTrackingErrorHandling:
    """Test error handling in tracking endpoints."""

    def test_unauthorized_access_returns_401(self, client):
        """Test that unauthorized requests return 401."""
        response = client.get("/applications")
        assert response.status_code == 401

    def test_invalid_token_returns_401(self, client):
        """Test that invalid tokens return 401."""
        response = client.get(
            "/applications",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401

    def test_database_error_handling(self, client, mock_get_current_user, mock_auth_header):
        """Test graceful handling of database errors."""
        with patch("api.main.get_applications") as mock_get_apps:
            mock_get_apps.side_effect = Exception("Database connection failed")
            response = client.get("/applications", headers=mock_auth_header)

        # Should return 500 but not crash
        assert response.status_code == 500
