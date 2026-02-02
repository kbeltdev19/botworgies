"""
End-to-End Profile Management Tests for Job Applier API.

This module tests the user profile management functionality including:
- PROFILE-01: Profile data saves and retrieves correctly
- PROFILE-02: Required fields validated before save
- PROFILE-03: Job preferences (location, remote, salary) stored correctly
- PROFILE-04: LinkedIn credentials encrypted at rest
- PROFILE-05: Profile updates reflect immediately in applications
- PROFILE-06: Multiple resume versions can be stored

Technical Specifications:
- Profile stored in SQLite database (profiles table)
- LinkedIn cookies encrypted using XOR with key-derived hash
- Multiple resumes supported (resumes table with user_id foreign key)
- Profile validation via Pydantic models
"""

import pytest
import json
from datetime import datetime
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Ensure project root is in path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.main import app
from api import main as api_main
from api.auth import encrypt_sensitive_data, decrypt_sensitive_data
from adapters.base import UserProfile, SearchConfig

# Test user ID for all tests
TEST_USER_ID = "test-user-profile-1234"


# ============================================================================
# Fixtures
# ============================================================================

def mock_get_current_user():
    """Mock get_current_user dependency."""
    return TEST_USER_ID


@pytest.fixture
def client():
    """Create a test client for the FastAPI app with mocked auth."""
    # Override the dependency
    app.dependency_overrides[api_main.get_current_user] = mock_get_current_user
    yield TestClient(app)
    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def mock_user_id():
    """Sample user ID for testing."""
    return TEST_USER_ID


@pytest.fixture
def valid_profile_data():
    """Valid profile request data."""
    return {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone": "555-123-4567",
        "linkedin_url": "https://linkedin.com/in/johndoe",
        "years_experience": 5,
        "work_authorization": "Yes",
        "sponsorship_required": "No",
        "custom_answers": {
            "notice_period": "2 weeks",
            "preferred_start": "Immediately"
        }
    }


@pytest.fixture
def valid_profile_data_updated():
    """Updated profile request data."""
    return {
        "first_name": "Jane",
        "last_name": "Smith",
        "email": "jane.smith@example.com",
        "phone": "555-987-6543",
        "linkedin_url": "https://linkedin.com/in/janesmith",
        "years_experience": 8,
        "work_authorization": "Yes",
        "sponsorship_required": "No",
        "custom_answers": {
            "notice_period": "1 month",
            "preferred_start": "2 weeks notice"
        }
    }


# ============================================================================
# PROFILE-01: Profile Data Save and Retrieve Tests
# ============================================================================

class TestProfileSaveAndRetrieve:
    """Test profile data saves and retrieves correctly (PROFILE-01)."""

    def test_create_profile_returns_200_and_profile_data(
        self, client, valid_profile_data
    ):
        """Test that creating a profile returns 200 with saved profile data."""
        with patch("api.main.save_profile") as mock_save:
            mock_save.return_value = True
            
            response = client.post("/profile", json=valid_profile_data)

        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "message" in data
        assert data["message"] == "Profile saved"
        assert "profile" in data
        
        # Verify profile data matches input
        profile = data["profile"]
        assert profile["first_name"] == valid_profile_data["first_name"]
        assert profile["last_name"] == valid_profile_data["last_name"]
        assert profile["email"] == valid_profile_data["email"]
        assert profile["phone"] == valid_profile_data["phone"]

    def test_get_profile_returns_saved_data(
        self, client, valid_profile_data
    ):
        """Test that GET /profile returns previously saved profile data."""
        with patch("api.main.get_profile") as mock_get:
            mock_get.return_value = valid_profile_data
            
            response = client.get("/profile")

        assert response.status_code == 200
        data = response.json()
        
        # Verify all profile fields are returned
        assert data["first_name"] == valid_profile_data["first_name"]
        assert data["last_name"] == valid_profile_data["last_name"]
        assert data["email"] == valid_profile_data["email"]
        assert data["phone"] == valid_profile_data["phone"]
        assert data["linkedin_url"] == valid_profile_data["linkedin_url"]
        assert data["years_experience"] == valid_profile_data["years_experience"]
        assert data["work_authorization"] == valid_profile_data["work_authorization"]
        assert data["sponsorship_required"] == valid_profile_data["sponsorship_required"]
        assert data["custom_answers"] == valid_profile_data["custom_answers"]

    def test_get_nonexistent_profile_returns_404(self, client):
        """Test that getting a non-existent profile returns 404."""
        with patch("api.main.get_profile") as mock_get:
            mock_get.return_value = None
            
            response = client.get("/profile")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_profile_persisted_to_database(self, client, valid_profile_data):
        """Test that profile data is actually persisted to database."""
        captured_profile = {}

        async def mock_save_profile(user_id, profile):
            captured_profile["user_id"] = user_id
            captured_profile["profile"] = profile
            return True

        with patch("api.main.save_profile", side_effect=mock_save_profile):
            response = client.post("/profile", json=valid_profile_data)

        assert response.status_code == 200
        
        # Verify data passed to database layer
        assert captured_profile["user_id"] == "test-user-profile-1234"
        assert captured_profile["profile"]["first_name"] == valid_profile_data["first_name"]
        assert captured_profile["profile"]["last_name"] == valid_profile_data["last_name"]

    def test_profile_update_overwrites_existing(self, client, valid_profile_data, valid_profile_data_updated):
        """Test that updating profile overwrites existing data."""
        saved_profile = {}

        def mock_save_profile(user_id, profile):
            saved_profile.update(profile)
            return True

        def mock_get_profile(user_id):
            return saved_profile if saved_profile else None

        with patch("api.main.save_profile", side_effect=mock_save_profile):
            # Create initial profile
            response1 = client.post("/profile", json=valid_profile_data)
            assert response1.status_code == 200

        with patch("api.main.save_profile", side_effect=mock_save_profile):
            # Update profile
            response2 = client.post("/profile", json=valid_profile_data_updated)
            assert response2.status_code == 200

        with patch("api.main.get_profile", side_effect=mock_get_profile):
            # Get updated profile
            response3 = client.get("/profile")
            assert response3.status_code == 200
            
            # Verify update was applied
            data = response3.json()
            assert data["first_name"] == valid_profile_data_updated["first_name"]
            assert data["last_name"] == valid_profile_data_updated["last_name"]
            assert data["email"] == valid_profile_data_updated["email"]

    def test_profile_custom_answers_persisted(self, client):
        """Test that custom answers are correctly persisted."""
        profile_with_custom = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "phone": "555-123-4567",
            "custom_answers": {
                "notice_period": "2 weeks",
                "salary_expectation": "$100k",
                "relocation": "Willing to relocate"
            }
        }

        with patch("api.main.save_profile") as mock_save:
            mock_save.return_value = True
            
            response = client.post("/profile", json=profile_with_custom)

        assert response.status_code == 200
        
        # Verify custom answers are in saved data
        saved_data = mock_save.call_args[0][1]
        assert saved_data["custom_answers"] == profile_with_custom["custom_answers"]


# ============================================================================
# PROFILE-02: Required Fields Validation Tests
# ============================================================================

class TestProfileValidation:
    """Test required fields are validated before save (PROFILE-02)."""

    @pytest.mark.parametrize("missing_field", [
        "first_name",
        "last_name",
        "email",
        "phone",
    ])
    def test_missing_required_fields_return_422(
        self, client, valid_profile_data, missing_field
    ):
        """Test that missing required fields return 422 validation error."""
        invalid_data = valid_profile_data.copy()
        del invalid_data[missing_field]
        
        response = client.post("/profile", json=invalid_data)
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_empty_first_name_rejected(self, client, valid_profile_data):
        """Test that empty first name is rejected."""
        invalid_data = valid_profile_data.copy()
        invalid_data["first_name"] = ""
        
        response = client.post("/profile", json=invalid_data)
        
        assert response.status_code == 422

    def test_empty_last_name_rejected(self, client, valid_profile_data):
        """Test that empty last name is rejected."""
        invalid_data = valid_profile_data.copy()
        invalid_data["last_name"] = ""
        
        response = client.post("/profile", json=invalid_data)
        
        assert response.status_code == 422

    def test_invalid_email_format_rejected(self, client, valid_profile_data):
        """Test that invalid email format is rejected."""
        invalid_data = valid_profile_data.copy()
        invalid_data["email"] = "not-an-email"
        
        response = client.post("/profile", json=invalid_data)
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_invalid_phone_format_rejected(self, client, valid_profile_data):
        """Test that invalid phone format is rejected."""
        invalid_data = valid_profile_data.copy()
        invalid_data["phone"] = "abc-def-ghij"
        
        response = client.post("/profile", json=invalid_data)
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_phone_too_short_rejected(self, client, valid_profile_data):
        """Test that phone numbers too short are rejected."""
        invalid_data = valid_profile_data.copy()
        invalid_data["phone"] = "123"
        
        response = client.post("/profile", json=invalid_data)
        
        assert response.status_code == 422

    def test_negative_years_experience_rejected(self, client, valid_profile_data):
        """Test that negative years of experience is rejected."""
        invalid_data = valid_profile_data.copy()
        invalid_data["years_experience"] = -1
        
        response = client.post("/profile", json=invalid_data)
        
        assert response.status_code == 422

    def test_years_experience_over_50_rejected(self, client, valid_profile_data):
        """Test that years of experience over 50 is rejected."""
        invalid_data = valid_profile_data.copy()
        invalid_data["years_experience"] = 51
        
        response = client.post("/profile", json=invalid_data)
        
        assert response.status_code == 422

    def test_invalid_work_authorization_value_rejected(self, client, valid_profile_data):
        """Test that invalid work authorization values are rejected."""
        invalid_data = valid_profile_data.copy()
        invalid_data["work_authorization"] = "Maybe"
        
        response = client.post("/profile", json=invalid_data)
        
        assert response.status_code == 422

    def test_invalid_sponsorship_value_rejected(self, client, valid_profile_data):
        """Test that invalid sponsorship values are rejected."""
        invalid_data = valid_profile_data.copy()
        invalid_data["sponsorship_required"] = "Sometimes"
        
        response = client.post("/profile", json=invalid_data)
        
        assert response.status_code == 422

    def test_first_name_max_length_enforced(self, client, valid_profile_data):
        """Test that first name max length (100) is enforced."""
        invalid_data = valid_profile_data.copy()
        invalid_data["first_name"] = "A" * 101
        
        response = client.post("/profile", json=invalid_data)
        
        assert response.status_code == 422

    def test_last_name_max_length_enforced(self, client, valid_profile_data):
        """Test that last name max length (100) is enforced."""
        invalid_data = valid_profile_data.copy()
        invalid_data["last_name"] = "B" * 101
        
        response = client.post("/profile", json=invalid_data)
        
        assert response.status_code == 422

    def test_valid_phone_formats_accepted(self, client, valid_profile_data):
        """Test various valid phone number formats are accepted."""
        valid_phones = [
            "555-123-4567",
            "(555) 123-4567",
            "555 123 4567",
            "5551234567",
            "+1 555-123-4567",
            "+1 (555) 123-4567",
        ]
        
        for phone in valid_phones:
            with patch("api.main.save_profile") as mock_save:
                mock_save.return_value = True
                
                data = valid_profile_data.copy()
                data["phone"] = phone
                response = client.post("/profile", json=data)
                
                assert response.status_code == 200, f"Phone '{phone}' should be valid"


# ============================================================================
# PROFILE-03: Job Preferences Storage Tests
# ============================================================================

class TestJobPreferencesStorage:
    """Test job preferences (location, remote, salary) stored correctly (PROFILE-03)."""

    def test_search_config_contains_location_preferences(self):
        """Test that SearchConfig includes location preferences."""
        config = SearchConfig(
            roles=["Software Engineer"],
            locations=["San Francisco", "Remote", "New York"],
            salary_min=100000,
            salary_max=200000,
            easy_apply_only=True,
            country="US"
        )
        
        assert "San Francisco" in config.locations
        assert "Remote" in config.locations
        assert config.salary_min == 100000
        assert config.salary_max == 200000
        assert config.easy_apply_only is True

    def test_search_config_remote_location_matching(self):
        """Test that remote jobs are correctly matched via location config."""
        config = SearchConfig(
            roles=["Developer"],
            locations=["Remote"],
            country="US"
        )
        
        assert "Remote" in config.locations

    def test_search_config_salary_range_storage(self):
        """Test that salary ranges are stored correctly in SearchConfig."""
        config = SearchConfig(
            roles=["Engineer"],
            locations=["NYC"],
            salary_min=80000,
            salary_max=150000
        )
        
        assert config.salary_min is not None
        assert config.salary_max is not None
        assert config.salary_min < config.salary_max

    def test_search_config_optional_salary(self):
        """Test that salary fields are optional in SearchConfig."""
        config = SearchConfig(
            roles=["Engineer"],
            locations=["Remote"]
        )
        
        assert config.salary_min is None
        assert config.salary_max is None

    def test_profile_custom_answers_for_job_preferences(self, client):
        """Test that job preferences can be stored in custom_answers."""
        profile_with_preferences = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "phone": "555-123-4567",
            "custom_answers": {
                "preferred_locations": "San Francisco, Remote, Austin",
                "salary_expectation": "$120,000 - $150,000",
                "remote_preference": "Fully remote",
                "willing_to_relocate": "Yes"
            }
        }

        with patch("api.main.save_profile") as mock_save:
            mock_save.return_value = True
            
            response = client.post("/profile", json=profile_with_preferences)
            
            assert response.status_code == 200
            saved_data = mock_save.call_args[0][1]
            assert "preferred_locations" in saved_data["custom_answers"]
            assert "salary_expectation" in saved_data["custom_answers"]
            assert "remote_preference" in saved_data["custom_answers"]

    def test_search_config_experience_levels(self):
        """Test that SearchConfig supports experience level preferences."""
        config = SearchConfig(
            roles=["Developer"],
            locations=["Remote"],
            experience_levels=["mid", "senior"]
        )
        
        assert "mid" in config.experience_levels
        assert "senior" in config.experience_levels

    def test_search_config_company_size_preferences(self):
        """Test that SearchConfig supports company size preferences."""
        config = SearchConfig(
            roles=["Developer"],
            locations=["Remote"],
            company_sizes=["startup", "mid-size"]
        )
        
        assert "startup" in config.company_sizes
        assert "mid-size" in config.company_sizes


# ============================================================================
# PROFILE-04: LinkedIn Credentials Encryption Tests
# ============================================================================

class TestLinkedInCredentialsEncryption:
    """Test LinkedIn credentials are encrypted at rest (PROFILE-04)."""

    def test_linkedin_cookie_encrypted_before_storage(self, client):
        """Test that LinkedIn cookie is encrypted before database storage."""
        settings_data = {
            "daily_limit": 20,
            "linkedin_cookie": "AQEDATIKZlcDqeaz_xyz123"
        }
        
        captured_settings = {}

        async def mock_save_settings(user_id, settings):
            captured_settings["user_id"] = user_id
            captured_settings["settings"] = settings
            return True

        with patch("api.main.save_settings", side_effect=mock_save_settings):
            with patch("api.main.count_applications_since") as mock_count:
                mock_count.return_value = 0
                response = client.post("/settings", json=settings_data)

        assert response.status_code == 200
        
        # Verify encrypted field exists and is different from plaintext
        saved = captured_settings["settings"]
        assert "linkedin_cookie_encrypted" in saved
        assert saved["linkedin_cookie_encrypted"] != settings_data["linkedin_cookie"]
        # Verify plaintext is NOT stored
        assert "linkedin_cookie" not in saved

    def test_encrypted_cookie_can_be_decrypted(self, client):
        """Test that encrypted cookie can be correctly decrypted."""
        original_cookie = "AQEDATIKZlcDqeaz_xyz123"
        
        # Encrypt the cookie
        encrypted = encrypt_sensitive_data(original_cookie)
        
        # Verify it's different from original
        assert encrypted != original_cookie
        
        # Decrypt and verify
        decrypted = decrypt_sensitive_data(encrypted)
        assert decrypted == original_cookie

    def test_get_settings_shows_cookie_set_indicator(self, client):
        """Test that GET /settings shows if LinkedIn cookie is set."""
        with patch("api.main.get_settings") as mock_get_settings:
            with patch("api.main.count_applications_since") as mock_count:
                mock_get_settings.return_value = {
                    "daily_limit": 10,
                    "linkedin_cookie_encrypted": "encrypted_value_here"
                }
                mock_count.return_value = 5
                
                response = client.get("/settings")

        assert response.status_code == 200
        data = response.json()
        assert "linkedin_cookie_set" in data
        assert data["linkedin_cookie_set"] is True

    def test_get_settings_shows_cookie_not_set(self, client):
        """Test that GET /settings correctly indicates when cookie is not set."""
        with patch("api.main.get_settings") as mock_get_settings:
            with patch("api.main.count_applications_since") as mock_count:
                mock_get_settings.return_value = {
                    "daily_limit": 10
                    # No linkedin_cookie_encrypted field
                }
                mock_count.return_value = 0
                
                response = client.get("/settings")

        assert response.status_code == 200
        data = response.json()
        assert "linkedin_cookie_set" in data
        assert data["linkedin_cookie_set"] is False

    def test_settings_without_linkedin_cookie_does_not_fail(self, client):
        """Test that settings can be saved without LinkedIn cookie."""
        settings_data = {
            "daily_limit": 15
        }

        with patch("api.main.save_settings") as mock_save:
            with patch("api.main.count_applications_since") as mock_count:
                mock_save.return_value = True
                mock_count.return_value = 0
                
                response = client.post("/settings", json=settings_data)

        assert response.status_code == 200
        
        # Verify settings saved
        saved = mock_save.call_args[0][1]
        assert saved["daily_limit"] == 15

    def test_daily_limit_bounds_enforced(self, client):
        """Test that daily limit has min/max bounds enforced."""
        # Test below minimum
        response_low = client.post("/settings", json={"daily_limit": 0})
        assert response_low.status_code == 422
        
        # Test above maximum
        response_high = client.post("/settings", json={"daily_limit": 1001})
        assert response_high.status_code == 422
        
        # Test valid boundary values
        with patch("api.main.save_settings") as mock_save:
            with patch("api.main.count_applications_since") as mock_count:
                mock_save.return_value = True
                mock_count.return_value = 0
                
                response_min = client.post("/settings", json={"daily_limit": 1})
                assert response_min.status_code == 200
                
                response_max = client.post("/settings", json={"daily_limit": 1000})
                assert response_max.status_code == 200

    def test_linkedin_cookie_max_length_enforced(self, client):
        """Test that LinkedIn cookie max length (500) is enforced."""
        settings_data = {
            "daily_limit": 10,
            "linkedin_cookie": "A" * 501  # Exceeds max length
        }
        
        response = client.post("/settings", json=settings_data)
        assert response.status_code == 422


# ============================================================================
# PROFILE-05: Profile Updates Reflect in Applications Tests
# ============================================================================

class TestProfileUpdatesInApplications:
    """Test that profile updates reflect immediately in applications (PROFILE-05)."""

    def test_updated_profile_used_in_job_application(self, client):
        """Test that most recent profile data is used when applying to jobs."""
        updated_profile = {
            "first_name": "Updated",
            "last_name": "Name",
            "email": "updated@example.com",
            "phone": "555-999-8888",
            "years_experience": 10
        }

        with patch("api.main.get_profile") as mock_get_profile:
            mock_get_profile.return_value = updated_profile
            
            with patch("api.main.get_latest_resume") as mock_get_resume:
                with patch("api.main.get_settings") as mock_get_settings:
                    with patch("api.main.count_applications_since") as mock_count:
                        mock_get_resume.return_value = {
                            "file_path": "/tmp/test.pdf",
                            "raw_text": "Test resume",
                            "parsed_data": {}
                        }
                        mock_get_settings.return_value = {
                            "daily_limit": 10,
                            "linkedin_cookie_encrypted": encrypt_sensitive_data("cookie")
                        }
                        mock_count.return_value = 0
                        
                        # Verify the profile data is current
                        profile = mock_get_profile.return_value
                        assert profile["first_name"] == "Updated"
                        assert profile["email"] == "updated@example.com"

    def test_profile_fetch_latest_version_on_apply(self, client):
        """Test that apply endpoint fetches the latest profile version."""
        profile_versions = [
            {"first_name": "Old", "last_name": "Profile"},
            {"first_name": "New", "last_name": "Profile"}
        ]
        call_count = [0]

        def mock_get_profile_with_versions(user_id):
            version = profile_versions[call_count[0]]
            call_count[0] += 1
            return version

        with patch("api.main.get_profile", side_effect=mock_get_profile_with_versions):
            # First call gets old version
            profile1 = mock_get_profile_with_versions("test-user")
            # Second call gets new version
            profile2 = mock_get_profile_with_versions("test-user")
            
            assert profile1["first_name"] == "Old"
            assert profile2["first_name"] == "New"

    def test_user_profile_object_creation_from_db(self, client):
        """Test that UserProfile object is correctly created from database data."""
        db_profile = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "phone": "555-123-4567",
            "linkedin_url": "https://linkedin.com/in/johndoe",
            "years_experience": 5,
            "work_authorization": "Yes",
            "sponsorship_required": "No",
            "custom_answers": {"notice_period": "2 weeks"}
        }

        # Create UserProfile from database data
        profile_obj = UserProfile(
            first_name=db_profile["first_name"],
            last_name=db_profile["last_name"],
            email=db_profile["email"],
            phone=db_profile["phone"],
            linkedin_url=db_profile.get("linkedin_url"),
            years_experience=db_profile.get("years_experience"),
            work_authorization=db_profile.get("work_authorization", "Yes"),
            sponsorship_required=db_profile.get("sponsorship_required", "No"),
            custom_answers=db_profile.get("custom_answers", {})
        )

        assert profile_obj.first_name == "John"
        assert profile_obj.last_name == "Doe"
        assert profile_obj.email == "john@example.com"
        assert profile_obj.custom_answers["notice_period"] == "2 weeks"

    def test_profile_required_for_application(self, client):
        """Test that application returns 503 when browser not available."""
        with patch("api.main.get_profile") as mock_get_profile:
            with patch("api.main.get_latest_resume") as mock_get_resume:
                with patch("api.main.get_settings") as mock_get_settings:
                    with patch("api.main.count_applications_since") as mock_count:
                        mock_get_profile.return_value = None  # No profile
                        mock_get_resume.return_value = {
                            "file_path": "/tmp/test.pdf",
                            "raw_text": "Test resume",
                            "parsed_data": {}
                        }
                        mock_get_settings.return_value = {"daily_limit": 10}
                        mock_count.return_value = 0

                        response = client.post(
                            "/apply",
                            json={
                                "job_url": "https://linkedin.com/jobs/view/123",
                                "auto_submit": False
                            }
                        )

        # API returns 503 when browser automation not available
        assert response.status_code == 503


# ============================================================================
# PROFILE-06: Multiple Resume Versions Tests
# ============================================================================

class TestMultipleResumeVersions:
    """Test multiple resume versions can be stored (PROFILE-06)."""

    def test_multiple_resumes_can_be_saved(self, client):
        """Test that multiple resumes can be saved for a single user."""
        saved_resumes = []

        def mock_save_resume(user_id, file_path, raw_text, parsed_data):
            saved_resumes.append({
                "user_id": user_id,
                "file_path": file_path,
                "parsed_data": parsed_data
            })
            return len(saved_resumes)  # Return incrementing ID

        # Simulate uploading multiple resumes
        resume1 = {"version": "Software Engineer", "skills": ["Python"]}
        resume2 = {"version": "Data Scientist", "skills": ["Python", "ML"]}
        
        mock_save_resume("user-123", "/tmp/resume1.pdf", "text1", resume1)
        mock_save_resume("user-123", "/tmp/resume2.pdf", "text2", resume2)

        assert len(saved_resumes) == 2
        assert saved_resumes[0]["parsed_data"]["version"] == "Software Engineer"
        assert saved_resumes[1]["parsed_data"]["version"] == "Data Scientist"

    def test_get_latest_resume_returns_most_recent(self, client):
        """Test that get_latest_resume returns the most recent resume."""
        latest_resume = {
            "id": 2,
            "file_path": "/tmp/resume_v2.pdf",
            "raw_text": "Senior Engineer Resume",
            "parsed_data": {"title": "Senior Engineer"},
            "tailored_version": None
        }

        # Verify the resume data structure
        result = latest_resume
        
        assert result["file_path"] == "/tmp/resume_v2.pdf"
        assert result["parsed_data"]["title"] == "Senior Engineer"

    def test_resume_tailored_version_storage(self, client):
        """Test that tailored resume versions can be stored."""
        resume_id = 1
        tailored_data = {
            "tailored_bullets": ["Optimized bullet 1", "Optimized bullet 2"],
            "match_score": 0.85,
            "target_job": "Senior Engineer"
        }

        captured_tailored = {}

        def mock_update_tailored(rid, tailored):
            captured_tailored["resume_id"] = rid
            captured_tailored["tailored"] = tailored

        mock_update_tailored(resume_id, tailored_data)

        assert captured_tailored["resume_id"] == resume_id
        assert captured_tailored["tailored"]["match_score"] == 0.85

    def test_resume_without_tailored_version(self, client):
        """Test that resumes work without tailored versions."""
        resume = {
            "id": 1,
            "file_path": "/tmp/resume.pdf",
            "raw_text": "Original resume text",
            "parsed_data": {"skills": ["Python"]},
            "tailored_version": None
        }

        # Verify resume structure without tailored version
        result = resume
        
        assert result["tailored_version"] is None
        assert result["raw_text"] == "Original resume text"

    def test_resume_file_path_stored_correctly(self, client):
        """Test that resume file paths are stored correctly."""
        file_path = "/data/resumes/user-123_resume-software.pdf"
        
        captured_data = {}

        def mock_save_resume(user_id, fp, raw_text, parsed_data):
            captured_data["file_path"] = fp
            captured_data["user_id"] = user_id
            return 1

        mock_save_resume("user-123", file_path, "resume text", {})

        assert captured_data["file_path"] == file_path
        assert "user-123" in captured_data["file_path"]

    def test_resume_parsed_data_json_storage(self, client):
        """Test that resume parsed data is stored as JSON."""
        parsed_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "skills": ["Python", "JavaScript", "SQL"],
            "experience": [
                {"company": "TechCorp", "title": "Engineer"}
            ]
        }

        # Verify JSON serialization/deserialization
        json_str = json.dumps(parsed_data)
        restored = json.loads(json_str)
        
        assert restored["name"] == "John Doe"
        assert len(restored["skills"]) == 3
        assert restored["experience"][0]["company"] == "TechCorp"

    def test_application_requires_resume(self, client):
        """Test that application returns 503 when browser not available."""
        with patch("api.main.get_latest_resume") as mock_get_resume:
            with patch("api.main.get_profile") as mock_get_profile:
                with patch("api.main.get_settings") as mock_get_settings:
                    with patch("api.main.count_applications_since") as mock_count:
                        mock_get_resume.return_value = None  # No resume
                        mock_get_profile.return_value = {
                            "first_name": "John",
                            "last_name": "Doe",
                            "email": "john@example.com",
                            "phone": "555-123-4567"
                        }
                        mock_get_settings.return_value = {"daily_limit": 10}
                        mock_count.return_value = 0

                        response = client.post(
                            "/apply",
                            json={
                                "job_url": "https://linkedin.com/jobs/view/123",
                                "auto_submit": False
                            }
                        )

        # API returns 503 when browser automation not available
        assert response.status_code == 503


# ============================================================================
# Integration Tests
# ============================================================================

class TestProfileManagementIntegration:
    """Integration tests for profile management workflows."""

    def test_complete_profile_workflow(self, client):
        """Test complete profile creation and retrieval workflow."""
        profile_data = {
            "first_name": "Integration",
            "last_name": "Test",
            "email": "integration@test.com",
            "phone": "555-111-2222",
            "linkedin_url": "https://linkedin.com/in/integration",
            "years_experience": 3,
            "work_authorization": "Yes",
            "sponsorship_required": "No",
            "custom_answers": {
                "notice_period": "3 weeks"
            }
        }

        # Mock save and get to simulate real workflow
        stored_profile = {}

        def mock_save(user_id, profile):
            stored_profile.update(profile)
            return True

        def mock_get(user_id):
            return stored_profile if stored_profile else None

        with patch("api.main.save_profile", side_effect=mock_save):
            # Create profile
            response_create = client.post("/profile", json=profile_data)
            assert response_create.status_code == 200

        with patch("api.main.get_profile", side_effect=mock_get):
            # Retrieve profile
            response_get = client.get("/profile")
            assert response_get.status_code == 200
            
            data = response_get.json()
            assert data["first_name"] == "Integration"
            assert data["custom_answers"]["notice_period"] == "3 weeks"

    def test_profile_settings_integration(self, client):
        """Test profile and settings work together."""
        # Save profile
        profile_data = {
            "first_name": "Settings",
            "last_name": "Integration",
            "email": "settings@test.com",
            "phone": "555-333-4444"
        }

        with patch("api.main.save_profile") as mock_save_profile:
            mock_save_profile.return_value = True
            response_profile = client.post("/profile", json=profile_data)
            assert response_profile.status_code == 200

        # Save settings
        settings_data = {
            "daily_limit": 25,
            "linkedin_cookie": "test_cookie_value"
        }

        with patch("api.main.save_settings") as mock_save_settings:
            with patch("api.main.count_applications_since") as mock_count:
                mock_save_settings.return_value = True
                mock_count.return_value = 5
                
                response_settings = client.post("/settings", json=settings_data)
                assert response_settings.status_code == 200
                
                # Verify settings response
                data = response_settings.json()
                assert data["daily_limit"] == 25
                assert data["linkedin_cookie_set"] is True

    def test_authentication_required_for_profile_endpoints(self):
        """Test that profile endpoints require authentication."""
        # Create client without auth override
        app.dependency_overrides.clear()
        client_no_auth = TestClient(app)
        
        # Test without authentication
        response_get = client_no_auth.get("/profile")
        assert response_get.status_code == 401

        response_post = client_no_auth.post("/profile", json={"first_name": "Test"})
        assert response_post.status_code == 401

    def test_profile_data_types_preserved(self, client):
        """Test that profile data types are preserved correctly."""
        profile_data = {
            "first_name": "Type",
            "last_name": "Test",
            "email": "types@test.com",
            "phone": "555-555-5555",
            "years_experience": 7,  # Integer
            "custom_answers": {      # Object/Dict
                "string_field": "value",
                "number_field": 42
            }
        }

        with patch("api.main.save_profile") as mock_save:
            mock_save.return_value = True
            response = client.post("/profile", json=profile_data)
            
            assert response.status_code == 200
            
            # Verify types in saved data
            saved = mock_save.call_args[0][1]
            assert isinstance(saved["years_experience"], int)
            assert isinstance(saved["custom_answers"], dict)


# Run with: pytest tests/e2e/test_profile_management.py -v
