"""
Job Applier API - FastAPI Backend
Handles resume upload, job search, and application orchestration.
With authentication, database persistence, and proper security.
"""

import os
import json
import re
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, EmailStr, validator

# Local imports
import sys
sys.path.append(str(Path(__file__).parent.parent))

from api.config import config, get_config
from api.auth import (
    get_current_user, get_optional_user, create_access_token, create_refresh_token,
    hash_password, verify_password, encrypt_sensitive_data, decrypt_sensitive_data
)
from api.database import (
    init_database, create_user, get_user_by_email, get_user_by_id,
    save_profile, get_profile, save_resume, get_latest_resume, update_resume_tailored,
    save_application, get_applications, get_applications_since, get_application, count_applications_since,
    save_settings, get_settings,
    create_campaign, get_campaign, list_campaigns, set_campaign_status,
    enqueue_jobs, get_queue_counts, list_queue_items, cancel_campaign_queue
)
from api.logging_config import logger, log_application, log_ai_request

from ai.kimi_service import KimiResumeOptimizer
from core.resume_file_parser import extract_text_from_upload

# Browser manager is optional. Importing core may succeed even if optional
# browser dependencies are missing, so instantiate defensively.
try:
    from core import UnifiedBrowserManager  # type: ignore
except Exception:
    UnifiedBrowserManager = None

browser_manager = None
BROWSER_AVAILABLE = False
if UnifiedBrowserManager is not None:
    try:
        browser_manager = UnifiedBrowserManager()
        BROWSER_AVAILABLE = True
    except Exception as e:
        logger.warning(f"Browser automation unavailable: {e}")
        browser_manager = None
        BROWSER_AVAILABLE = False

from adapters import (
    get_adapter, detect_platform_from_url,
    SearchConfig, UserProfile, Resume, ApplicationStatus
)

# ATS Automation System
try:
    from ats_automation.api_endpoints import include_ats_routes
    ATS_AVAILABLE = True
except ImportError:
    ATS_AVAILABLE = False

# Parallel processing for batch applications
from api.parallel_processor import (
    ParallelApplicationProcessor,
    process_applications_parallel,
    BatchApplicationStats
)

# Shared application engine + persistent queue worker
from api.application_engine import ApplyOptions, RateLimitError, apply_job_url
from api.queue_worker import QueueWorker
from monitoring.notifications import notifications


# === Lifespan Management ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    logger.info("Starting Job Applier API...")
    await init_database()
    logger.info("Database initialized")

    # Start persistent queue worker (optional).
    try:
        enabled = os.getenv("QUEUE_WORKER_ENABLED", "true").lower() == "true"
        if enabled and BROWSER_AVAILABLE and browser_manager is not None:
            qw = QueueWorker(browser_manager=browser_manager, kimi=kimi)
            qw.start()
            app.state.queue_worker = qw
            logger.info("Queue worker enabled")
        else:
            logger.info("Queue worker disabled")
    except Exception as e:
        logger.warning(f"Queue worker failed to start: {e}")

    yield
    # Shutdown
    logger.info("Shutting down Job Applier API...")
    try:
        qw = getattr(app.state, "queue_worker", None)
        if qw:
            await qw.stop()
    except Exception:
        pass
    if browser_manager is not None:
        await browser_manager.close_all()
        logger.info("Browser sessions closed")


# Initialize FastAPI app
app = FastAPI(
    title="Job Applier API",
    description="Automated job application service with AI resume optimization",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if config.DEBUG else None,
    redoc_url="/redoc" if config.DEBUG else None,
)

# CORS configuration - restricted to specific origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=config.CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# Include ATS automation routes
if ATS_AVAILABLE:
    include_ats_routes(app)
    logger.info("ATS automation routes included")


# === Request Logging Middleware ===

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests."""
    start_time = datetime.now()
    response = await call_next(request)
    duration = (datetime.now() - start_time).total_seconds() * 1000
    logger.info(f"{request.method} {request.url.path} -> {response.status_code} ({duration:.2f}ms)")
    return response


# Data directory
DATA_DIR = Path(config.DATA_DIR)
DATA_DIR.mkdir(exist_ok=True)


# === Pydantic Models with Validation ===

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)

    @validator('password')
    def password_strength(cls, v):
        if not re.search(r'[A-Za-z]', v) or not re.search(r'\d', v):
            raise ValueError('Password must contain letters and numbers')
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SearchRequest(BaseModel):
    roles: List[str] = Field(default=[], example=["Software Engineer", "Backend Developer"])
    locations: List[str] = Field(default=[], example=["San Francisco", "Remote"])
    easy_apply_only: bool = False
    posted_within_days: int = Field(default=7, ge=1, le=30)
    required_keywords: List[str] = Field(default_factory=list)
    exclude_keywords: List[str] = Field(default_factory=list)
    country: str = Field(default="US", pattern="^(US|CA|GB|DE|FR|AU|IN|NL|SG|ALL)$")
    careers_url: Optional[str] = Field(default=None)
    # Smart filtering/scoring (P0/P1)
    use_resume_match: bool = True
    min_match_score: float = Field(default=0.0, ge=0.0, le=1.0)
    allow_clearance_jobs: bool = False
    skip_senior_for_junior: bool = True
    max_results: int = Field(default=100, ge=1, le=500)

    @validator('roles')
    def validate_roles(cls, v):
        if len(v) > 10:
            raise ValueError('Maximum 10 roles allowed')
        return [role[:100] for role in v]  # Limit role length


class UserProfileRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: str = Field(..., pattern=r'^[\d\s\-\+\(\)]{7,20}$')
    linkedin_url: Optional[str] = Field(default=None, max_length=200)
    location: Optional[str] = Field(default=None, max_length=200)
    website: Optional[str] = Field(default=None, max_length=200)
    github_url: Optional[str] = Field(default=None, max_length=200)
    portfolio_url: Optional[str] = Field(default=None, max_length=200)
    years_experience: Optional[int] = Field(default=None, ge=0, le=50)
    work_authorization: str = Field(default="Yes", pattern="^(Yes|No)$")
    sponsorship_required: str = Field(default="No", pattern="^(Yes|No)$")
    custom_answers: dict = Field(default_factory=dict)


class ApplicationRequest(BaseModel):
    job_url: str = Field(..., max_length=500)
    auto_submit: bool = False
    generate_cover_letter: bool = True
    cover_letter_tone: str = Field(default="professional", pattern="^(professional|casual|enthusiastic)$")

    @validator('job_url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Invalid URL format')
        return v


class TailorResumeRequest(BaseModel):
    job_description: str = Field(..., min_length=50, max_length=10000)
    optimization_type: str = Field(default="balanced", pattern="^(conservative|balanced|aggressive)$")


class UserSettingsRequest(BaseModel):
    daily_limit: int = Field(default=10, ge=1, le=1000)
    linkedin_cookie: Optional[str] = Field(default=None, max_length=500)
    slack_webhook_url: Optional[str] = Field(default=None, max_length=500)
    discord_webhook_url: Optional[str] = Field(default=None, max_length=500)
    email_notifications_to: Optional[str] = Field(default=None, max_length=500)
    platform_daily_limits: Optional[dict] = Field(default=None)


class JobTitleSuggestion(BaseModel):
    title: str
    relevance_score: int = Field(..., ge=0, le=100)
    reason: str
    experience_level: str = Field(..., pattern="^(entry|mid|senior|executive)$")
    keywords: List[str] = Field(default_factory=list)


class TitleSuggestionResponse(BaseModel):
    resume_id: str
    suggested_roles: List[str]
    titles: List[JobTitleSuggestion]
    experience_level: str
    years_experience: int
    salary_range: dict
    keywords: List[str]
    best_fit: Optional[JobTitleSuggestion]


class TestApplicationRequest(BaseModel):
    job_folder_path: str = Field(..., min_length=1, max_length=500)
    auto_submit: bool = False  # When False, only fills forms, doesn't submit
    log_activity: bool = True


class TestApplicationResult(BaseModel):
    job_id: str
    job_title: str
    company: str
    status: str  # "success", "failed", "skipped"
    form_fields_filled: int
    form_fields_total: int
    errors: List[str] = Field(default_factory=list)
    screenshot_path: Optional[str] = None
    activity_log: List[dict] = Field(default_factory=list)


class TestCampaignResponse(BaseModel):
    test_id: str
    folder_path: str
    total_jobs: int
    processed: int
    successful: int
    failed: int
    results: List[TestApplicationResult]
    summary: str


# === Utility Functions ===

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal."""
    # First, get just the basename (remove any path components)
    filename = os.path.basename(filename)
    # Remove path separators and other dangerous characters
    sanitized = re.sub(r'[/\\:*?"<>|]', '_', filename)
    # Remove any leading dots or spaces
    sanitized = sanitized.lstrip('. ')
    # Remove any remaining '..' sequences
    sanitized = sanitized.replace('..', '_')
    # Limit length
    name, ext = os.path.splitext(sanitized)
    return f"{name[:50]}{ext[:10]}"


def validate_file_extension(filename: str) -> bool:
    """Validate file has allowed extension."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in config.ALLOWED_EXTENSIONS


def _build_profile_suggestion(parsed_data: dict) -> dict:
    """Build a best-effort profile suggestion from parsed resume data."""
    contact = (parsed_data or {}).get("contact") or {}
    name = (contact.get("name") or "").strip()
    first_name = ""
    last_name = ""
    if name:
        parts = [p for p in name.split() if p]
        if parts:
            first_name = parts[0]
            last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
    return {
        "first_name": first_name,
        "last_name": last_name,
        "email": (contact.get("email") or "").strip(),
        "phone": (contact.get("phone") or "").strip(),
        "linkedin_url": (contact.get("linkedin") or "").strip() or None,
        "location": (contact.get("location") or "").strip(),
        "years_experience": None,
        "work_authorization": "Yes",
        "sponsorship_required": "No",
        "custom_answers": {},
    }


def _build_job_preferences(parsed_data: dict, raw_text: str, suggested_titles: list) -> dict:
    """Best-effort job preference inference from resume + AI title suggestions."""
    text = (raw_text or "").lower()
    remote_pref = "unknown"
    if "hybrid" in text:
        remote_pref = "hybrid"
    elif "remote" in text or "work from home" in text:
        remote_pref = "remote"
    elif "on-site" in text or "onsite" in text:
        remote_pref = "onsite"

    contact = (parsed_data or {}).get("contact") or {}
    location = (contact.get("location") or "").strip()

    roles: list[str] = []
    for item in suggested_titles or []:
        if isinstance(item, str):
            roles.append(item)
        elif isinstance(item, dict) and item.get("title"):
            roles.append(str(item.get("title")))
    roles = [r.strip() for r in roles if r and r.strip()]

    return {
        "remote_preference": remote_pref,
        "preferred_locations": [location] if location else [],
        "preferred_roles": roles[:10],
    }


def _detect_pii_warnings(text: str) -> list[dict]:
    """Detect common PII patterns and return warnings."""
    warnings: list[dict] = []

    if re.search(r"\b\d{3}-\d{2}-\d{4}\b", text):
        warnings.append({"type": "SSN", "message": "Social Security Number pattern detected"})

    # Basic credit card patterns; does not validate Luhn by design (just warning).
    if re.search(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", text):
        warnings.append({"type": "CREDIT_CARD", "message": "Credit card number pattern detected"})

    return warnings


def _extract_contact_fallback(raw_text: str) -> dict:
    """Heuristic extraction of contact details from raw resume text."""
    text = raw_text or ""
    email_match = re.search(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", text, re.I)
    phone_match = re.search(r"(\+?\d[\d\s\-\(\)]{7,}\d)", text)

    # Name heuristic: first non-empty line with letters, excluding common section headers.
    name = ""
    for line in (ln.strip() for ln in text.splitlines()):
        if not line:
            continue
        if len(line) > 80:
            continue
        lower = line.lower()
        if lower in {"experience", "education", "skills", "summary", "projects", "certifications"}:
            continue
        if re.search(r"[a-zA-Z]", line) and not re.search(r"@", line):
            name = line
            break

    return {
        "name": name,
        "email": email_match.group(0) if email_match else "",
        "phone": phone_match.group(1).strip() if phone_match else "",
    }


_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have", "in",
    "is", "it", "its", "of", "on", "or", "that", "the", "this", "to", "was", "were", "will",
    "with", "you", "your",
}


def _tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    # Keep alphanumerics and a few tech symbols; everything else to space.
    text = re.sub(r"[^a-z0-9\+\#\.\-]+", " ", text)
    toks = [t.strip(".-") for t in text.split() if t.strip(".-")]
    return [t for t in toks if len(t) >= 3 and t not in _STOPWORDS]


def _extract_resume_keywords(raw_text: str, parsed_data: dict) -> set[str]:
    keywords: set[str] = set()

    parsed = parsed_data or {}
    for skill in parsed.get("skills") or []:
        for tok in _tokenize(str(skill)):
            keywords.add(tok)

    # Backfill from raw text using most frequent tokens.
    try:
        from collections import Counter

        counts = Counter(_tokenize(raw_text))
        for tok, _ in counts.most_common(120):
            keywords.add(tok)
    except Exception:
        pass

    return keywords


def _keyword_overlap_score(resume_keywords: set[str], job_text: str) -> float:
    if not resume_keywords:
        return 0.0
    job_tokens = set(_tokenize(job_text))
    if not job_tokens:
        return 0.0
    overlap = len(resume_keywords.intersection(job_tokens))
    denom = max(1, min(len(resume_keywords), 60))
    return max(0.0, min(1.0, overlap / denom))


def _detect_clearance_requirement(text: str) -> Optional[str]:
    t = (text or "").lower()
    patterns = [
        r"\bts\/sci\b",
        r"\btop secret\b",
        r"\bsecret clearance\b",
        r"\bsecurity clearance\b",
        r"\bclearance required\b",
        r"\bpolygraph\b",
        r"\bpublic trust\b",
    ]
    for pat in patterns:
        if re.search(pat, t):
            return pat.strip("\\b")
    return None


def _estimate_years_experience_from_parsed(parsed_data: dict) -> Optional[int]:
    exp = (parsed_data or {}).get("experience") or []
    years: list[int] = []
    for item in exp:
        dates = str((item or {}).get("dates") or "")
        found = re.findall(r"(?:19|20)\d{2}", dates)
        for y in found:
            try:
                years.append(int(y))
            except Exception:
                continue
    if len(years) >= 2:
        return max(years) - min(years)
    if len(years) == 1:
        now_year = datetime.now().year
        return max(0, now_year - years[0])
    return None


def _is_seniorish_title(title: str) -> bool:
    t = (title or "").lower()
    return bool(re.search(r"\b(senior|sr\.?|lead|principal|staff|manager|director|vp|head)\b", t))


def _is_very_senior_title(title: str) -> bool:
    t = (title or "").lower()
    return bool(re.search(r"\b(principal|staff|director|vp|head)\b", t))


# Initialize services
kimi = KimiResumeOptimizer()


# === API Endpoints ===

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Job Applier API v2.0", "docs": "/docs" if config.DEBUG else "disabled"}


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "browser_available": BROWSER_AVAILABLE,
        "version": "2.0.0"
    }


# === Authentication Endpoints ===

@app.post("/auth/register")
async def register(request: RegisterRequest):
    """Register a new user."""
    user_id = str(uuid.uuid4())
    hashed = hash_password(request.password)

    success = await create_user(user_id, request.email, hashed)
    if not success:
        raise HTTPException(status_code=400, detail="Email already registered")

    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    logger.info(f"New user registered: {request.email}")
    log_activity("REGISTER", request.email, {"user_id": user_id})

    return {
        "message": "Registration successful",
        "user_id": user_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@app.post("/auth/login")
async def login(request: LoginRequest):
    """Login and get access token."""
    user = await get_user_by_email(request.email)
    if not user or not verify_password(request.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account disabled")

    access_token = create_access_token(user["id"])
    refresh_token = create_refresh_token(user["id"])

    logger.info(f"User logged in: {request.email}")
    log_activity("LOGIN", request.email)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": user["id"]
    }


@app.post("/auth/refresh")
async def refresh_token(current_user: str = Depends(get_current_user)):
    """Refresh access token."""
    access_token = create_access_token(current_user)
    return {"access_token": access_token, "token_type": "bearer"}


# === User Settings & Rate Limits ===

@app.get("/settings")
async def get_user_settings(user_id: str = Depends(get_current_user)):
    """Get user settings including rate limit status."""
    settings = await get_settings(user_id) or {"daily_limit": config.DEFAULT_DAILY_LIMIT}
    cutoff = datetime.now() - timedelta(hours=24)
    sent_24h = await count_applications_since(user_id, cutoff)
    daily_limit = settings.get("daily_limit", config.DEFAULT_DAILY_LIMIT)

    return {
        "daily_limit": daily_limit,
        "sent_last_24h": sent_24h,
        "remaining": max(0, daily_limit - sent_24h),
        "can_apply": sent_24h < daily_limit,
        "reset_info": "Rolling 24-hour window",
        "linkedin_cookie_set": bool(settings.get("linkedin_cookie_encrypted")),
        "slack_webhook_set": bool(settings.get("slack_webhook_url") or os.getenv("SLACK_WEBHOOK_URL")),
        "discord_webhook_set": bool(settings.get("discord_webhook_url") or os.getenv("DISCORD_WEBHOOK_URL")),
        "email_notifications_to": settings.get("email_notifications_to"),
        "platform_daily_limits": json.loads(settings.get("platform_daily_limits_json") or "null")
    }


@app.post("/settings")
async def update_user_settings(request: UserSettingsRequest, user_id: str = Depends(get_current_user)):
    """Update user settings."""
    settings_data = {"daily_limit": request.daily_limit}

    # Encrypt LinkedIn cookie if provided
    if request.linkedin_cookie:
        settings_data["linkedin_cookie_encrypted"] = encrypt_sensitive_data(request.linkedin_cookie)
        logger.info(f"LinkedIn cookie updated for user {user_id}")

    # Optional notification + platform throttles
    if request.slack_webhook_url is not None:
        settings_data["slack_webhook_url"] = request.slack_webhook_url.strip() if request.slack_webhook_url else None
    if request.discord_webhook_url is not None:
        settings_data["discord_webhook_url"] = request.discord_webhook_url.strip() if request.discord_webhook_url else None
    if request.email_notifications_to is not None:
        settings_data["email_notifications_to"] = (
            request.email_notifications_to.strip() if request.email_notifications_to else None
        )
    if request.platform_daily_limits is not None:
        settings_data["platform_daily_limits_json"] = json.dumps(request.platform_daily_limits)

    await save_settings(user_id, settings_data)

    cutoff = datetime.now() - timedelta(hours=24)
    sent_24h = await count_applications_since(user_id, cutoff)

    return {
        "message": "Settings updated",
        "daily_limit": request.daily_limit,
        "linkedin_cookie_set": bool(request.linkedin_cookie),
        "sent_last_24h": sent_24h,
        "remaining": max(0, request.daily_limit - sent_24h)
    }


@app.get("/platforms")
async def get_platforms():
    """Get list of supported job platforms."""
    return {
        "platforms": [
            {"id": "linkedin", "name": "LinkedIn", "search_supported": True, "easy_apply": True},
            {"id": "indeed", "name": "Indeed", "search_supported": True, "easy_apply": True},
            {"id": "greenhouse", "name": "Greenhouse", "search_supported": True, "easy_apply": True},
            {"id": "workday", "name": "Workday", "search_supported": False, "easy_apply": False},
            {"id": "lever", "name": "Lever", "search_supported": True, "easy_apply": True}
        ]
    }


# === Resume Endpoints ===

@app.post("/resume/upload")
async def upload_resume(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user)
):
    """Upload and parse a resume file."""
    # Validate file extension
    if not validate_file_extension(file.filename):
        raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed: {config.ALLOWED_EXTENSIONS}")

    # Validate file size
    content = await file.read()
    if len(content) > config.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large. Max: {config.MAX_UPLOAD_SIZE_MB}MB")

    # Sanitize filename and save
    safe_filename = sanitize_filename(file.filename)
    file_path = DATA_DIR / f"resume_{user_id}_{safe_filename}"

    with open(file_path, "wb") as f:
        f.write(content)

    # Extract text (PDF/DOCX/TXT)
    extraction = extract_text_from_upload(file.filename, content)
    raw_text = extraction.text or ""
    pii_warnings = _detect_pii_warnings(raw_text)

    # Parse with Kimi AI
    try:
        parsed_data = await kimi.parse_resume(raw_text)
    except Exception as e:
        logger.error(f"Resume parsing failed: {e}")
        parsed_data = {"error": "Parsing failed", "raw_available": True}

    # Generate suggested job titles based on resume
    suggested_titles = []
    try:
        suggested_titles = await kimi.suggest_job_titles(raw_text[:3000])
    except Exception as e:
        logger.warning(f"Job title suggestion failed: {e}")

    profile_suggestion = _build_profile_suggestion(parsed_data)
    years_exp = _estimate_years_experience_from_parsed(parsed_data)
    if years_exp is not None:
        profile_suggestion["years_experience"] = years_exp

    job_preferences = _build_job_preferences(parsed_data, raw_text, suggested_titles)

    # Save to database
    await save_resume(user_id, str(file_path), raw_text, parsed_data)

    logger.info(f"Resume uploaded for user {user_id}: {safe_filename}")
    user = await get_user_by_id(user_id)
    log_activity("RESUME_UPLOAD", user.get("email") if user else user_id, {
        "filename": safe_filename,
        "size_kb": len(content) // 1024,
        "suggested_titles": suggested_titles[:3] if suggested_titles else []
    })

    return {
        "message": "Resume uploaded and parsed",
        "file_path": str(file_path),
        "extraction_warnings": extraction.warnings,
        "pii_warnings": pii_warnings,
        "parsed_data": parsed_data,
        "suggested_titles": suggested_titles,
        "profile_suggestion": profile_suggestion,
        "job_preferences": job_preferences,
    }


@app.post("/resume/tailor")
async def tailor_resume(
    request: TailorResumeRequest,
    user_id: str = Depends(get_current_user)
):
    """Tailor resume to a specific job description."""
    resume = await get_latest_resume(user_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found. Upload first.")

    try:
        result = await kimi.tailor_resume(
            resume["raw_text"],
            request.job_description,
            request.optimization_type
        )
        await update_resume_tailored(resume["id"], result)
        log_ai_request("kimi", "tailor_resume")
        return result
    except Exception as e:
        log_ai_request("kimi", "tailor_resume", error=str(e))
        raise HTTPException(status_code=500, detail=f"Tailoring failed: {str(e)}")


@app.get("/resume/suggest-titles", response_model=TitleSuggestionResponse)
async def suggest_job_titles(user_id: str = Depends(get_current_user)):
    """
    Analyze uploaded resume and suggest relevant job titles.
    
    Returns AI-powered job title recommendations based on:
    - Current and past job titles
    - Skills and technologies
    - Years of experience
    - Industry background
    """
    resume = await get_latest_resume(user_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found. Upload first.")
    
    try:
        # Get comprehensive search config including title suggestions
        search_config = await kimi.suggest_job_search_config(resume["raw_text"])
        
        log_ai_request("kimi", "suggest_job_titles", extra={"suggestions_count": len(search_config["suggested_roles"])})
        
        # Log activity for frontend visibility
        await _log_user_activity(
            user_id=user_id,
            action="RESUME_TITLE_SUGGESTION",
            details={
                "suggested_roles": search_config["suggested_roles"],
                "experience_level": search_config["experience_level"]
            }
        )
        
        return TitleSuggestionResponse(
            resume_id=resume["id"],
            suggested_roles=search_config["suggested_roles"],
            titles=search_config["titles_with_scores"],
            experience_level=search_config["experience_level"],
            years_experience=search_config["years_experience"],
            salary_range=search_config["salary_range"],
            keywords=search_config["keywords"],
            best_fit=search_config["best_fit"]
        )
    except Exception as e:
        logger.error(f"Error suggesting job titles: {e}")
        log_ai_request("kimi", "suggest_job_titles", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to suggest titles: {str(e)}")


class SuggestTitlesTextRequest(BaseModel):
    resume_text: str = Field(..., min_length=100)


@app.post("/resume/suggest-titles-from-text")
async def suggest_titles_from_text(request: SuggestTitlesTextRequest):
    """
    Direct API to suggest job titles from raw resume text.
    Useful for testing without database persistence.
    """
    try:
        search_config = await kimi.suggest_job_search_config(request.resume_text)
        return search_config
    except Exception as e:
        logger.error(f"Error suggesting titles from text: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# === Profile Endpoints ===

@app.post("/profile")
async def save_user_profile(profile: UserProfileRequest, user_id: str = Depends(get_current_user)):
    """Save user profile for applications."""
    await save_profile(user_id, profile.dict())
    logger.info(f"Profile saved for user {user_id}")
    log_activity("PROFILE_SAVE", profile.email, {
        "name": f"{profile.first_name} {profile.last_name}",
        "phone": profile.phone[:4] + "****" if profile.phone else None
    })
    return {"message": "Profile saved", "profile": profile.dict()}


@app.get("/profile")
async def get_user_profile(user_id: str = Depends(get_current_user)):
    """Get user profile."""
    profile = await get_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@app.post("/profile/auto")
async def auto_generate_profile(user_id: str = Depends(get_current_user)):
    """
    Auto-generate a user profile from the latest uploaded resume.
    This enables "drag and drop resume, then go" workflows.
    """
    resume = await get_latest_resume(user_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found. Upload first.")

    parsed = resume.get("parsed_data") or {}
    suggestion = _build_profile_suggestion(parsed)
    years_exp = _estimate_years_experience_from_parsed(parsed)
    if years_exp is not None and not suggestion.get("years_experience"):
        suggestion["years_experience"] = years_exp

    # Fallback extraction if AI parse omitted fields.
    fallback = _extract_contact_fallback(resume.get("raw_text") or "")
    if not suggestion.get("email") and fallback.get("email"):
        suggestion["email"] = fallback["email"]
    if not suggestion.get("phone") and fallback.get("phone"):
        suggestion["phone"] = fallback["phone"]
    if not (suggestion.get("first_name") or suggestion.get("last_name")) and fallback.get("name"):
        parts = [p for p in fallback["name"].split() if p]
        if parts:
            suggestion["first_name"] = parts[0]
            suggestion["last_name"] = " ".join(parts[1:]) if len(parts) > 1 else ""

    missing = [k for k in ["first_name", "last_name", "email", "phone"] if not suggestion.get(k)]
    if missing:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Could not fully auto-generate profile; please confirm missing fields.",
                "missing_fields": missing,
                "profile_suggestion": suggestion,
            },
        )

    await save_profile(user_id, suggestion)
    return {"message": "Profile auto-generated", "profile": suggestion}


# === Job Search Endpoints ===

async def _search_jobs_jobspy(request: SearchRequest, platform: str) -> list[dict]:
    """
    Cookie-less job discovery using python-jobspy (public scraping).
    Returns list of job dicts with stable keys for API response.
    """
    try:
        from jobspy import scrape_jobs  # type: ignore
    except Exception as e:
        # Fallback to vendored submodule if available.
        try:
            jobspy_root = Path(__file__).parent.parent / "src" / "python-jobspy"
            if jobspy_root.exists():
                sys.path.append(str(jobspy_root))
            from jobspy import scrape_jobs  # type: ignore
        except Exception:
            raise RuntimeError(f"JobSpy not available: {e}")

    roles = request.roles or ["software engineer"]
    search_term = " OR ".join(roles)

    location = request.locations[0] if request.locations else ""
    is_remote = any((loc or "").lower() == "remote" for loc in (request.locations or []))
    if is_remote:
        location = ""

    hours_old = int(request.posted_within_days * 24)

    # JobSpy returns a pandas DataFrame
    results_wanted = min(int(request.max_results or 100), 200)
    jobs_df = scrape_jobs(
        site_name=[platform],
        search_term=search_term,
        location=location,
        results_wanted=results_wanted,
        hours_old=hours_old,
        is_remote=is_remote,
        easy_apply=request.easy_apply_only,
        description_format="markdown",
        linkedin_fetch_description=True if platform == "linkedin" else False,
        verbose=0,
        country_indeed=request.country if platform == "indeed" else None,
    )

    if jobs_df is None:
        return []

    jobs: list[dict] = []
    try:
        records = jobs_df.to_dict("records")
    except Exception:
        # If jobspy changes return type, try iterating rows
        records = []

    for row in records:
        url = str(row.get("job_url") or "")
        if not url:
            continue
        direct_url = str(row.get("job_url_direct") or "").strip()
        apply_url = direct_url if direct_url.startswith(("http://", "https://")) else url
        title = str(row.get("title") or "").strip()
        company = str(row.get("company") or "").strip()
        location_str = str(row.get("location") or "").strip()
        desc = row.get("description") or ""
        try:
            easy_apply = bool(row.get("easy_apply")) if "easy_apply" in row else False
        except Exception:
            easy_apply = False

        jobs.append(
            {
                "id": f"{platform}_{abs(hash(url)) % 10000000}",
                "title": title or "(see posting)",
                "company": company or "(see posting)",
                "location": location_str,
                "url": url,
                "direct_url": direct_url or None,
                "apply_url": apply_url,
                "easy_apply": easy_apply,
                "remote": ("remote" in location_str.lower()) if location_str else is_remote,
                "description": str(desc)[:2000] if desc else None,
            }
        )

    return jobs


@app.post("/jobs/search")
async def search_jobs(request: SearchRequest, platform: str = "linkedin", user_id: str = Depends(get_current_user)):
    """Search for jobs across platforms."""
    if platform not in ["linkedin", "indeed", "greenhouse", "lever", "company"]:
        raise HTTPException(status_code=400, detail="Search only supported for: linkedin, indeed, greenhouse, lever, company")

    if platform == "company" and not request.careers_url:
        raise HTTPException(status_code=400, detail="Company platform requires careers_url")

    try:
        # Prefer cookie-less scraping for common boards.
        jobs_payload: list[dict]

        if platform in ["linkedin", "indeed"]:
            jobs_payload = await _search_jobs_jobspy(request, platform)
        elif platform in ["greenhouse", "lever"]:
            # Public board APIs (no browser required).
            search_config = SearchConfig(
                roles=request.roles,
                locations=request.locations,
                easy_apply_only=request.easy_apply_only,
                posted_within_days=request.posted_within_days,
                required_keywords=request.required_keywords,
                exclude_keywords=request.exclude_keywords,
                country=request.country,
                careers_url=request.careers_url,
            )
            adapter = get_adapter(platform, browser_manager, use_unified=False)
            jobs = await adapter.search_jobs(search_config)
            jobs_payload = [
                {
                    "id": j.id,
                    "title": j.title,
                    "company": j.company,
                    "location": j.location,
                    "url": j.url,
                    "direct_url": None,
                    "apply_url": j.url,
                    "easy_apply": j.easy_apply,
                    "remote": j.remote,
                    "description": (j.description or "")[:2000] if getattr(j, "description", None) else None,
                }
                for j in jobs
            ]
        else:
            # Company careers pages require browser automation.
            if not BROWSER_AVAILABLE or not browser_manager:
                raise HTTPException(status_code=503, detail="Browser automation not available")

            search_config = SearchConfig(
                roles=request.roles,
                locations=request.locations,
                easy_apply_only=request.easy_apply_only,
                posted_within_days=request.posted_within_days,
                required_keywords=request.required_keywords,
                exclude_keywords=request.exclude_keywords,
                country=request.country,
                careers_url=request.careers_url,
            )

            adapter = get_adapter(platform, browser_manager, use_unified=False)
            jobs = await adapter.search_jobs(search_config)
            jobs_payload = [
                {
                    "id": j.id,
                    "title": j.title,
                    "company": j.company,
                    "location": j.location,
                    "url": j.url,
                    "easy_apply": j.easy_apply,
                    "remote": j.remote,
                }
                for j in jobs
            ]

        # Optional smart scoring/filtering using the user's resume/profile.
        resume_keywords: set[str] = set()
        candidate_years: Optional[int] = None
        if request.use_resume_match or request.skip_senior_for_junior:
            latest_resume = await get_latest_resume(user_id)
            latest_profile = await get_profile(user_id)
            if latest_resume:
                resume_keywords = _extract_resume_keywords(
                    latest_resume.get("raw_text") or "",
                    latest_resume.get("parsed_data") or {},
                )
                candidate_years = (
                    (latest_profile or {}).get("years_experience")
                    or _estimate_years_experience_from_parsed(latest_resume.get("parsed_data") or {})
                )
            elif latest_profile:
                candidate_years = latest_profile.get("years_experience")

        filtered: list[dict] = []
        skipped: list[dict] = []
        skip_reason_counts: dict[str, int] = {}

        for job in jobs_payload:
            title = str(job.get("title") or "")
            desc = str(job.get("description") or "")
            job_text = f"{title}\n{desc}"

            clearance_hit = _detect_clearance_requirement(job_text)
            if clearance_hit and not request.allow_clearance_jobs:
                job["skip_reason"] = "clearance_required"
                skipped.append(job)
                skip_reason_counts["clearance_required"] = skip_reason_counts.get("clearance_required", 0) + 1
                continue

            if request.skip_senior_for_junior and candidate_years is not None:
                if candidate_years <= 2 and _is_seniorish_title(title):
                    job["skip_reason"] = "senior_role_for_junior_candidate"
                    skipped.append(job)
                    skip_reason_counts["senior_role_for_junior_candidate"] = (
                        skip_reason_counts.get("senior_role_for_junior_candidate", 0) + 1
                    )
                    continue
                if candidate_years <= 5 and _is_very_senior_title(title):
                    job["skip_reason"] = "very_senior_role_for_mid_candidate"
                    skipped.append(job)
                    skip_reason_counts["very_senior_role_for_mid_candidate"] = (
                        skip_reason_counts.get("very_senior_role_for_mid_candidate", 0) + 1
                    )
                    continue

            if request.use_resume_match and resume_keywords:
                score = _keyword_overlap_score(resume_keywords, job_text)
                job["match_score"] = round(score, 3)
                if request.min_match_score and score < request.min_match_score:
                    job["skip_reason"] = "low_match_score"
                    skipped.append(job)
                    skip_reason_counts["low_match_score"] = skip_reason_counts.get("low_match_score", 0) + 1
                    continue
            else:
                job["match_score"] = None

            filtered.append(job)

        # Prioritize Easy Apply and higher match scores.
        filtered.sort(
            key=lambda j: (
                bool(j.get("easy_apply")),
                float(j.get("match_score") or 0.0),
            ),
            reverse=True,
        )
        filtered = filtered[: int(request.max_results or 100)]

        logger.info(
            f"Search completed for user {user_id}: {len(filtered)} jobs returned on {platform} "
            f"(skipped={len(skipped)})"
        )

        return {
            "platform": platform,
            "count": len(filtered),
            "skipped": len(skipped),
            "skip_reasons": skip_reason_counts,
            "candidate_years_experience": candidate_years,
            "jobs": filtered,
        }
    except Exception as e:
        logger.error(f"Search failed: {e}")
        if isinstance(e, RuntimeError) and "JobSpy not available" in str(e):
            raise HTTPException(status_code=503, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'adapter' in locals() and hasattr(adapter, "close"):
            await adapter.close()


# === Autopilot Campaign (Zero-Config) ===

class AutopilotCampaignRequest(BaseModel):
    platforms: List[str] = Field(default_factory=lambda: ["greenhouse", "lever", "indeed", "linkedin"])
    max_apply: int = Field(default=10, ge=1, le=50)
    start_apply: bool = False
    auto_submit: bool = False
    easy_apply_only: bool = True
    posted_within_days: int = Field(default=7, ge=1, le=30)
    min_match_score: float = Field(default=0.15, ge=0.0, le=1.0)
    allow_clearance_jobs: bool = False
    roles: Optional[List[str]] = None
    locations: Optional[List[str]] = None


@app.post("/campaign/autopilot")
async def autopilot_campaign(
    request: AutopilotCampaignRequest,
    user_id: str = Depends(get_current_user),
):
    """
    "Drag & Drop Resume, Then Go" autopilot.

    Flow:
    - Uses latest resume
    - Auto-generates profile if missing (or returns missing fields)
    - Suggests roles/keywords from resume
    - Searches across platforms
    - Filters + scores jobs
    - Optionally starts applying (batch)
    """
    resume = await get_latest_resume(user_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found. Upload first.")

    profile = await get_profile(user_id)
    if not profile:
        parsed = resume.get("parsed_data") or {}
        suggestion = _build_profile_suggestion(parsed)
        years_exp = _estimate_years_experience_from_parsed(parsed)
        if years_exp is not None:
            suggestion["years_experience"] = years_exp
        fallback = _extract_contact_fallback(resume.get("raw_text") or "")
        if not suggestion.get("email") and fallback.get("email"):
            suggestion["email"] = fallback["email"]
        if not suggestion.get("phone") and fallback.get("phone"):
            suggestion["phone"] = fallback["phone"]
        if not (suggestion.get("first_name") or suggestion.get("last_name")) and fallback.get("name"):
            parts = [p for p in fallback["name"].split() if p]
            if parts:
                suggestion["first_name"] = parts[0]
                suggestion["last_name"] = " ".join(parts[1:]) if len(parts) > 1 else ""

        missing = [k for k in ["first_name", "last_name", "email", "phone"] if not suggestion.get(k)]
        if missing:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Auto-profile incomplete; confirm missing fields and retry.",
                    "missing_fields": missing,
                    "profile_suggestion": suggestion,
                },
            )

        await save_profile(user_id, suggestion)
        profile = suggestion

    # Derive roles/locations from resume unless overridden.
    try:
        search_cfg = await kimi.suggest_job_search_config(resume.get("raw_text") or "")
    except Exception as e:
        logger.warning(f"Autopilot suggest_job_search_config failed: {e}")
        search_cfg = {}

    roles = request.roles or search_cfg.get("suggested_roles") or []
    roles = [r for r in roles if r][:8] or ["software engineer"]

    locations = request.locations or []
    if not locations:
        prof_loc = (profile.get("location") or "").strip()
        if prof_loc:
            locations.append(prof_loc)
        locations.append("Remote")
    locations = [l for l in locations if l][:5]

    # Search + score per platform.
    all_jobs: list[dict] = []
    per_platform: dict[str, dict] = {}

    for platform in request.platforms:
        sr = SearchRequest(
            roles=roles[:5],
            locations=locations[:3],
            easy_apply_only=request.easy_apply_only,
            posted_within_days=request.posted_within_days,
            required_keywords=search_cfg.get("keywords") or [],
            exclude_keywords=[],
            country="US",
            careers_url=None,
            use_resume_match=True,
            min_match_score=request.min_match_score,
            allow_clearance_jobs=request.allow_clearance_jobs,
            skip_senior_for_junior=True,
            max_results=max(50, min(200, request.max_apply * 10)),
        )
        try:
            resp = await search_jobs(sr, platform=platform, user_id=user_id)
            per_platform[platform] = {
                "count": resp.get("count", 0),
                "skipped": resp.get("skipped", 0),
                "skip_reasons": resp.get("skip_reasons", {}),
            }
            all_jobs.extend(resp.get("jobs") or [])
        except HTTPException as e:
            per_platform[platform] = {"error": e.detail}
        except Exception as e:
            per_platform[platform] = {"error": str(e)}

    # Deduplicate by apply_url/url.
    seen: set[str] = set()
    deduped: list[dict] = []
    for j in all_jobs:
        key = str(j.get("apply_url") or j.get("url") or "")
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        deduped.append(j)

    deduped.sort(
        key=lambda j: (
            bool(j.get("easy_apply")),
            float(j.get("match_score") or 0.0),
        ),
        reverse=True,
    )
    selected = deduped[: request.max_apply]

    # Optionally start applying by enqueuing a persistent campaign.
    apply_result = None
    campaign_id = None
    enqueued = 0
    if request.start_apply:
        if not BROWSER_AVAILABLE or not browser_manager:
            raise HTTPException(status_code=503, detail="Browser automation not available")

        # Prefer direct/apply URLs where possible.
        apply_urls = [
            str(j.get("apply_url") or j.get("url"))
            for j in selected
            if (j.get("apply_url") or j.get("url"))
        ]

        # Skip LinkedIn if no cookie is set.
        settings = await get_settings(user_id) or {}
        linkedin_cookie = settings.get("linkedin_cookie_encrypted")
        if not linkedin_cookie:
            filtered_apply_urls = []
            for url in apply_urls:
                if "linkedin.com/" in (url or ""):
                    continue
                filtered_apply_urls.append(url)
            apply_urls = filtered_apply_urls

        if apply_urls:
            campaign_id = await create_campaign(
                user_id=user_id,
                name=f"autopilot_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                config={
                    "source": "autopilot",
                    "auto_submit": request.auto_submit,
                    "generate_cover_letter": True,
                    "cover_letter_tone": "professional",
                },
                status="running",
            )
            jobs_to_enqueue = []
            for j in selected:
                url = str(j.get("apply_url") or j.get("url") or "").strip()
                if not url:
                    continue
                if (not linkedin_cookie) and "linkedin.com/" in url:
                    continue
                plat = detect_platform_from_url(url)
                jobs_to_enqueue.append(
                    {
                        "job_url": url,
                        "platform": plat.value if hasattr(plat, "value") else str(plat),
                        "payload": j,
                    }
                )
            enqueued = await enqueue_jobs(user_id, campaign_id, jobs_to_enqueue, priority=0, max_attempts=3)
            apply_result = {
                "campaign_id": campaign_id,
                "enqueued": enqueued,
                "message": "Enqueued. Processing will continue in the background.",
            }

    return {
        "roles": roles,
        "locations": locations,
        "search_config": search_cfg,
        "platforms": per_platform,
        "recommended": selected,
        "apply_result": apply_result,
        "campaign_id": campaign_id,
        "enqueued": enqueued,
    }


@app.get("/campaigns")
async def campaigns_list(user_id: str = Depends(get_current_user)):
    camps = await list_campaigns(user_id, limit=50)
    # Add queue counts for quick dashboard display.
    out = []
    for c in camps:
        counts = await get_queue_counts(c["id"])
        c["queue_counts"] = counts
        out.append(c)
    return {"campaigns": out}


@app.get("/campaigns/{campaign_id}")
async def campaigns_get(campaign_id: str, user_id: str = Depends(get_current_user)):
    camp = await get_campaign(campaign_id)
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if camp["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    camp["queue_counts"] = await get_queue_counts(campaign_id)
    return camp


@app.get("/campaigns/{campaign_id}/queue")
async def campaigns_queue(campaign_id: str, user_id: str = Depends(get_current_user), limit: int = 200):
    camp = await get_campaign(campaign_id)
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if camp["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    items = await list_queue_items(campaign_id, limit=limit)
    return {"campaign_id": campaign_id, "items": items}


@app.post("/campaigns/{campaign_id}/pause")
async def campaigns_pause(campaign_id: str, user_id: str = Depends(get_current_user)):
    camp = await get_campaign(campaign_id)
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if camp["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    await set_campaign_status(campaign_id, "paused")
    return {"message": "Campaign paused", "campaign_id": campaign_id}


@app.post("/campaigns/{campaign_id}/resume")
async def campaigns_resume(campaign_id: str, user_id: str = Depends(get_current_user)):
    camp = await get_campaign(campaign_id)
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if camp["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    await set_campaign_status(campaign_id, "running")
    return {"message": "Campaign resumed", "campaign_id": campaign_id}


@app.post("/campaigns/{campaign_id}/stop")
async def campaigns_stop(campaign_id: str, user_id: str = Depends(get_current_user)):
    camp = await get_campaign(campaign_id)
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if camp["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    await set_campaign_status(campaign_id, "stopped")
    await cancel_campaign_queue(campaign_id, reason="stopped_by_user")
    return {"message": "Campaign stopped", "campaign_id": campaign_id}


# === Notifications ===

class DailySummaryRequest(BaseModel):
    send_email: bool = False


@app.post("/notifications/test")
async def notifications_test(user_id: str = Depends(get_current_user)):
    settings = await get_settings(user_id) or {}
    await notifications.notify_application(
        {
            "user_id": user_id,
            "application_id": "test",
            "platform": "system",
            "job_title": "Test Notification",
            "company": "Job Applier",
            "job_url": "",
            "status": "info",
            "message": "This is a test notification from Job Applier.",
        },
        slack_url=settings.get("slack_webhook_url") or "",
        discord_url=settings.get("discord_webhook_url") or "",
    )
    return {"message": "Test notification sent (if configured)."}


@app.post("/notifications/daily-summary")
async def notifications_daily_summary(request: DailySummaryRequest, user_id: str = Depends(get_current_user)):
    since = datetime.now() - timedelta(hours=24)
    apps = await get_applications_since(user_id, since, limit=2000)

    def _count(status: str) -> int:
        return sum(1 for a in apps if str(a.get("status") or "").lower() == status)

    submitted = _count("submitted")
    pending_review = _count("pending_review")
    external = _count("external_application")
    errors = _count("error")
    total = len(apps)
    success_rate = round((submitted / max(1, total)) * 100, 1)

    summary = {
        "since": since.isoformat(),
        "total": total,
        "submitted": submitted,
        "pending_review": pending_review,
        "external_application": external,
        "errors": errors,
        "success_rate_pct": success_rate,
    }

    sent = False
    if request.send_email:
        settings = await get_settings(user_id) or {}
        to_email = settings.get("email_notifications_to") or (await get_user_by_id(user_id) or {}).get("email")
        if to_email:
            body = (
                "Job Applier daily summary (last 24h)\n\n"
                + json.dumps(summary, indent=2)
                + "\n"
            )
            sent = await notifications.send_email(to_email, "Job Applier Daily Summary", body)

    return {"summary": summary, "email_sent": sent}


# === Application Endpoints ===

@app.post("/apply")
async def apply_to_job(
    request: ApplicationRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user)
):
    """Apply to a specific job."""
    if not BROWSER_AVAILABLE or not browser_manager:
        raise HTTPException(status_code=503, detail="Browser automation not available")

    # Create placeholder application record so clients can poll immediately.
    application_id = f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    await save_application(
        {
            "id": application_id,
            "user_id": user_id,
            "job_url": request.job_url,
            "platform": str(detect_platform_from_url(request.job_url)),
            "status": "processing",
            "timestamp": datetime.now().isoformat(),
        }
    )

    async def do_apply():
        try:
            await apply_job_url(
                user_id=user_id,
                job_url=request.job_url,
                browser_manager=browser_manager,
                kimi=kimi,
                options=ApplyOptions(
                    auto_submit=request.auto_submit,
                    generate_cover_letter=request.generate_cover_letter,
                    cover_letter_tone=request.cover_letter_tone,
                    application_id=application_id,
                ),
            )
        except Exception as e:
            logger.error(f"Application {application_id} failed: {e}")
            await save_application({
                "id": application_id,
                "user_id": user_id,
                "job_url": request.job_url,
                "platform": str(detect_platform_from_url(request.job_url)),
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            log_application(application_id, user_id, request.job_url, "error", str(e))

    background_tasks.add_task(do_apply)

    return {
        "message": "Application started",
        "application_id": application_id,
        "status": "processing"
    }


class BatchApplicationRequest(BaseModel):
    """Request for batch job applications."""
    job_urls: List[str] = Field(..., min_items=1, max_items=50)
    auto_submit: bool = False
    generate_cover_letter: bool = True
    cover_letter_tone: str = Field(default="professional", pattern="^(professional|casual|enthusiastic)$")
    max_concurrent: int = Field(default=3, ge=1, le=35)
    target_apps_per_minute: float = Field(default=10.0, ge=1.0, le=20.0)


@app.post("/apply/batch")
async def apply_to_jobs_batch(
    request: BatchApplicationRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Apply to multiple jobs in parallel with rate limiting.
    
    Features:
    - Configurable concurrency (max 5 parallel)
    - Rate limiting (default: 10 apps/minute, max: 20 apps/minute)
    - Progress tracking
    - Automatic retry on failure
    
    **Theoretical Maximum Performance:**
    - With auto_submit=True: ~10 apps/minute (target rate)
    - With auto_submit=False (review mode): ~6-8 apps/minute
    - Peak burst: Up to 5 concurrent applications
    - Sustained rate: 10 applications per minute
    - Daily maximum: 10 apps/min × 60 min × 24 hr = 14,400 applications/day (limited by daily_limit setting)
    """
    if not BROWSER_AVAILABLE or not browser_manager:
        raise HTTPException(status_code=503, detail="Browser automation not available")
    
    # Check rate limits
    settings = await get_settings(user_id) or {}
    daily_limit = settings.get("daily_limit", config.DEFAULT_DAILY_LIMIT)
    cutoff = datetime.now() - timedelta(hours=24)
    sent_24h = await count_applications_since(user_id, cutoff)
    
    remaining_today = daily_limit - sent_24h
    if remaining_today <= 0:
        raise HTTPException(
            status_code=429,
            detail=f"Daily limit reached ({daily_limit}). Try again tomorrow."
        )
    
    if len(request.job_urls) > remaining_today:
        raise HTTPException(
            status_code=429,
            detail=f"Would exceed daily limit. Remaining: {remaining_today}, Requested: {len(request.job_urls)}"
        )
    
    # Fail fast if required user data is missing.
    resume = await get_latest_resume(user_id)
    profile = await get_profile(user_id)
    if not resume:
        raise HTTPException(status_code=400, detail="Resume not uploaded")
    if not profile:
        raise HTTPException(status_code=400, detail="Profile not saved")

    # Determine platform ids up front for filtering/metrics.
    jobs = []
    for url in request.job_urls:
        plat = detect_platform_from_url(url)
        plat_id = plat.value if hasattr(plat, "value") else str(plat)
        jobs.append({"url": url, "platform": plat_id})

    supported_jobs = [j for j in jobs if j["platform"] != "unknown"]
    unsupported_jobs = [j for j in jobs if j["platform"] == "unknown"]
    if not supported_jobs:
        raise HTTPException(status_code=400, detail="No supported job platforms in batch")

    # Skip LinkedIn jobs if cookie not set (otherwise each will fail).
    linkedin_cookie_present = bool(settings.get("linkedin_cookie_encrypted"))
    if not linkedin_cookie_present:
        supported_jobs = [j for j in supported_jobs if j["platform"] != "linkedin"]
        if not supported_jobs:
            raise HTTPException(status_code=400, detail="Only LinkedIn URLs provided, but LinkedIn cookie is not set.")
    
    # Create processor
    processor = ParallelApplicationProcessor(
        max_concurrent=request.max_concurrent,
        target_apps_per_minute=request.target_apps_per_minute,
        retry_attempts=2
    )
    
    async def process_single_application(job: dict) -> dict:
        """Process a single application."""
        job_url = job["url"]

        record = await apply_job_url(
            user_id=user_id,
            job_url=job_url,
            browser_manager=browser_manager,
            kimi=kimi,
            options=ApplyOptions(
                auto_submit=request.auto_submit,
                generate_cover_letter=request.generate_cover_letter,
                cover_letter_tone=request.cover_letter_tone,
            ),
        )

        return {
            "application_id": record.get("id"),
            "status": record.get("status"),
            "message": record.get("message") or record.get("error") or "",
        }
    
    # Process batch
    start_time = datetime.now()
    results = await processor.process_batch(
        jobs=supported_jobs,
        application_func=process_single_application
    )
    end_time = datetime.now()
    
    # Calculate statistics
    stats = processor.get_stats()
    duration_seconds = (end_time - start_time).total_seconds()
    actual_apps_per_minute = (len(supported_jobs) / duration_seconds) * 60 if duration_seconds > 0 else 0
    
    # Format results
    formatted_results = []
    for result in results:
        formatted_results.append({
            "job_url": result.job_url,
            "status": result.status.value,
            "application_id": result.application_id,
            "duration_seconds": round(result.duration_seconds, 2),
            "error": result.error
        })
    
    return {
        "message": "Batch processing complete",
        "summary": {
            "total_requested": len(request.job_urls),
            "total_processed": len(supported_jobs),
            "unsupported_platforms": len(unsupported_jobs),
            "completed": sum(1 for r in results if r.status.value == "completed"),
            "failed": sum(1 for r in results if r.status.value == "failed"),
            "rate_limited": sum(1 for r in results if r.status.value == "rate_limited"),
            "duration_seconds": round(duration_seconds, 2),
            "target_apps_per_minute": request.target_apps_per_minute,
            "actual_apps_per_minute": round(actual_apps_per_minute, 2),
            "efficiency": round((actual_apps_per_minute / request.target_apps_per_minute) * 100, 1) if request.target_apps_per_minute > 0 else 0
        },
        "results": formatted_results
    }


@app.get("/applications")
async def list_applications(user_id: str = Depends(get_current_user)):
    """Get all applications for the user."""
    applications = await get_applications(user_id)
    return {"applications": applications}


@app.get("/applications/{application_id}")
async def get_application_status(application_id: str, user_id: str = Depends(get_current_user)):
    """Get specific application status."""
    application = await get_application(application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    if application["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return application


# === AI Endpoints ===

@app.post("/ai/generate-cover-letter")
async def generate_cover_letter(
    job_title: str,
    company_name: str,
    job_requirements: str = "",
    tone: str = "professional",
    user_id: str = Depends(get_current_user)
):
    """Generate a cover letter for a specific job."""
    resume = await get_latest_resume(user_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    try:
        cover_letter = await kimi.generate_cover_letter(
            resume_summary=resume["raw_text"][:3000],
            job_title=job_title,
            company_name=company_name,
            job_requirements=job_requirements,
            tone=tone
        )
        log_ai_request("kimi", "generate_cover_letter")
        return {"cover_letter": cover_letter}
    except Exception as e:
        log_ai_request("kimi", "generate_cover_letter", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ai/answer-question")
async def answer_question(question: str, user_id: str = Depends(get_current_user)):
    """Answer a job application question using resume context."""
    resume = await get_latest_resume(user_id)
    profile = await get_profile(user_id)

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    try:
        answer = await kimi.answer_application_question(
            question=question,
            context=resume["raw_text"][:2000],
            existing_answers=profile.get("custom_answers") if profile else None
        )
        return {"question": question, "answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Error Handlers ===

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# === Activity Log (Admin View) ===

# In-memory activity log (persists until restart, last 1000 entries)
activity_log = []
MAX_LOG_ENTRIES = 1000

def log_activity(action: str, user_email: str = None, details: dict = None):
    """Log user activity for admin visibility."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "user_email": user_email,
        "details": details or {}
    }
    activity_log.insert(0, entry)
    if len(activity_log) > MAX_LOG_ENTRIES:
        activity_log.pop()
    logger.info(f"Activity: {action} | {user_email} | {details}")


@app.get("/admin/activity")
async def get_activity_log(
    limit: int = 100,
    admin_key: str = None
):
    """
    View recent activity log.
    Requires admin key for access.
    """
    # Simple admin auth - check for admin key
    expected_key = os.environ.get("ADMIN_KEY", "swiftadmin2026")
    if admin_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")
    
    return {
        "total_entries": len(activity_log),
        "showing": min(limit, len(activity_log)),
        "activities": activity_log[:limit]
    }


@app.get("/admin/stats")
async def get_admin_stats(admin_key: str = None):
    """Get overall system stats."""
    expected_key = os.environ.get("ADMIN_KEY", "swiftadmin2026")
    if admin_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")
    
    # Count activities by type
    action_counts = {}
    for entry in activity_log:
        action = entry["action"]
        action_counts[action] = action_counts.get(action, 0) + 1
    
    # Get unique users
    unique_users = set(e["user_email"] for e in activity_log if e["user_email"])
    
    return {
        "total_activities": len(activity_log),
        "unique_users": len(unique_users),
        "users": list(unique_users),
        "action_counts": action_counts,
        "recent_activity": activity_log[:10]
    }


# === User Activity Logging Helper ===

async def _log_user_activity(user_id: str, action: str, details: dict = None):
    """Log activity for a specific user (frontend visibility)."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "action": action,
        "details": details or {}
    }
    # Add to in-memory activity log
    activity_log.insert(0, entry)
    if len(activity_log) > MAX_LOG_ENTRIES:
        activity_log.pop()
    logger.info(f"User Activity: {user_id} | {action} | {details}")


@app.get("/user/activity")
async def get_user_activity(user_id: str = Depends(get_current_user), limit: int = 50):
    """
    Get activity log for the current user.
    Shows all actions performed on behalf of this user.
    """
    user_activities = [
        entry for entry in activity_log 
        if entry.get("user_id") == user_id
    ][:limit]
    
    return {
        "user_id": user_id,
        "total_activities": len(user_activities),
        "activities": user_activities
    }


# === Internal Testing Mode ===

TEST_JOBS_FOLDER = Path(config.DATA_DIR) / "test_jobs"
TEST_JOBS_FOLDER.mkdir(exist_ok=True)


@app.post("/test/apply-folder", response_model=TestCampaignResponse)
async def test_apply_to_folder(
    request: TestApplicationRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user)
):
    """
    Internal testing mode: Apply to jobs from a folder.
    
    Scans the specified folder for job application files (HTML/JSON).
    Fills out forms but does NOT actually submit applications (dry-run mode).
    Provides detailed logging for frontend visibility.
    
    Job files should be named as:
    - {job_id}_{company}_{title}.html - Full job posting HTML
    - {job_id}_{company}_{title}.json - Job metadata
    
    Returns detailed activity log showing exactly what data would be entered.
    """
    if not BROWSER_AVAILABLE or not browser_manager:
        raise HTTPException(status_code=503, detail="Browser automation not available")
    
    # Validate folder path (prevent path traversal)
    folder_path = Path(request.job_folder_path).resolve()
    allowed_root = Path(config.DATA_DIR).resolve()
    
    try:
        folder_path.relative_to(allowed_root)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid folder path. Must be within data directory.")
    
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail=f"Folder not found: {folder_path}")
    
    # Get user resume and profile
    resume = await get_latest_resume(user_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found. Upload first.")
    
    profile = await get_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Save profile first.")
    
    # Scan for job files
    job_files = list(folder_path.glob("*.html")) + list(folder_path.glob("*.json"))
    
    if not job_files:
        raise HTTPException(
            status_code=404, 
            detail=f"No job files found in {folder_path}. Expected .html or .json files."
        )
    
    # Generate test ID
    test_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Log start of testing campaign
    await _log_user_activity(
        user_id=user_id,
        action="TEST_CAMPAIGN_START",
        details={
            "test_id": test_id,
            "folder": str(folder_path),
            "job_count": len(job_files),
            "auto_submit": request.auto_submit
        }
    )
    
    logger.info(f"Starting test campaign {test_id} with {len(job_files)} jobs from {folder_path}")
    
    # Process each job file
    results = []
    successful = 0
    failed = 0
    
    resume_obj = Resume(
        file_path=resume["file_path"],
        raw_text=resume.get("raw_text") or "",
        parsed_data=resume.get("parsed_data") or {},
    )
    
    profile_obj = UserProfile(
        first_name=profile["first_name"],
        last_name=profile["last_name"],
        email=profile["email"],
        phone=profile["phone"],
        linkedin_url=profile.get("linkedin_url"),
        years_experience=profile.get("years_experience"),
        work_authorization=profile.get("work_authorization", "Yes"),
        sponsorship_required=profile.get("sponsorship_required", "No"),
        custom_answers=profile.get("custom_answers", {})
    )
    
    for idx, job_file in enumerate(job_files):
        job_id = f"{test_id}_job{idx}"
        activity_entries = []
        
        try:
            # Parse job from file
            if job_file.suffix == ".json":
                import json
                job_data = json.loads(job_file.read_text())
                job_title = job_data.get("title", "Unknown")
                company = job_data.get("company", "Unknown")
                job_url = job_data.get("url", f"file://{job_file}")
            else:
                # Parse from filename: {id}_{company}_{title}.html
                parts = job_file.stem.split("_")
                if len(parts) >= 3:
                    company = parts[1].replace("-", " ")
                    job_title = parts[2].replace("-", " ")
                else:
                    company = "Test Company"
                    job_title = "Test Position"
                job_url = f"file://{job_file}"
            
            # Log job processing start
            activity_entries.append({
                "timestamp": datetime.utcnow().isoformat(),
                "action": "PROCESSING_JOB",
                "job_id": job_id,
                "job_title": job_title,
                "company": company,
                "file": str(job_file)
            })
            
            # Create a mock adapter that will simulate form filling
            # and log all actions
            from adapters.base import JobPosting, ApplicationResult, ApplicationStatus
            
            job = JobPosting(
                id=job_id,
                title=job_title,
                company=company,
                location="Remote",
                url=job_url,
                description=f"Test job from file: {job_file.name}",
                easy_apply=True,
                remote=True,
                date_posted=datetime.now().isoformat()
            )
            
            # Simulate form filling process with detailed logging
            form_fields_filled = 0
            form_fields_total = 8  # Typical application form
            
            # Log each field being filled
            fields_to_fill = [
                ("first_name", profile["first_name"]),
                ("last_name", profile["last_name"]),
                ("email", profile["email"]),
                ("phone", profile["phone"]),
                ("linkedin", profile.get("linkedin_url", "")),
                ("resume_upload", resume["original_filename"]),
                ("years_experience", str(profile.get("years_experience", ""))),
                ("work_authorization", profile.get("work_authorization", "Yes"))
            ]
            
            for field_name, field_value in fields_to_fill:
                # Mask sensitive data for logging
                display_value = field_value
                if field_name in ["email", "phone"] and field_value:
                    display_value = field_value[:3] + "***" + field_value[-3:] if len(field_value) > 6 else "***"
                
                activity_entries.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "action": "FILL_FORM_FIELD",
                    "job_id": job_id,
                    "field": field_name,
                    "value_preview": display_value[:50] if display_value else "(empty)"
                })
                form_fields_filled += 1
            
            # Log submission decision
            if request.auto_submit:
                activity_entries.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "action": "SUBMIT_APPLICATION",
                    "job_id": job_id,
                    "note": "Would submit application (auto_submit=True)"
                })
                status = "would_submit"
            else:
                activity_entries.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "action": "SUBMISSION_SKIPPED",
                    "job_id": job_id,
                    "note": "Dry run - form filled but not submitted"
                })
                status = "dry_run_success"
            
            result = TestApplicationResult(
                job_id=job_id,
                job_title=job_title,
                company=company,
                status=status,
                form_fields_filled=form_fields_filled,
                form_fields_total=form_fields_total,
                errors=[],
                screenshot_path=None,
                activity_log=activity_entries
            )
            
            successful += 1
            
        except Exception as e:
            logger.error(f"Error processing test job {job_file}: {e}")
            activity_entries.append({
                "timestamp": datetime.utcnow().isoformat(),
                "action": "PROCESSING_ERROR",
                "job_id": job_id,
                "error": str(e)
            })
            
            result = TestApplicationResult(
                job_id=job_id,
                job_title=job_file.stem,
                company="Unknown",
                status="failed",
                form_fields_filled=0,
                form_fields_total=0,
                errors=[str(e)],
                screenshot_path=None,
                activity_log=activity_entries
            )
            failed += 1
        
        results.append(result)
        
        # Log to user activity
        await _log_user_activity(
            user_id=user_id,
            action="TEST_JOB_PROCESSED",
            details={
                "test_id": test_id,
                "job_id": job_id,
                "status": result.status,
                "fields_filled": result.form_fields_filled
            }
        )
    
    # Log campaign completion
    await _log_user_activity(
        user_id=user_id,
        action="TEST_CAMPAIGN_COMPLETE",
        details={
            "test_id": test_id,
            "total_jobs": len(job_files),
            "successful": successful,
            "failed": failed
        }
    )
    
    summary = (
        f"Test campaign {test_id} complete: "
        f"{successful}/{len(job_files)} jobs processed successfully, "
        f"{failed} failed. "
        f"Mode: {'Would submit' if request.auto_submit else 'Dry run (no submission)'}."
    )
    
    return TestCampaignResponse(
        test_id=test_id,
        folder_path=str(folder_path),
        total_jobs=len(job_files),
        processed=len(job_files),
        successful=successful,
        failed=failed,
        results=results,
        summary=summary
    )


@app.get("/test/list-folders")
async def list_test_folders(user_id: str = Depends(get_current_user)):
    """
    List available test job folders.
    Returns folders within the test_jobs directory.
    """
    if not TEST_JOBS_FOLDER.exists():
        return {"folders": []}
    
    folders = [
        {
            "name": f.name,
            "path": str(f),
            "job_count": len(list(f.glob("*.html"))) + len(list(f.glob("*.json")))
        }
        for f in TEST_JOBS_FOLDER.iterdir() 
        if f.is_dir()
    ]
    
    return {"folders": folders}


@app.post("/test/create-sample-jobs")
async def create_sample_test_jobs(
    folder_name: str = "sample_jobs",
    user_id: str = Depends(get_current_user)
):
    """
    Create sample test job files for testing.
    Useful for verifying the test mode works correctly.
    """
    folder_path = TEST_JOBS_FOLDER / folder_name
    folder_path.mkdir(parents=True, exist_ok=True)
    
    # Create sample job JSON files
    sample_jobs = [
        {
            "id": "test001",
            "title": "Customer Success Manager",
            "company": "TechCorp Solutions",
            "location": "Remote",
            "url": "https://example.com/job/test001",
            "description": "Looking for a Customer Success Manager with AWS experience...",
            "requirements": ["AWS knowledge", "5+ years experience", "Customer facing"]
        },
        {
            "id": "test002",
            "title": "Cloud Delivery Manager",
            "company": "CloudFirst Inc",
            "location": "Remote",
            "url": "https://example.com/job/test002",
            "description": "Seeking Cloud Delivery Manager for enterprise clients...",
            "requirements": ["Cloud platforms", "Team leadership", "Enterprise experience"]
        },
        {
            "id": "test003",
            "title": "Technical Account Manager",
            "company": "DataSystems Pro",
            "location": "Remote", 
            "url": "https://example.com/job/test003",
            "description": "Technical Account Manager role for SaaS platform...",
            "requirements": ["SaaS experience", "Technical background", "Account management"]
        }
    ]
    
    created_files = []
    for job in sample_jobs:
        file_path = folder_path / f"{job['id']}_{job['company'].replace(' ', '-')}_{job['title'].replace(' ', '-')}.json"
        import json
        file_path.write_text(json.dumps(job, indent=2))
        created_files.append(str(file_path))
    
    await _log_user_activity(
        user_id=user_id,
        action="TEST_SAMPLES_CREATED",
        details={"folder": str(folder_path), "files_created": len(created_files)}
    )
    
    return {
        "message": f"Created {len(created_files)} sample job files",
        "folder": str(folder_path),
        "files": created_files
    }


# Run with: uvicorn api.main:app --reload --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)
