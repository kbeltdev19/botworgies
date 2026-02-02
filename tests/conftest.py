"""
Pytest fixtures and configuration for Job Applier test suite.
"""

import pytest
import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


# === Async Event Loop ===

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# === Test Data Fixtures ===

@pytest.fixture
def sample_resume_text():
    """Sample resume for testing."""
    return """
JOHN DOE
Software Engineer | john.doe@email.com | (555) 123-4567

EXPERIENCE

Software Engineer at StartupCo (2020-2022)
- Built REST APIs using Flask and PostgreSQL
- Implemented CI/CD pipelines with GitHub Actions
- Led a team of 2 junior developers

Junior Developer at TechCorp (2018-2020)
- Developed Python automation scripts
- Maintained AWS EC2 and S3 infrastructure
- Created data processing pipelines

SKILLS
Python, Flask, PostgreSQL, AWS, Docker, Git, REST APIs

EDUCATION
BS Computer Science, State University (2018)
"""


@pytest.fixture
def sample_job_description():
    """Sample job description for testing."""
    return """
Senior Software Engineer - Backend

We're looking for an experienced backend engineer to join our team.

Requirements:
- 5+ years of experience with Python
- Strong experience with Kubernetes and Docker
- Experience with Go language preferred
- PostgreSQL or similar relational databases
- Team leadership experience

Nice to have:
- gRPC experience
- Rust knowledge
- ML/AI background
"""


@pytest.fixture
def sample_user_profile():
    """Sample user profile for testing."""
    from adapters.base import UserProfile
    return UserProfile(
        first_name="John",
        last_name="Doe",
        email="john.doe@email.com",
        phone="555-123-4567",
        linkedin_url="https://linkedin.com/in/johndoe",
        years_experience=4,
        work_authorization="Yes",
        sponsorship_required="No"
    )


@pytest.fixture
def sample_resume(sample_resume_text):
    """Sample Resume object for testing."""
    from adapters.base import Resume
    return Resume(
        file_path="/tmp/test_resume.pdf",
        raw_text=sample_resume_text,
        parsed_data={
            "name": "John Doe",
            "email": "john.doe@email.com",
            "experience": [
                {"company": "StartupCo", "title": "Software Engineer", "dates": "2020-2022"},
                {"company": "TechCorp", "title": "Junior Developer", "dates": "2018-2020"}
            ],
            "skills": ["Python", "Flask", "PostgreSQL", "AWS", "Docker"]
        }
    )


@pytest.fixture
def mock_kimi_service():
    """Mock Kimi service for testing."""
    mock = AsyncMock()
    mock.tailor_resume.return_value = {
        "tailored_bullets": [
            "Built REST APIs using Flask and PostgreSQL - relevant to backend role",
            "Led team of 2 developers - demonstrates leadership"
        ],
        "match_score": 0.72,
        "missing_skills": ["Kubernetes", "Go", "gRPC"]
    }
    mock.generate_cover_letter.return_value = """
Dear Hiring Manager,

I am excited to apply for the Senior Software Engineer position. 
With 4 years of Python experience and a background in building REST APIs,
I believe I would be a strong addition to your team.

Sincerely,
John Doe
"""
    return mock


@pytest.fixture
def mock_browser_manager():
    """Mock browser manager for testing."""
    mock = MagicMock()
    mock.create_session = AsyncMock(return_value={
        "session_id": "test-session-123",
        "page": MagicMock()
    })
    mock.close_session = AsyncMock()
    mock.human_like_delay = AsyncMock()
    mock.human_like_click = AsyncMock()
    mock.human_like_scroll = AsyncMock()
    mock.wait_for_cloudflare = AsyncMock()
    return mock


# === Test Environment Setup ===

@pytest.fixture(autouse=True)
def setup_test_env():
    """Setup test environment variables."""
    os.environ.setdefault("TESTING", "true")
    os.environ.setdefault("MOONSHOT_API_KEY", "test-key")
    os.environ.setdefault("BROWSERBASE_API_KEY", "test-key")
    os.environ.setdefault("DATABASE_PATH", "/tmp/test_job_applier.db")
    os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only")
    yield
    # Cleanup test database
    test_db = Path("/tmp/test_job_applier.db")
    if test_db.exists():
        test_db.unlink()


@pytest.fixture(autouse=True, scope="session")
def init_test_database():
    """Initialize test database before all tests."""
    import asyncio
    os.environ["DATABASE_PATH"] = "/tmp/test_job_applier.db"
    
    from api.database import init_database
    asyncio.run(init_database())
    yield


# === Authenticated Test Client ===

@pytest.fixture
def authenticated_client():
    """
    Create a test client with authentication bypassed.
    Uses dependency_overrides for proper FastAPI authentication mocking.
    """
    from fastapi.testclient import TestClient
    from api.main import app, get_current_user
    
    # Override the authentication dependency
    async def mock_get_current_user():
        return "test-user-uuid-1234"
    
    app.dependency_overrides[get_current_user] = mock_get_current_user
    
    try:
        client = TestClient(app)
        yield client
    finally:
        # Clean up override
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def auth_headers():
    """Create valid JWT authentication headers."""
    from api.auth import create_access_token
    
    token = create_access_token("test-user-uuid-1234")
    return {"Authorization": f"Bearer {token}"}


# === Markers ===

def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line("markers", "e2e: End-to-end tests (slow)")
    config.addinivalue_line("markers", "stealth: Anti-detection tests")
    config.addinivalue_line("markers", "safety: Hallucination/safety tests")
    config.addinivalue_line("markers", "performance: Performance benchmarks")
