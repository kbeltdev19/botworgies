"""
Job Applier API - FastAPI Backend
Handles resume upload, job search, and application orchestration.
With authentication, database persistence, and proper security.
"""

import os
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
    save_application, get_applications, get_application, count_applications_since,
    save_settings, get_settings
)
from api.logging_config import logger, log_application, log_ai_request

from ai.kimi_service import KimiResumeOptimizer

# Browser manager is optional - may not be available on serverless
try:
    from browser.stealth_manager import StealthBrowserManager
    BROWSER_AVAILABLE = True
except ImportError:
    StealthBrowserManager = None
    BROWSER_AVAILABLE = False

from adapters import (
    get_adapter, detect_platform_from_url,
    SearchConfig, UserProfile, Resume, ApplicationStatus
)

# Parallel processing for batch applications
from api.parallel_processor import (
    ParallelApplicationProcessor,
    process_applications_parallel,
    BatchApplicationStats
)


# === Lifespan Management ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    logger.info("Starting Job Applier API...")
    await init_database()
    logger.info("Database initialized")
    yield
    # Shutdown
    logger.info("Shutting down Job Applier API...")
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


# Initialize services
kimi = KimiResumeOptimizer()
browser_manager = StealthBrowserManager() if BROWSER_AVAILABLE else None


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
        "linkedin_cookie_set": bool(settings.get("linkedin_cookie_encrypted"))
    }


@app.post("/settings")
async def update_user_settings(request: UserSettingsRequest, user_id: str = Depends(get_current_user)):
    """Update user settings."""
    settings_data = {"daily_limit": request.daily_limit}

    # Encrypt LinkedIn cookie if provided
    if request.linkedin_cookie:
        settings_data["linkedin_cookie_encrypted"] = encrypt_sensitive_data(request.linkedin_cookie)
        logger.info(f"LinkedIn cookie updated for user {user_id}")

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
            {"id": "greenhouse", "name": "Greenhouse", "search_supported": False, "easy_apply": True},
            {"id": "workday", "name": "Workday", "search_supported": False, "easy_apply": False},
            {"id": "lever", "name": "Lever", "search_supported": False, "easy_apply": True}
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

    # Extract text
    if file.filename.endswith(".txt"):
        raw_text = content.decode("utf-8")
    else:
        raw_text = content.decode("utf-8", errors="ignore")

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
        "parsed_data": parsed_data,
        "suggested_titles": suggested_titles
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


# === Job Search Endpoints ===

@app.post("/jobs/search")
async def search_jobs(request: SearchRequest, platform: str = "linkedin", user_id: str = Depends(get_current_user)):
    """Search for jobs across platforms."""
    if not BROWSER_AVAILABLE or not browser_manager:
        raise HTTPException(status_code=503, detail="Browser automation not available")

    if platform not in ["linkedin", "indeed", "company"]:
        raise HTTPException(status_code=400, detail="Search only supported for: linkedin, indeed, company")

    if platform == "company" and not request.careers_url:
        raise HTTPException(status_code=400, detail="Company platform requires careers_url")

    search_config = SearchConfig(
        roles=request.roles,
        locations=request.locations,
        easy_apply_only=request.easy_apply_only,
        posted_within_days=request.posted_within_days,
        required_keywords=request.required_keywords,
        exclude_keywords=request.exclude_keywords,
        country=request.country,
        careers_url=request.careers_url
    )

    try:
        # Get LinkedIn cookie if available
        settings = await get_settings(user_id)
        linkedin_cookie = None
        if settings and settings.get("linkedin_cookie_encrypted"):
            linkedin_cookie = decrypt_sensitive_data(settings["linkedin_cookie_encrypted"])

        adapter = get_adapter(platform, browser_manager, session_cookie=linkedin_cookie)
        jobs = await adapter.search_jobs(search_config)

        logger.info(f"Search completed for user {user_id}: {len(jobs)} jobs found on {platform}")

        return {
            "platform": platform,
            "count": len(jobs),
            "jobs": [
                {
                    "id": j.id,
                    "title": j.title,
                    "company": j.company,
                    "location": j.location,
                    "url": j.url,
                    "easy_apply": j.easy_apply,
                    "remote": j.remote
                }
                for j in jobs
            ]
        }
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'adapter' in locals():
            await adapter.close()


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

    # Check rate limit
    settings = await get_settings(user_id) or {}
    daily_limit = settings.get("daily_limit", config.DEFAULT_DAILY_LIMIT)
    cutoff = datetime.now() - timedelta(hours=24)
    sent_24h = await count_applications_since(user_id, cutoff)

    if sent_24h >= daily_limit:
        raise HTTPException(
            status_code=429,
            detail=f"Daily limit reached ({daily_limit}). Sent: {sent_24h}. Try again later."
        )

    resume = await get_latest_resume(user_id)
    profile = await get_profile(user_id)

    if not resume:
        raise HTTPException(status_code=400, detail="Resume not uploaded")
    if not profile:
        raise HTTPException(status_code=400, detail="Profile not saved")

    # Detect platform
    platform = detect_platform_from_url(request.job_url)
    if platform == "unknown":
        raise HTTPException(status_code=400, detail="Unsupported job platform")

    # Check LinkedIn auth requirement
    linkedin_cookie = None
    if platform == "linkedin":
        if settings.get("linkedin_cookie_encrypted"):
            linkedin_cookie = decrypt_sensitive_data(settings["linkedin_cookie_encrypted"])
        else:
            raise HTTPException(status_code=400, detail="LinkedIn requires authentication. Add li_at cookie in settings.")

    # Generate cover letter if requested
    cover_letter = None
    if request.generate_cover_letter:
        try:
            cover_letter = await kimi.generate_cover_letter(
                resume_summary=resume["raw_text"][:2000],
                job_title="Position",
                company_name="Company",
                job_requirements="",
                tone=request.cover_letter_tone
            )
        except Exception as e:
            logger.warning(f"Cover letter generation failed: {e}")

    # Create application record
    application_id = f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    async def do_apply():
        logger.info(f"Starting application {application_id} for {request.job_url}")
        adapter = None
        try:
            adapter = get_adapter(platform, browser_manager, session_cookie=linkedin_cookie)
            job = await adapter.get_job_details(request.job_url)
            logger.info(f"Got job details: {job.title} at {job.company}")

            # Build Resume and UserProfile objects
            resume_obj = Resume(
                file_path=resume["file_path"],
                raw_text=resume["raw_text"],
                parsed_data=resume["parsed_data"]
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

            result = await adapter.apply_to_job(
                job=job,
                resume=resume_obj,
                profile=profile_obj,
                cover_letter=cover_letter,
                auto_submit=request.auto_submit
            )

            await save_application({
                "id": application_id,
                "user_id": user_id,
                "job_url": request.job_url,
                "job_title": job.title,
                "company": job.company,
                "platform": platform,
                "status": result.status.value,
                "message": result.message,
                "screenshot_path": result.screenshot_path,
                "timestamp": datetime.now().isoformat()
            })

            log_application(application_id, user_id, request.job_url, result.status.value)
            user = await get_user_by_id(user_id)
            log_activity("APPLY", user.get("email") if user else user_id, {
                "job": job.title,
                "company": job.company,
                "platform": platform,
                "status": result.status.value
            })

        except Exception as e:
            logger.error(f"Application {application_id} failed: {e}")
            await save_application({
                "id": application_id,
                "user_id": user_id,
                "job_url": request.job_url,
                "platform": platform,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            log_application(application_id, user_id, request.job_url, "error", str(e))
        finally:
            if adapter:
                await adapter.close()

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
    max_concurrent: int = Field(default=3, ge=1, le=5)
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
    
    # Get user data
    resume = await get_latest_resume(user_id)
    profile = await get_profile(user_id)
    
    if not resume:
        raise HTTPException(status_code=400, detail="Resume not uploaded")
    if not profile:
        raise HTTPException(status_code=400, detail="Profile not saved")
    
    # Get LinkedIn cookie if available
    linkedin_cookie = None
    if settings.get("linkedin_cookie_encrypted"):
        linkedin_cookie = decrypt_sensitive_data(settings["linkedin_cookie_encrypted"])
    
    # Prepare jobs list
    jobs = [{"url": url, "platform": detect_platform_from_url(url)} for url in request.job_urls]
    
    # Filter out unsupported platforms
    supported_jobs = [j for j in jobs if j["platform"] != "unknown"]
    unsupported_jobs = [j for j in jobs if j["platform"] == "unknown"]
    
    if not supported_jobs:
        raise HTTPException(status_code=400, detail="No supported job platforms in batch")
    
    # Create processor
    processor = ParallelApplicationProcessor(
        max_concurrent=request.max_concurrent,
        target_apps_per_minute=request.target_apps_per_minute,
        retry_attempts=2
    )
    
    async def process_single_application(job: dict) -> dict:
        """Process a single application."""
        platform = job["platform"]
        job_url = job["url"]
        
        # Check LinkedIn auth
        if platform == "linkedin" and not linkedin_cookie:
            raise Exception("LinkedIn requires authentication. Add li_at cookie in settings.")
        
        # Generate cover letter if requested
        cover_letter = None
        if request.generate_cover_letter:
            try:
                cover_letter = await kimi.generate_cover_letter(
                    resume_summary=resume["raw_text"][:2000],
                    job_title="Position",
                    company_name="Company",
                    job_requirements="",
                    tone=request.cover_letter_tone
                )
            except Exception as e:
                logger.warning(f"Cover letter generation failed for {job_url}: {e}")
        
        # Build objects
        resume_obj = Resume(
            file_path=resume["file_path"],
            raw_text=resume["raw_text"],
            parsed_data=resume["parsed_data"]
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
        
        # Apply
        adapter = get_adapter(platform, browser_manager, session_cookie=linkedin_cookie)
        try:
            job_details = await adapter.get_job_details(job_url)
            result = await adapter.apply_to_job(
                job=job_details,
                resume=resume_obj,
                profile=profile_obj,
                cover_letter=cover_letter,
                auto_submit=request.auto_submit
            )
            
            # Save application
            app_id = f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            await save_application({
                "id": app_id,
                "user_id": user_id,
                "job_url": job_url,
                "job_title": job_details.title,
                "company": job_details.company,
                "platform": platform,
                "status": result.status.value,
                "message": result.message,
                "screenshot_path": result.screenshot_path,
                "timestamp": datetime.now().isoformat()
            })
            
            return {
                "application_id": app_id,
                "status": result.status.value,
                "message": result.message
            }
        finally:
            await adapter.close()
    
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
            resume_context=resume["raw_text"][:2000],
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


# Run with: uvicorn api.main:app --reload --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)
