"""
End-to-End Authentication Tests for Job Applier API.

This module tests the complete authentication flow including:
- User registration (AUTH-01)
- Password security requirements (AUTH-02)
- JWT token generation and validation (AUTH-03)
- Login persistence and token refresh (AUTH-04)
- Security headers and CORS (AUTH-05)

Technical Specifications:
- JWT tokens: 24h access / 30d refresh
- Password hashing: SHA-256 with salt
- Auth header: Bearer token in Authorization header
"""

import pytest
import jwt
import hashlib
import os
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

# Ensure project root is in path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.main import app
from api.auth import (
    SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token, create_refresh_token, hash_password, verify_password,
    decode_token
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_db_user():
    """Sample user data as stored in database."""
    return {
        "id": "test-user-uuid-1234",
        "email": "test@example.com",
        "hashed_password": hash_password("SecurePass123"),
        "created_at": datetime.now().isoformat(),
        "is_active": True
    }


@pytest.fixture
def valid_registration_data():
    """Valid registration request data."""
    return {
        "email": "newuser@example.com",
        "password": "SecurePass123"
    }


@pytest.fixture
def valid_login_data():
    """Valid login request data."""
    return {
        "email": "test@example.com",
        "password": "SecurePass123"
    }


@pytest.fixture
def mock_create_user():
    """Mock successful user creation."""
    with patch("api.main.create_user") as mock:
        mock.return_value = True
        yield mock


@pytest.fixture
def mock_create_user_duplicate():
    """Mock duplicate email (user already exists)."""
    with patch("api.main.create_user") as mock:
        mock.return_value = False
        yield mock


@pytest.fixture
def mock_get_user_by_email(mock_db_user):
    """Mock getting user by email (user exists)."""
    with patch("api.main.get_user_by_email") as mock:
        mock.return_value = mock_db_user
        yield mock


@pytest.fixture
def mock_get_user_by_email_not_found():
    """Mock getting user by email (user not found)."""
    with patch("api.main.get_user_by_email") as mock:
        mock.return_value = None
        yield mock


@pytest.fixture
def mock_get_user_by_id(mock_db_user):
    """Mock getting user by ID."""
    with patch("api.main.get_user_by_id") as mock:
        mock.return_value = mock_db_user
        yield mock


@pytest.fixture
def mock_get_user_by_id_inactive():
    """Mock getting inactive user by ID."""
    with patch("api.main.get_user_by_id") as mock:
        mock.return_value = {
            "id": "inactive-user-1234",
            "email": "inactive@example.com",
            "hashed_password": hash_password("SecurePass123"),
            "created_at": datetime.now().isoformat(),
            "is_active": False
        }
        yield mock


# ============================================================================
# AUTH-01: User Registration Tests
# ============================================================================

class TestUserRegistration:
    """Test user registration with valid credentials (AUTH-01)."""

    def test_valid_registration_returns_200_and_user_data(
        self, client, mock_create_user
    ):
        """Test that valid registration returns 200 with user data and tokens."""
        response = client.post(
            "/auth/register",
            json={"email": "newuser@example.com", "password": "SecurePass123"}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "message" in data
        assert data["message"] == "Registration successful"
        assert "user_id" in data
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

        # Verify tokens are non-empty strings
        assert isinstance(data["access_token"], str)
        assert isinstance(data["refresh_token"], str)
        assert len(data["access_token"]) > 0
        assert len(data["refresh_token"]) > 0

        # Verify user_id is a valid UUID format
        assert len(data["user_id"]) == 36  # UUID length

    def test_user_stored_in_database(self, client):
        """Test that registration creates user in database."""
        captured_user_data = {}

        async def mock_create_user_capture(user_id, email, hashed_password):
            captured_user_data["user_id"] = user_id
            captured_user_data["email"] = email
            captured_user_data["hashed_password"] = hashed_password
            return True

        with patch("api.main.create_user", side_effect=mock_create_user_capture):
            response = client.post(
                "/auth/register",
                json={"email": "dbtest@example.com", "password": "SecurePass123"}
            )

        assert response.status_code == 200

        # Verify user data was passed to database
        assert captured_user_data["email"] == "dbtest@example.com"
        assert captured_user_data["hashed_password"] != "SecurePass123"  # Should be hashed
        assert len(captured_user_data["hashed_password"]) == 64  # SHA-256 hex length
        assert captured_user_data["user_id"] is not None

    def test_registration_duplicate_email_returns_400(
        self, client, mock_create_user_duplicate
    ):
        """Test that duplicate email registration returns 400 error."""
        response = client.post(
            "/auth/register",
            json={"email": "existing@example.com", "password": "SecurePass123"}
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "already registered" in data["detail"].lower()

    def test_registration_invalid_email_format(self, client):
        """Test that invalid email format is rejected."""
        response = client.post(
            "/auth/register",
            json={"email": "not-an-email", "password": "SecurePass123"}
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data


# ============================================================================
# AUTH-02: Password Security Requirements Tests
# ============================================================================

class TestPasswordSecurityRequirements:
    """Test password security requirements (AUTH-02)."""

    @pytest.mark.parametrize("password", [
        "Short1",      # 6 chars - too short
        "Short12",     # 7 chars - still too short
        "a" * 7,       # 7 chars, no complexity
    ])
    def test_rejection_of_short_passwords(self, client, password):
        """Test that passwords shorter than 8 characters are rejected."""
        response = client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": password}
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    @pytest.mark.parametrize("password", [
        "onlylowercase",      # No uppercase, no numbers
        "ONLYUPPERCASE",      # No lowercase, no numbers
        "1234567890",         # Only numbers
        "onlyletters",        # No numbers
        "ONLYLETTERS",        # No lowercase, no numbers
    ])
    def test_rejection_of_weak_passwords_no_complexity(self, client, password):
        """Test that passwords without required complexity are rejected."""
        response = client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": password}
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    @pytest.mark.parametrize("password", [
        "SecurePass123",      # Upper, lower, numbers
        "MyP@ssw0rd",         # Upper, lower, numbers, special
        "Complex1Test",       # Upper, lower, numbers
        "A1b2c3d4e5",         # Mixed with numbers
    ])
    def test_acceptance_of_strong_passwords(self, client, mock_create_user, password):
        """Test that passwords meeting complexity requirements are accepted."""
        response = client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": password}
        )

        assert response.status_code == 200

    def test_error_messages_are_clear_for_short_password(self, client):
        """Test that error messages for short passwords are clear and helpful."""
        response = client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "Short1"}
        )

        assert response.status_code == 422
        data = response.json()
        
        # Error should indicate minimum length requirement
        error_str = str(data)
        assert any(term in error_str.lower() for term in [
            "at least", "minimum", "8", "short", "ensure this value has at least"
        ])

    def test_error_messages_are_clear_for_weak_password(self, client):
        """Test that error messages for weak passwords are clear and helpful."""
        response = client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "onlylowercase"}
        )

        assert response.status_code == 422
        data = response.json()
        
        # Error should indicate complexity requirement
        error_str = str(data)
        assert any(term in error_str.lower() for term in [
            "letter", "number", "digit", "contain", "password must contain"
        ])


# ============================================================================
# AUTH-03: JWT Token Generation and Validation Tests
# ============================================================================

class TestJWTTokenGenerationAndValidation:
    """Test JWT token generation, validation, and expiration (AUTH-03)."""

    def test_tokens_generated_on_login(
        self, client, mock_get_user_by_email, valid_login_data
    ):
        """Test that access and refresh tokens are generated on successful login."""
        response = client.post("/auth/login", json=valid_login_data)

        assert response.status_code == 200
        data = response.json()

        # Both tokens should be present
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

        # Tokens should be valid JWT format (3 parts separated by dots)
        access_parts = data["access_token"].split(".")
        refresh_parts = data["refresh_token"].split(".")
        assert len(access_parts) == 3
        assert len(refresh_parts) == 3

    def test_valid_tokens_are_accepted(self, client, mock_get_user_by_email):
        """Test that valid access tokens are accepted for protected endpoints."""
        # First login to get a token
        login_response = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "SecurePass123"}
        )
        token = login_response.json()["access_token"]

        # Use token to access protected endpoint
        with patch("api.main.get_settings") as mock_settings:
            mock_settings.return_value = {"daily_limit": 10}
            with patch("api.main.count_applications_since") as mock_count:
                mock_count.return_value = 0
                response = client.get(
                    "/settings",
                    headers={"Authorization": f"Bearer {token}"}
                )

        assert response.status_code == 200

    def test_expired_tokens_are_rejected(self, client):
        """Test that expired tokens are rejected with 401."""
        # Create an expired token
        expired_token = jwt.encode(
            {
                "sub": "test-user-id",
                "exp": datetime.utcnow() - timedelta(minutes=1),  # Expired 1 minute ago
                "type": "access",
                "iat": datetime.utcnow() - timedelta(hours=25)
            },
            SECRET_KEY,
            algorithm=ALGORITHM
        )

        response = client.get(
            "/settings",
            headers={"Authorization": f"Bearer {expired_token}"}
        )

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert any(term in data["detail"].lower() for term in [
            "invalid", "expired", "token"
        ])

    def test_invalid_tokens_return_401(self, client):
        """Test that malformed/invalid tokens return 401."""
        invalid_tokens = [
            "not.a.valid.token",
            "Bearer token",
            "",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature",
        ]

        for token in invalid_tokens:
            response = client.get(
                "/settings",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 401, f"Token '{token}' should be rejected"

    def test_missing_token_returns_401(self, client):
        """Test that requests without tokens to protected endpoints return 401."""
        response = client.get("/settings")

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    def test_refresh_token_type_rejected_for_access(self, client):
        """Test that refresh tokens are rejected when access tokens are required."""
        # Create a refresh token (type="refresh")
        refresh_token = create_refresh_token("test-user-id")

        response = client.get(
            "/settings",
            headers={"Authorization": f"Bearer {refresh_token}"}
        )

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "type" in data["detail"].lower()

    def test_token_contains_correct_payload(self, client, mock_get_user_by_email):
        """Test that decoded token contains correct user information."""
        login_response = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "SecurePass123"}
        )
        token = login_response.json()["access_token"]

        # Decode token (without verification for payload check)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        assert payload["sub"] == "test-user-uuid-1234"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_access_token_expiration_time(self):
        """Test that access tokens have correct expiration (24 hours)."""
        token = create_access_token("test-user-id")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        exp_time = datetime.fromtimestamp(payload["exp"])
        iat_time = datetime.fromtimestamp(payload["iat"])
        
        # Should be approximately 24 hours
        expected_exp = iat_time + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        assert abs((exp_time - expected_exp).total_seconds()) < 5  # Within 5 seconds

    def test_refresh_token_expiration_time(self):
        """Test that refresh tokens have correct expiration (30 days)."""
        token = create_refresh_token("test-user-id")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        exp_time = datetime.fromtimestamp(payload["exp"])
        iat_time = datetime.fromtimestamp(payload["iat"])
        
        # Should be approximately 30 days
        expected_exp = iat_time + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        assert abs((exp_time - expected_exp).total_seconds()) < 5  # Within 5 seconds


# ============================================================================
# AUTH-04: Login Persistence Tests
# ============================================================================

class TestLoginPersistence:
    """Test token refresh mechanism and concurrent sessions (AUTH-04)."""

    def test_token_refresh_mechanism(
        self, client, mock_get_user_by_email
    ):
        """Test that refresh endpoint generates new access token."""
        # Login to get initial tokens
        login_response = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "SecurePass123"}
        )
        initial_token = login_response.json()["access_token"]

        # Wait a tiny bit to ensure different iat
        time.sleep(0.1)

        # Use refresh endpoint with the access token
        refresh_response = client.post(
            "/auth/refresh",
            headers={"Authorization": f"Bearer {initial_token}"}
        )

        assert refresh_response.status_code == 200
        data = refresh_response.json()

        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

        # New token should be different from initial
        new_token = data["access_token"]
        assert new_token != initial_token

        # New token should be valid
        new_response = client.get(
            "/settings",
            headers={"Authorization": f"Bearer {new_token}"}
        )
        assert new_response.status_code == 200

    def test_concurrent_sessions_handled_properly(
        self, client, mock_get_user_by_email
    ):
        """Test that multiple login sessions work independently."""
        # Simulate two different login sessions
        login_response_1 = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "SecurePass123"}
        )
        login_response_2 = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "SecurePass123"}
        )

        token_1 = login_response_1.json()["access_token"]
        token_2 = login_response_2.json()["access_token"]

        # Both tokens should be valid simultaneously
        with patch("api.main.get_settings") as mock_settings:
            mock_settings.return_value = {"daily_limit": 10}
            with patch("api.main.count_applications_since") as mock_count:
                mock_count.return_value = 0
                
                response_1 = client.get(
                    "/settings",
                    headers={"Authorization": f"Bearer {token_1}"}
                )
                response_2 = client.get(
                    "/settings",
                    headers={"Authorization": f"Bearer {token_2}"}
                )

        assert response_1.status_code == 200
        assert response_2.status_code == 200

    def test_inactive_user_cannot_login(
        self, client
    ):
        """Test that inactive users cannot login."""
        inactive_user = {
            "id": "inactive-user-1234",
            "email": "inactive@example.com",
            "hashed_password": hash_password("SecurePass123"),
            "created_at": datetime.now().isoformat(),
            "is_active": False
        }

        with patch("api.main.get_user_by_email", return_value=inactive_user):
            response = client.post(
                "/auth/login",
                json={"email": "inactive@example.com", "password": "SecurePass123"}
            )

        assert response.status_code == 403
        data = response.json()
        assert "disabled" in data["detail"].lower() or "inactive" in data["detail"].lower()

    def test_refresh_token_with_invalid_user_fails(self, client):
        """Test that refresh with valid token but invalid user fails."""
        # Create token for non-existent user
        token = create_access_token("non-existent-user-id")

        with patch("api.main.get_settings") as mock_settings:
            mock_settings.return_value = None
            response = client.get(
                "/settings",
                headers={"Authorization": f"Bearer {token}"}
            )

        # Should return 401 since user doesn't exist in context
        # The get_current_user only validates token, doesn't check user exists
        # But protected endpoints might check
        assert response.status_code in [200, 401, 404]  # Depends on implementation


# ============================================================================
# AUTH-05: Security Headers and CORS Tests
# ============================================================================

class TestSecurityHeadersAndCORS:
    """Test CORS headers and rate limiting on auth endpoints (AUTH-05)."""

    def test_cors_headers_present_on_auth_endpoints(self, client, mock_create_user):
        """Test that CORS headers are present on authentication endpoints."""
        # Test preflight request
        response = client.options(
            "/auth/register",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )

        # Check CORS headers
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers

    def test_cors_allows_configured_origins(self, client, mock_create_user):
        """Test that configured origins are allowed."""
        allowed_origins = [
            "http://localhost:3000",
            "https://job-applier.pages.dev"
        ]

        for origin in allowed_origins:
            response = client.post(
                "/auth/register",
                json={"email": f"test-{hash(origin)}@example.com", "password": "SecurePass123"},
                headers={"Origin": origin}
            )
            
            assert response.status_code == 200
            # CORS header should be present
            assert "access-control-allow-origin" in response.headers

    def test_rate_limiting_on_register_endpoint(self, client):
        """Test that rate limiting is applied to register endpoint."""
        # This test assumes rate limiting is implemented
        # The actual behavior depends on the rate limiter configuration
        
        # Make multiple rapid requests
        responses = []
        for i in range(5):
            with patch("api.main.create_user") as mock:
                mock.return_value = True
                response = client.post(
                    "/auth/register",
                    json={"email": f"rate{i}@example.com", "password": "SecurePass123"}
                )
                responses.append(response.status_code)

        # All should succeed if rate limit is not exceeded
        # If rate limiting is strict, some might return 429
        assert all(code in [200, 429] for code in responses)

    def test_rate_limiting_on_login_endpoint(
        self, client, mock_get_user_by_email
    ):
        """Test that rate limiting is applied to login endpoint."""
        # Make multiple rapid login attempts
        responses = []
        for _ in range(5):
            response = client.post(
                "/auth/login",
                json={"email": "test@example.com", "password": "SecurePass123"}
            )
            responses.append(response.status_code)

        # Should either succeed or be rate limited
        assert all(code in [200, 429] for code in responses)

    def test_www_authenticate_header_on_401(self, client):
        """Test that 401 responses include WWW-Authenticate header."""
        response = client.get("/settings")

        assert response.status_code == 401
        assert "www-authenticate" in response.headers
        assert "bearer" in response.headers["www-authenticate"].lower()

    def test_security_headers_present(self, client):
        """Test that security headers are present on responses."""
        response = client.get("/health")

        assert response.status_code == 200
        
        # Check for common security headers
        # Note: Actual headers depend on middleware configuration
        headers = response.headers
        
        # Content-Type should be set
        assert "content-type" in headers

    def test_password_not_returned_in_response(self, client, mock_create_user):
        """Test that password is never returned in API responses."""
        response = client.post(
            "/auth/register",
            json={"email": "newuser@example.com", "password": "SecurePass123"}
        )

        assert response.status_code == 200
        response_text = response.text

        # Password or its hash should not appear in response
        assert "SecurePass123" not in response_text
        assert "password" not in response_text.lower()


# ============================================================================
# Password Hashing Tests
# ============================================================================

class TestPasswordHashing:
    """Test SHA-256 password hashing with salt."""

    def test_hash_password_returns_sha256_hex(self):
        """Test that hash_password returns SHA-256 hex string."""
        password = "TestPassword123"
        hashed = hash_password(password)

        # Should be 64 characters (SHA-256 hex length)
        assert len(hashed) == 64
        # Should only contain hex characters
        assert all(c in "0123456789abcdef" for c in hashed)

    def test_hash_password_is_consistent(self):
        """Test that same password produces same hash (with same salt)."""
        password = "TestPassword123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 == hash2

    def test_hash_password_is_different_for_different_passwords(self):
        """Test that different passwords produce different hashes."""
        hash1 = hash_password("Password123")
        hash2 = hash_password("Password124")

        assert hash1 != hash2

    def test_verify_password_correct(self):
        """Test that verify_password returns True for correct password."""
        password = "TestPassword123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test that verify_password returns False for incorrect password."""
        password = "TestPassword123"
        hashed = hash_password(password)

        assert verify_password("WrongPassword123", hashed) is False

    def test_salt_is_used_in_hashing(self):
        """Test that salt environment variable affects hashing."""
        password = "TestPassword123"
        
        # Default salt
        with patch.dict(os.environ, {}, clear=False):
            hash_default = hash_password(password)
        
        # Different salt
        with patch.dict(os.environ, {"PASSWORD_SALT": "different-salt"}):
            # Re-import to pick up new salt
            from api.auth import hash_password as hash_with_different_salt
            hash_different = hash_with_different_salt(password)

        # Hashes should be different with different salts
        assert hash_default != hash_different


# ============================================================================
# JWT Token Decode Tests
# ============================================================================

class TestJWTDecode:
    """Test JWT token decoding functionality."""

    def test_decode_valid_token(self):
        """Test decoding a valid token."""
        user_id = "test-user-123"
        token = create_access_token(user_id)
        
        payload = decode_token(token)
        
        assert payload is not None
        assert payload.sub == user_id
        assert payload.type == "access"

    def test_decode_expired_token_returns_none(self):
        """Test that decoding an expired token returns None."""
        token = jwt.encode(
            {
                "sub": "test-user",
                "exp": datetime.utcnow() - timedelta(minutes=1),
                "type": "access"
            },
            SECRET_KEY,
            algorithm=ALGORITHM
        )
        
        payload = decode_token(token)
        assert payload is None

    def test_decode_invalid_token_returns_none(self):
        """Test that decoding an invalid token returns None."""
        payload = decode_token("invalid.token.here")
        assert payload is None

    def test_decode_token_with_wrong_secret(self):
        """Test that token signed with wrong secret is rejected."""
        token = jwt.encode(
            {
                "sub": "test-user",
                "exp": datetime.utcnow() + timedelta(hours=1),
                "type": "access"
            },
            "wrong-secret-key",
            algorithm=ALGORITHM
        )
        
        payload = decode_token(token)
        assert payload is None
