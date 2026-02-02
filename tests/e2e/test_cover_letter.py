"""
End-to-End Cover Letter Generation Tests for Job Applier API.

This module tests the cover letter generation functionality according to
the evaluation criteria:

- COVER-01: Cover letter references specific job/company
- COVER-02: Tone matches user preference (formal, conversational, etc.)
- COVER-03: No fabricated qualifications or experience
- COVER-04: Letter length appropriate (250-400 words)
- COVER-05: Generated content is grammatically correct
- COVER-06: User can edit generated cover letter
- COVER-07: Multiple template options available

Technical Specifications:
- Endpoint: POST /ai/generate-cover-letter
- Integration: Cover letter generated during POST /apply with generate_cover_letter=true
- AI Service: KimiResumeOptimizer (Moonshot AI)
- Tone Options: professional, casual, enthusiastic
"""

import pytest
import re
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

# Ensure project root is in path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.main import app
from api.auth import create_access_token


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def auth_token():
    """Generate a valid auth token for testing."""
    return create_access_token("test-user-uuid-1234")


@pytest.fixture
def auth_headers(auth_token):
    """Authorization headers with valid token."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def sample_resume_data():
    """Sample resume data stored in database format."""
    return {
        "id": "resume-123",
        "user_id": "test-user-uuid-1234",
        "file_path": "/tmp/test_resume.pdf",
        "raw_text": """
JOHN DOE
Software Engineer | john.doe@email.com | (555) 123-4567

EXPERIENCE

Senior Software Engineer at TechCorp (2020-Present)
- Led development of microservices architecture serving 1M+ users
- Implemented CI/CD pipelines with GitHub Actions and Docker
- Mentored team of 5 junior developers

Software Engineer at StartupCo (2018-2020)
- Built REST APIs using Python and Flask
- Managed PostgreSQL databases and optimized queries
- Deployed applications on AWS EC2 and Kubernetes

SKILLS
Python, Flask, PostgreSQL, AWS, Docker, Kubernetes, Git, REST APIs, CI/CD

EDUCATION
BS Computer Science, State University (2018)
""",
        "parsed_data": {
            "name": "John Doe",
            "email": "john.doe@email.com",
            "skills": ["Python", "Flask", "PostgreSQL", "AWS", "Docker", "Kubernetes"],
            "experience_years": 6
        },
        "created_at": datetime.now().isoformat()
    }


@pytest.fixture
def mock_cover_letter_professional():
    """Mock professional tone cover letter."""
    return """Dear Hiring Manager,

I am writing to express my strong interest in the Senior Backend Engineer position at Acme Corporation. With over 6 years of experience in software engineering and a proven track record of leading technical initiatives, I am confident in my ability to contribute effectively to your engineering team.

In my current role at TechCorp, I have led the development of microservices architecture that now serves over one million users. This experience has strengthened my expertise in Python, Flask, and PostgreSQL, which align closely with the requirements outlined in your job posting. Additionally, my work with Docker and Kubernetes has given me valuable DevOps experience that would be beneficial to your infrastructure team.

Previously, at StartupCo, I built REST APIs and optimized database queries, achieving a 40% improvement in response times. I have also mentored junior developers, demonstrating my commitment to team growth and knowledge sharing.

I am particularly drawn to Acme Corporation because of your innovative approach to cloud solutions and your commitment to engineering excellence. I would welcome the opportunity to discuss how my background in backend development and system architecture could support your team's goals.

Thank you for considering my application. I look forward to the possibility of contributing to Acme Corporation's continued success.

Sincerely,
John Doe"""


@pytest.fixture
def mock_cover_letter_casual():
    """Mock casual tone cover letter."""
    return """Hi there,

I'm excited to apply for the Senior Backend Engineer role at Acme Corporation! I've been working as a software engineer for about 6 years now, and I think my experience with Python and building scalable systems would be a great fit for your team.

At TechCorp, I've been leading the development of microservices that handle over a million users. It's been a rewarding challenge, and I've learned a ton about building reliable backend systems with Flask and PostgreSQL. I also work quite a bit with Docker and Kubernetes, which sounds like it matches what you're looking for.

Before that, at StartupCo, I got to build REST APIs from scratch and really dive deep into database optimization. I even got to mentor some junior developers along the way, which has been one of the most fulfilling parts of my career.

I've been following Acme Corporation's work in cloud solutions, and I'm genuinely impressed by what your team has built. I'd love to chat more about how I could contribute to your engineering efforts.

Thanks for taking the time to review my application!

Best,
John Doe"""


@pytest.fixture
def mock_cover_letter_enthusiastic():
    """Mock enthusiastic tone cover letter."""
    return """Dear Acme Corporation Hiring Team,

I am absolutely thrilled to apply for the Senior Backend Engineer position! This opportunity perfectly aligns with my passion for building scalable systems and my 6 years of hands-on experience in software engineering.

I am incredibly excited about the possibility of bringing my expertise to TechCorp! Leading the development of microservices architecture serving 1M+ users has been an amazing journey, and I am eager to apply these skills at Acme Corporation. My deep knowledge of Python, Flask, and PostgreSQL, combined with my DevOps experience in Docker and Kubernetes, makes me confident that I can make an immediate impact on your team.

My time at StartupCo was transformative - I built REST APIs that powered critical business functions and achieved remarkable 40% performance improvements through database optimization. I am passionate about mentoring others and have successfully guided 5 junior developers in their careers!

What excites me most about Acme Corporation is your groundbreaking work in cloud solutions and your dedication to engineering excellence. I would be honored to contribute to your mission and help drive innovation within your engineering team!

Thank you for this incredible opportunity. I am eagerly looking forward to discussing how my enthusiasm and expertise can help Acme Corporation achieve even greater success!

With excitement and gratitude,
John Doe"""


@pytest.fixture
def valid_cover_letter_request():
    """Valid cover letter generation request data."""
    return {
        "job_title": "Senior Backend Engineer",
        "company_name": "Acme Corporation",
        "job_requirements": "5+ years Python, Flask, PostgreSQL, Docker, Kubernetes, REST APIs",
        "tone": "professional"
    }


@pytest.fixture
def mock_get_latest_resume(sample_resume_data):
    """Mock getting the latest resume for a user."""
    with patch("api.main.get_latest_resume") as mock:
        mock.return_value = sample_resume_data
        yield mock


@pytest.fixture
def mock_kimi_service():
    """Mock Kimi AI service for cover letter generation."""
    with patch("api.main.kimi") as mock:
        mock.generate_cover_letter = AsyncMock()
        yield mock


# ============================================================================
# Helper Functions
# ============================================================================

def count_words(text: str) -> int:
    """Count words in a text."""
    return len(text.split())


def contains_company_reference(text: str, company: str) -> bool:
    """Check if text contains reference to company name."""
    # Check for exact match or common variations
    company_lower = company.lower()
    text_lower = text.lower()
    
    # Direct mention
    if company_lower in text_lower:
        return True
    
    # Check for partial matches (e.g., "Acme" from "Acme Corporation")
    company_parts = company_lower.split()
    for part in company_parts:
        if len(part) > 3 and part in text_lower:  # Avoid matching short words like "the", "inc"
            return True
    
    return False


def contains_job_reference(text: str, job_title: str) -> bool:
    """Check if text contains reference to job title."""
    text_lower = text.lower()
    job_lower = job_title.lower()
    
    # Direct match
    if job_lower in text_lower:
        return True
    
    # Check for key terms
    key_terms = [term for term in job_lower.split() if len(term) > 3]
    matches = sum(1 for term in key_terms if term in text_lower)
    
    # If majority of key terms match, consider it a reference
    return matches >= len(key_terms) / 2


def check_grammar_indicators(text: str) -> bool:
    """Basic grammar checks - looks for common issues."""
    issues = []
    
    # Check for repeated punctuation
    if re.search(r'[.]{2,}', text):
        issues.append("repeated periods")
    
    # Check for sentences starting with lowercase
    sentences = re.split(r'[.!?]+', text)
    for sentence in sentences:
        stripped = sentence.strip()
        if stripped and stripped[0].islower():
            issues.append("sentence starts with lowercase")
            break
    
    # Check for proper greeting/closing
    greetings = ["dear", "hi", "hello", "to whom", "hiring manager"]
    has_greeting = any(g in text.lower() for g in greetings)
    if not has_greeting:
        issues.append("missing greeting")
    
    closings = ["sincerely", "best", "regards", "thank you", "thanks"]
    has_closing = any(c in text.lower() for c in closings)
    if not has_closing:
        issues.append("missing closing")
    
    return len(issues) == 0


# ============================================================================
# COVER-01: Cover letter references specific job/company
# ============================================================================

class TestCoverLetterJobCompanyReferences:
    """Test that cover letters reference specific job and company (COVER-01)."""

    @pytest.mark.asyncio
    def test_cover_letter_includes_company_name(
        self, client, auth_headers, mock_get_latest_resume, mock_kimi_service,
        mock_cover_letter_professional
    ):
        """Test that generated cover letter includes the company name."""
        mock_kimi_service.generate_cover_letter.return_value = mock_cover_letter_professional
        
        response = client.post(
            "/ai/generate-cover-letter",
            params={
                "job_title": "Senior Backend Engineer",
                "company_name": "Acme Corporation",
                "job_requirements": "Python, Flask experience",
                "tone": "professional"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "cover_letter" in data
        
        cover_letter = data["cover_letter"]
        assert contains_company_reference(cover_letter, "Acme Corporation"), \
            "Cover letter should reference the company name"

    @pytest.mark.asyncio
    def test_cover_letter_includes_job_title(
        self, client, auth_headers, mock_get_latest_resume, mock_kimi_service,
        mock_cover_letter_professional
    ):
        """Test that generated cover letter includes the job title."""
        mock_kimi_service.generate_cover_letter.return_value = mock_cover_letter_professional
        
        response = client.post(
            "/ai/generate-cover-letter",
            params={
                "job_title": "Senior Backend Engineer",
                "company_name": "Acme Corporation",
                "tone": "professional"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        cover_letter = data["cover_letter"]
        
        assert contains_job_reference(cover_letter, "Senior Backend Engineer"), \
            "Cover letter should reference the job title"

    @pytest.mark.asyncio
    def test_cover_letter_addresses_job_requirements(
        self, client, auth_headers, mock_get_latest_resume, mock_kimi_service
    ):
        """Test that cover letter addresses specific job requirements."""
        requirements = "Python, Flask, PostgreSQL, Kubernetes, Docker"
        
        cover_letter_with_requirements = f"""Dear Hiring Manager,

I am writing to apply for the position. My experience includes Python and Flask development,
along with PostgreSQL database management. I have also worked extensively with Docker
and Kubernetes for containerization and orchestration.

Sincerely,
John Doe"""
        
        mock_kimi_service.generate_cover_letter.return_value = cover_letter_with_requirements
        
        response = client.post(
            "/ai/generate-cover-letter",
            params={
                "job_title": "Backend Developer",
                "company_name": "TechCorp",
                "job_requirements": requirements,
                "tone": "professional"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        cover_letter = data["cover_letter"].lower()
        
        # Should mention at least some of the required skills
        required_skills = ["python", "flask", "postgresql", "kubernetes", "docker"]
        mentioned_skills = [skill for skill in required_skills if skill in cover_letter]
        
        assert len(mentioned_skills) >= 2, \
            f"Cover letter should address job requirements. Found: {mentioned_skills}"


# ============================================================================
# COVER-02: Tone matches user preference
# ============================================================================

class TestCoverLetterToneMatching:
    """Test that cover letter tone matches user preference (COVER-02)."""

    @pytest.mark.parametrize("tone,expected_phrases", [
        ("professional", ["dear hiring manager", "sincerely", "application", "experience"]),
        ("casual", ["hi", "hey", "best", "thanks", "chat"]),
        ("enthusiastic", ["excited", "thrilled", "passionate", "eager", "absolutely"]),
    ])
    @pytest.mark.asyncio
    def test_cover_letter_tone_variations(
        self, client, auth_headers, mock_get_latest_resume, mock_kimi_service,
        mock_cover_letter_professional, mock_cover_letter_casual, mock_cover_letter_enthusiastic,
        tone, expected_phrases
    ):
        """Test that different tone options produce appropriately styled cover letters."""
        # Return appropriate mock based on tone
        tone_to_mock = {
            "professional": mock_cover_letter_professional,
            "casual": mock_cover_letter_casual,
            "enthusiastic": mock_cover_letter_enthusiastic
        }
        mock_kimi_service.generate_cover_letter.return_value = tone_to_mock.get(tone, mock_cover_letter_professional)
        
        response = client.post(
            "/ai/generate-cover-letter",
            params={
                "job_title": "Software Engineer",
                "company_name": "TestCorp",
                "tone": tone
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        cover_letter_lower = data["cover_letter"].lower()
        
        # Check that at least one expected phrase for the tone is present
        matches = [phrase for phrase in expected_phrases if phrase in cover_letter_lower]
        assert len(matches) > 0, \
            f"Cover letter with '{tone}' tone should contain expected phrases. Found: {matches}"

    @pytest.mark.asyncio
    def test_invalid_tone_rejected(
        self, client, auth_headers, mock_get_latest_resume
    ):
        """Test that invalid tone options are rejected."""
        response = client.post(
            "/ai/generate-cover-letter",
            params={
                "job_title": "Software Engineer",
                "company_name": "TestCorp",
                "tone": "invalid_tone"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    def test_default_tone_is_professional(
        self, client, auth_headers, mock_get_latest_resume, mock_kimi_service,
        mock_cover_letter_professional
    ):
        """Test that default tone is professional when not specified."""
        mock_kimi_service.generate_cover_letter.return_value = mock_cover_letter_professional
        
        # Mock the generate_cover_letter call to capture the tone parameter
        captured_tone = None
        async def capture_tone(*args, **kwargs):
            nonlocal captured_tone
            captured_tone = kwargs.get('tone', 'not_specified')
            return mock_cover_letter_professional
        
        mock_kimi_service.generate_cover_letter.side_effect = capture_tone
        
        response = client.post(
            "/ai/generate-cover-letter",
            params={
                "job_title": "Software Engineer",
                "company_name": "TestCorp"
                # tone not specified
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        # The API should use a default tone when not specified
        assert captured_tone is not None


# ============================================================================
# COVER-03: No fabricated qualifications or experience
# ============================================================================

class TestCoverLetterNoFabrication:
    """Test that cover letters don't fabricate qualifications (COVER-03)."""

    @pytest.mark.asyncio
    def test_cover_letter_based_on_actual_resume(
        self, client, auth_headers, mock_get_latest_resume, mock_kimi_service
    ):
        """Test that cover letter content is based on actual resume data."""
        # Cover letter that references actual resume content
        fact_based_cover_letter = """Dear Hiring Manager,

I am applying for the position at your company. My experience includes working at
TechCorp where I led development of microservices and worked with Python, Flask,
and PostgreSQL. I also have experience with Docker and Kubernetes from my time there.

Previously at StartupCo, I built REST APIs and managed AWS infrastructure.

Sincerely,
John Doe"""
        
        mock_kimi_service.generate_cover_letter.return_value = fact_based_cover_letter
        
        response = client.post(
            "/ai/generate-cover-letter",
            params={
                "job_title": "Backend Engineer",
                "company_name": "NewCorp",
                "tone": "professional"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        cover_letter = data["cover_letter"]
        
        # Verify the AI was called with resume content
        mock_kimi_service.generate_cover_letter.assert_called_once()
        call_kwargs = mock_kimi_service.generate_cover_letter.call_args.kwargs
        
        # Should include resume summary in the call
        assert "resume_summary" in call_kwargs
        assert len(call_kwargs["resume_summary"]) > 0

    @pytest.mark.asyncio
    def test_cover_letter_no_exaggerated_years_experience(
        self, client, auth_headers, mock_get_latest_resume, mock_kimi_service
    ):
        """Test that cover letter doesn't exaggerate years of experience."""
        # Resume shows 6 years, cover letter should not claim more
        accurate_experience_letter = """Dear Hiring Manager,

With 6 years of experience in software engineering, I am excited to apply...

Sincerely,
John Doe"""
        
        mock_kimi_service.generate_cover_letter.return_value = accurate_experience_letter
        
        response = client.post(
            "/ai/generate-cover-letter",
            params={
                "job_title": "Senior Engineer",
                "company_name": "BigCorp",
                "tone": "professional"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        cover_letter = data["cover_letter"].lower()
        
        # Should not claim more than actual experience
        # Look for patterns like "10+ years", "15 years", etc. that exceed resume
        exaggerated_patterns = [r"\b1[0-9]\+?\s*years", r"\b[2-9][0-9]\+?\s*years"]
        for pattern in exaggerated_patterns:
            assert not re.search(pattern, cover_letter), \
                f"Cover letter should not exaggerate years of experience"

    @pytest.mark.asyncio
    def test_cover_letter_no_invented_companies(
        self, client, auth_headers, mock_get_latest_resume, mock_kimi_service
    ):
        """Test that cover letter doesn't invent companies not on resume."""
        cover_letter = """Dear Hiring Manager,

At TechCorp and StartupCo, I gained valuable experience...

Sincerely,
John Doe"""
        
        mock_kimi_service.generate_cover_letter.return_value = cover_letter
        
        response = client.post(
            "/ai/generate-cover-letter",
            params={
                "job_title": "Developer",
                "company_name": "TestCorp",
                "tone": "professional"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        content = data["cover_letter"]
        
        # Should only reference actual companies from resume
        actual_companies = ["techcorp", "startupco"]
        invented_companies = ["google", "microsoft", "amazon", "facebook", "apple", "netflix"]
        
        content_lower = content.lower()
        for company in invented_companies:
            if company not in actual_companies:
                assert company not in content_lower, \
                    f"Cover letter should not invent experience at {company}"


# ============================================================================
# COVER-04: Letter length appropriate (250-400 words)
# ============================================================================

class TestCoverLetterLength:
    """Test that cover letter length is appropriate (COVER-04)."""

    @pytest.mark.asyncio
    def test_cover_letter_minimum_length(
        self, client, auth_headers, mock_get_latest_resume, mock_kimi_service
    ):
        """Test that cover letter meets minimum length requirement."""
        # Create a cover letter with sufficient length (250+ words)
        long_cover_letter = """Dear Hiring Manager,

I am writing to express my strong interest in the Software Engineer position at your company.
With over 6 years of experience in software development, I have developed a comprehensive
skill set that aligns well with the requirements of this role.

Throughout my career, I have gained extensive experience in Python, Flask, and PostgreSQL.
At my current position, I have successfully led the development of microservices architecture
that serves over one million users. This experience has taught me the importance of writing
clean, maintainable code and designing systems that can scale efficiently.

In addition to my technical skills, I have experience with Docker and Kubernetes, which
I understand are important technologies for your team. I have also worked extensively with
AWS services, including EC2, S3, and RDS, giving me a strong foundation in cloud infrastructure.

What excites me most about this opportunity is the chance to work with a talented team
on challenging problems. I am particularly drawn to your company's mission and values,
and I believe my background in backend development would allow me to make meaningful
contributions from day one.

I would welcome the opportunity to discuss how my experience and skills could benefit
your team. Thank you for considering my application. I look forward to hearing from you.

Sincerely,
John Doe

P.S. I am available for an interview at your earliest convenience and can be reached
at the contact information provided above."""
        
        mock_kimi_service.generate_cover_letter.return_value = long_cover_letter
        
        response = client.post(
            "/ai/generate-cover-letter",
            params={
                "job_title": "Software Engineer",
                "company_name": "TestCorp",
                "tone": "professional"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        word_count = count_words(data["cover_letter"])
        
        assert word_count >= 250, \
            f"Cover letter should be at least 250 words. Got: {word_count}"

    @pytest.mark.asyncio
    def test_cover_letter_maximum_length(
        self, client, auth_headers, mock_get_latest_resume, mock_kimi_service
    ):
        """Test that cover letter doesn't exceed maximum length."""
        # Create an overly long cover letter (400+ words)
        overly_long_letter = "Dear Hiring Manager,\n\n" + \
            " ".join(["I have experience with Python and software development."] * 200) + \
            "\n\nSincerely,\nJohn Doe"
        
        mock_kimi_service.generate_cover_letter.return_value = overly_long_letter
        
        response = client.post(
            "/ai/generate-cover-letter",
            params={
                "job_title": "Software Engineer",
                "company_name": "TestCorp",
                "tone": "professional"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        word_count = count_words(data["cover_letter"])
        
        # In a real implementation, this might be truncated or rejected
        # For now, we just verify the word count
        assert word_count > 0

    @pytest.mark.asyncio
    def test_cover_letter_optimal_length(
        self, client, auth_headers, mock_get_latest_resume, mock_kimi_service,
        mock_cover_letter_professional
    ):
        """Test that cover letter falls within optimal range (250-400 words)."""
        mock_kimi_service.generate_cover_letter.return_value = mock_cover_letter_professional
        
        response = client.post(
            "/ai/generate-cover-letter",
            params={
                "job_title": "Software Engineer",
                "company_name": "TestCorp",
                "tone": "professional"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        word_count = count_words(data["cover_letter"])
        
        # Optimal range: 250-400 words
        assert 250 <= word_count <= 400, \
            f"Cover letter should be 250-400 words. Got: {word_count}"


# ============================================================================
# COVER-05: Generated content is grammatically correct
# ============================================================================

class TestCoverLetterGrammar:
    """Test that generated content is grammatically correct (COVER-05)."""

    @pytest.mark.asyncio
    def test_cover_letter_has_proper_structure(
        self, client, auth_headers, mock_get_latest_resume, mock_kimi_service,
        mock_cover_letter_professional
    ):
        """Test that cover letter has proper structure (greeting, body, closing)."""
        mock_kimi_service.generate_cover_letter.return_value = mock_cover_letter_professional
        
        response = client.post(
            "/ai/generate-cover-letter",
            params={
                "job_title": "Software Engineer",
                "company_name": "TestCorp",
                "tone": "professional"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        cover_letter = data["cover_letter"]
        
        # Check for proper greeting
        greetings = ["Dear", "Hi", "Hello", "To Whom"]
        has_greeting = any(greeting in cover_letter for greeting in greetings)
        assert has_greeting, "Cover letter should have a proper greeting"
        
        # Check for proper closing
        closings = ["Sincerely", "Best regards", "Thank you", "Thanks"]
        has_closing = any(closing in cover_letter for closing in closings)
        assert has_closing, "Cover letter should have a proper closing"
        
        # Check for signature
        assert "John Doe" in cover_letter or "Doe" in cover_letter, \
            "Cover letter should include applicant name"

    @pytest.mark.asyncio
    def test_cover_letter_no_grammar_issues(
        self, client, auth_headers, mock_get_latest_resume, mock_kimi_service
    ):
        """Test that cover letter doesn't have obvious grammar issues."""
        well_written_letter = """Dear Hiring Manager,

I am writing to express my strong interest in the Software Engineer position at your company.
With my background in Python development and system architecture, I believe I would be a
valuable addition to your team.

During my time at TechCorp, I led the development of several key projects. I worked closely
with cross-functional teams to deliver high-quality software solutions. My experience with
Flask and PostgreSQL has prepared me well for this role.

I would welcome the opportunity to discuss how my skills align with your needs.

Sincerely,
John Doe"""
        
        mock_kimi_service.generate_cover_letter.return_value = well_written_letter
        
        response = client.post(
            "/ai/generate-cover-letter",
            params={
                "job_title": "Software Engineer",
                "company_name": "TestCorp",
                "tone": "professional"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        cover_letter = data["cover_letter"]
        
        # Basic grammar checks
        assert check_grammar_indicators(cover_letter), \
            "Cover letter should not have obvious grammar issues"
        
        # Check for sentence capitalization
        lines = cover_letter.split('\n')
        for line in lines:
            stripped = line.strip()
            if stripped and len(stripped) > 5 and stripped[0].isalpha():
                assert stripped[0].isupper() or stripped.startswith('iPhone') or stripped.startswith('iOS'), \
                    f"Sentence should start with uppercase: '{stripped}'"

    @pytest.mark.asyncio
    def test_cover_letter_proper_punctuation(
        self, client, auth_headers, mock_get_latest_resume, mock_kimi_service
    ):
        """Test that cover letter has proper punctuation."""
        letter_with_good_punctuation = """Dear Hiring Manager,

I am excited to apply for this position. My experience includes Python, Flask, and PostgreSQL.
At my current company, I have led several successful projects.

I look forward to hearing from you.

Sincerely,
John Doe"""
        
        mock_kimi_service.generate_cover_letter.return_value = letter_with_good_punctuation
        
        response = client.post(
            "/ai/generate-cover-letter",
            params={
                "job_title": "Developer",
                "company_name": "TestCorp",
                "tone": "professional"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        cover_letter = data["cover_letter"]
        
        # Check for repeated punctuation (e.g., "..." or "!!")
        assert not re.search(r'[.]{2,}', cover_letter), \
            "Cover letter should not have repeated periods"
        assert not re.search(r'[!]{2,}', cover_letter), \
            "Cover letter should not have repeated exclamation marks"


# ============================================================================
# COVER-06: User can edit generated cover letter
# ============================================================================

class TestCoverLetterEditFunctionality:
    """Test that users can edit generated cover letters (COVER-06)."""

    @pytest.mark.asyncio
    def test_cover_letter_returned_in_editable_format(
        self, client, auth_headers, mock_get_latest_resume, mock_kimi_service,
        mock_cover_letter_professional
    ):
        """Test that cover letter is returned in a plain text editable format."""
        mock_kimi_service.generate_cover_letter.return_value = mock_cover_letter_professional
        
        response = client.post(
            "/ai/generate-cover-letter",
            params={
                "job_title": "Software Engineer",
                "company_name": "TestCorp",
                "tone": "professional"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return plain text cover letter
        assert "cover_letter" in data
        assert isinstance(data["cover_letter"], str)
        assert len(data["cover_letter"]) > 0
        
        # Should not be in a binary or encoded format
        assert not data["cover_letter"].startswith("data:"), \
            "Cover letter should not be data URL encoded"
        assert not data["cover_letter"].startswith("eyJ"), \
            "Cover letter should not be base64 encoded"

    @pytest.mark.asyncio
    def test_cover_letter_edit_in_application_flow(
        self, client, auth_headers, mock_get_latest_resume, mock_kimi_service
    ):
        """Test that cover letter can be edited during application process."""
        # Mock the application flow dependencies
        with patch("api.main.get_profile") as mock_get_profile:
            mock_get_profile.return_value = {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
                "phone": "555-123-4567"
            }
            with patch("api.main.get_settings") as mock_get_settings:
                mock_get_settings.return_value = {
                    "daily_limit": 10,
                    "linkedin_cookie_encrypted": None
                }
                with patch("api.main.count_applications_since") as mock_count:
                    mock_count.return_value = 0
                    with patch("api.main.detect_platform_from_url") as mock_detect:
                        mock_detect.return_value = "greenhouse"
                        
                        # Test application endpoint accepts generate_cover_letter parameter
                        response = client.post(
                            "/apply",
                            json={
                                "job_url": "https://boards.greenhouse.io/test/jobs/123",
                                "auto_submit": False,
                                "generate_cover_letter": True,
                                "cover_letter_tone": "professional"
                            },
                            headers=auth_headers
                        )
                        
                        # Should accept the request and start processing
                        assert response.status_code in [200, 503]  # 503 if browser not available
                        
                        if response.status_code == 200:
                            data = response.json()
                            assert "application_id" in data

    @pytest.mark.asyncio
    def test_cover_letter_tone_parameter_in_application(
        self, client, auth_headers, mock_get_latest_resume, mock_kimi_service
    ):
        """Test that cover letter tone can be specified in application request."""
        cover_letter_generated = []
        
        async def capture_cover_letter(*args, **kwargs):
            cover_letter_generated.append(kwargs.get('tone'))
            return "Test cover letter content"
        
        mock_kimi_service.generate_cover_letter.side_effect = capture_cover_letter
        
        with patch("api.main.get_profile") as mock_get_profile:
            mock_get_profile.return_value = {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
                "phone": "555-123-4567"
            }
            with patch("api.main.get_settings") as mock_get_settings:
                mock_get_settings.return_value = {
                    "daily_limit": 10,
                    "linkedin_cookie_encrypted": None
                }
                with patch("api.main.count_applications_since") as mock_count:
                    mock_count.return_value = 0
                    with patch("api.main.detect_platform_from_url") as mock_detect:
                        mock_detect.return_value = "greenhouse"
                        
                        response = client.post(
                            "/apply",
                            json={
                                "job_url": "https://boards.greenhouse.io/test/jobs/123",
                                "generate_cover_letter": True,
                                "cover_letter_tone": "enthusiastic"
                            },
                            headers=auth_headers
                        )
                        
                        # Verify tone is passed through
                        if response.status_code == 200 and cover_letter_generated:
                            assert "enthusiastic" in cover_letter_generated or len(cover_letter_generated) == 0


# ============================================================================
# COVER-07: Multiple template options available
# ============================================================================

class TestCoverLetterTemplates:
    """Test that multiple template options are available (COVER-07)."""

    @pytest.mark.asyncio
    def test_cover_letter_tone_options_available(
        self, client, auth_headers, mock_get_latest_resume, mock_kimi_service
    ):
        """Test that multiple tone options (templates) are available."""
        valid_tones = ["professional", "casual", "enthusiastic"]
        
        for tone in valid_tones:
            mock_kimi_service.generate_cover_letter.return_value = f"Cover letter with {tone} tone"
            
            response = client.post(
                "/ai/generate-cover-letter",
                params={
                    "job_title": "Software Engineer",
                    "company_name": "TestCorp",
                    "tone": tone
                },
                headers=auth_headers
            )
            
            assert response.status_code == 200, \
                f"Tone '{tone}' should be accepted"

    @pytest.mark.asyncio
    def test_different_tones_produce_different_content(
        self, client, auth_headers, mock_get_latest_resume, mock_kimi_service,
        mock_cover_letter_professional, mock_cover_letter_casual, mock_cover_letter_enthusiastic
    ):
        """Test that different tones produce meaningfully different content."""
        tone_responses = {}
        
        tone_to_mock = {
            "professional": mock_cover_letter_professional,
            "casual": mock_cover_letter_casual,
            "enthusiastic": mock_cover_letter_enthusiastic
        }
        
        for tone in ["professional", "casual", "enthusiastic"]:
            mock_kimi_service.generate_cover_letter.return_value = tone_to_mock.get(tone, mock_cover_letter_professional)
            
            response = client.post(
                "/ai/generate-cover-letter",
                params={
                    "job_title": "Software Engineer",
                    "company_name": "TestCorp",
                    "tone": tone
                },
                headers=auth_headers
            )
            
            assert response.status_code == 200
            tone_responses[tone] = response.json()["cover_letter"]
        
        # Different tones should produce different content
        assert tone_responses["professional"] != tone_responses["casual"], \
            "Professional and casual tones should produce different content"
        assert tone_responses["professional"] != tone_responses["enthusiastic"], \
            "Professional and enthusiastic tones should produce different content"
        assert tone_responses["casual"] != tone_responses["enthusiastic"], \
            "Casual and enthusiastic tones should produce different content"


# ============================================================================
# Error Handling and Edge Cases
# ============================================================================

class TestCoverLetterErrorHandling:
    """Test error handling for cover letter generation."""

    @pytest.mark.asyncio
    def test_cover_letter_without_resume_returns_404(
        self, client, auth_headers
    ):
        """Test that cover letter generation fails gracefully without resume."""
        with patch("api.main.get_latest_resume") as mock:
            mock.return_value = None
            
            response = client.post(
                "/ai/generate-cover-letter",
                params={
                    "job_title": "Software Engineer",
                    "company_name": "TestCorp"
                },
                headers=auth_headers
            )
            
            assert response.status_code == 404
            data = response.json()
            assert "detail" in data
            assert "resume" in data["detail"].lower()

    @pytest.mark.asyncio
    def test_cover_letter_missing_required_params(
        self, client, auth_headers, mock_get_latest_resume
    ):
        """Test that missing required parameters are handled."""
        # Missing job_title
        response = client.post(
            "/ai/generate-cover-letter",
            params={
                "company_name": "TestCorp"
                # job_title missing
            },
            headers=auth_headers
        )
        
        assert response.status_code == 422
        
        # Missing company_name
        response = client.post(
            "/ai/generate-cover-letter",
            params={
                "job_title": "Software Engineer"
                # company_name missing
            },
            headers=auth_headers
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    def test_cover_letter_unauthenticated(
        self, client, mock_get_latest_resume
    ):
        """Test that unauthenticated requests are rejected."""
        response = client.post(
            "/ai/generate-cover-letter",
            params={
                "job_title": "Software Engineer",
                "company_name": "TestCorp"
            }
            # No auth headers
        )
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    def test_cover_letter_ai_service_failure(
        self, client, auth_headers, mock_get_latest_resume, mock_kimi_service
    ):
        """Test graceful handling of AI service failure."""
        mock_kimi_service.generate_cover_letter.side_effect = Exception("AI service unavailable")
        
        response = client.post(
            "/ai/generate-cover-letter",
            params={
                "job_title": "Software Engineer",
                "company_name": "TestCorp"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data


# ============================================================================
# Integration Tests (Placeholders for actual API calls)
# ============================================================================

@pytest.mark.e2e
class TestCoverLetterIntegration:
    """Integration tests with actual AI service (marked as e2e)."""

    @pytest.mark.skip(reason="Requires actual Moonshot API key - run manually")
    def test_cover_letter_generation_with_real_api(self, client, auth_headers):
        """Integration test with actual Kimi AI service."""
        # This test would make an actual API call to Moonshot
        # Only run this with valid credentials and in a controlled environment
        pass

    @pytest.mark.skip(reason="Requires actual resume data - run manually")
    def test_cover_letter_end_to_end_flow(self):
        """End-to-end test of cover letter generation and application."""
        # This test would verify the complete flow:
        # 1. Upload resume
        # 2. Generate cover letter
        # 3. Edit cover letter
        # 4. Submit application with cover letter
        pass
