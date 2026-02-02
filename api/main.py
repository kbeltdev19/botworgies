"""
Job Applier API - FastAPI Backend
Handles resume upload, job search, and application orchestration.
"""

import os
import json
import asyncio
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Import our services
import sys
sys.path.append(str(Path(__file__).parent.parent))

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

# Initialize FastAPI app
app = FastAPI(
    title="Job Applier API",
    description="Automated job application service with AI resume optimization",
    version="1.0.0"
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data directory
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


# === Pydantic Models ===

class SearchRequest(BaseModel):
    roles: List[str] = Field(..., example=["Software Engineer", "Backend Developer"])
    locations: List[str] = Field(..., example=["San Francisco", "Remote"])
    easy_apply_only: bool = False
    posted_within_days: int = 7
    required_keywords: List[str] = Field(default_factory=list)
    exclude_keywords: List[str] = Field(default_factory=list)
    country: str = Field(default="US", description="Country filter: US, CA, GB, DE, ALL")


class UserProfileRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str
    linkedin_url: Optional[str] = None
    years_experience: Optional[int] = None
    work_authorization: str = "Yes"
    sponsorship_required: str = "No"
    custom_answers: dict = Field(default_factory=dict)


class ApplicationRequest(BaseModel):
    job_url: str
    auto_submit: bool = False
    generate_cover_letter: bool = True
    cover_letter_tone: str = "professional"


class TailorResumeRequest(BaseModel):
    job_description: str
    optimization_type: str = "balanced"


class UserSettingsRequest(BaseModel):
    daily_limit: int = Field(default=10, ge=1, le=100, description="Max applications per 24 hours")


# === In-Memory State (use Redis in production) ===
state = {
    "resumes": {},  # user_id -> Resume
    "profiles": {},  # user_id -> UserProfile
    "applications": [],  # List of applications
    "jobs_cache": {},  # Search results cache
    "user_settings": {},  # user_id -> {daily_limit: int, ...}
}

# Default settings
DEFAULT_DAILY_LIMIT = 10

# Initialize services
kimi = KimiResumeOptimizer()
browser_manager = StealthBrowserManager() if BROWSER_AVAILABLE else None


# === API Endpoints ===

@app.get("/")
async def root():
    return {"status": "ok", "message": "Job Applier API v1.0"}


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# === User Settings & Rate Limits ===

def get_user_settings(user_id: str) -> dict:
    """Get user settings with defaults."""
    return state["user_settings"].get(user_id, {"daily_limit": DEFAULT_DAILY_LIMIT})


def count_applications_last_24h(user_id: str) -> int:
    """Count applications submitted in last 24 hours for a user."""
    from datetime import timedelta
    cutoff = datetime.now() - timedelta(hours=24)
    count = 0
    for app in state["applications"]:
        if app.get("user_id", "default") == user_id:
            try:
                app_time = datetime.fromisoformat(app["timestamp"])
                if app_time > cutoff and app.get("status") not in ["error", "cancelled"]:
                    count += 1
            except (KeyError, ValueError):
                pass
    return count


@app.get("/settings")
async def get_settings(user_id: str = "default"):
    """Get user settings including rate limit status."""
    settings = get_user_settings(user_id)
    sent_24h = count_applications_last_24h(user_id)
    daily_limit = settings.get("daily_limit", DEFAULT_DAILY_LIMIT)
    
    return {
        "daily_limit": daily_limit,
        "sent_last_24h": sent_24h,
        "remaining": max(0, daily_limit - sent_24h),
        "can_apply": sent_24h < daily_limit,
        "reset_info": "Rolling 24-hour window"
    }


@app.post("/settings")
async def update_settings(request: UserSettingsRequest, user_id: str = "default"):
    """Update user settings."""
    if user_id not in state["user_settings"]:
        state["user_settings"][user_id] = {}
    
    state["user_settings"][user_id]["daily_limit"] = request.daily_limit
    
    sent_24h = count_applications_last_24h(user_id)
    
    return {
        "message": "Settings updated",
        "daily_limit": request.daily_limit,
        "sent_last_24h": sent_24h,
        "remaining": max(0, request.daily_limit - sent_24h)
    }


@app.get("/platforms")
async def get_platforms():
    """Get list of supported job platforms."""
    return {
        "platforms": [
            {
                "id": "linkedin",
                "name": "LinkedIn",
                "search_supported": True,
                "easy_apply": True,
                "url_pattern": "linkedin.com/jobs"
            },
            {
                "id": "indeed",
                "name": "Indeed",
                "search_supported": True,
                "easy_apply": True,
                "url_pattern": "indeed.com/viewjob"
            },
            {
                "id": "greenhouse",
                "name": "Greenhouse",
                "search_supported": False,
                "easy_apply": True,
                "url_pattern": "boards.greenhouse.io/*/jobs/*"
            },
            {
                "id": "workday",
                "name": "Workday",
                "search_supported": False,
                "easy_apply": False,
                "note": "Often requires account creation",
                "url_pattern": "*.myworkdayjobs.com"
            },
            {
                "id": "lever",
                "name": "Lever",
                "search_supported": False,
                "easy_apply": True,
                "url_pattern": "jobs.lever.co/*/*"
            }
        ]
    }


# --- Resume Endpoints ---

@app.post("/resume/upload")
async def upload_resume(
    file: UploadFile = File(...),
    user_id: str = "default"
):
    """Upload and parse a resume file."""
    # Save file
    file_path = DATA_DIR / f"resume_{user_id}_{file.filename}"
    content = await file.read()
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Extract text (simple for now - could use PDF parser)
    if file.filename.endswith(".txt"):
        raw_text = content.decode("utf-8")
    else:
        # For PDF/DOCX, would use proper parsers
        raw_text = content.decode("utf-8", errors="ignore")
    
    # Parse with Kimi
    parsed_data = await kimi.parse_resume(raw_text)
    
    # Store resume
    resume = Resume(
        file_path=str(file_path),
        raw_text=raw_text,
        parsed_data=parsed_data
    )
    state["resumes"][user_id] = resume
    
    return {
        "message": "Resume uploaded and parsed",
        "file_path": str(file_path),
        "parsed_data": parsed_data
    }


@app.post("/resume/tailor")
async def tailor_resume(
    request: TailorResumeRequest,
    user_id: str = "default"
):
    """Tailor resume to a specific job description."""
    resume = state["resumes"].get(user_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found. Upload first.")
    
    result = await kimi.tailor_resume(
        resume.raw_text,
        request.job_description,
        request.optimization_type
    )
    
    # Store tailored version
    resume.tailored_version = result
    
    return result


# --- Profile Endpoints ---

@app.post("/profile")
async def save_profile(profile: UserProfileRequest, user_id: str = "default"):
    """Save user profile for applications."""
    user_profile = UserProfile(
        first_name=profile.first_name,
        last_name=profile.last_name,
        email=profile.email,
        phone=profile.phone,
        linkedin_url=profile.linkedin_url,
        years_experience=profile.years_experience,
        work_authorization=profile.work_authorization,
        sponsorship_required=profile.sponsorship_required,
        custom_answers=profile.custom_answers
    )
    state["profiles"][user_id] = user_profile
    
    return {"message": "Profile saved", "profile": profile.dict()}


@app.get("/profile/{user_id}")
async def get_profile(user_id: str):
    """Get user profile."""
    profile = state["profiles"].get(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return {
        "first_name": profile.first_name,
        "last_name": profile.last_name,
        "email": profile.email,
        "phone": profile.phone,
        "linkedin_url": profile.linkedin_url,
        "years_experience": profile.years_experience
    }


# --- Job Search Endpoints ---

@app.post("/jobs/search")
async def search_jobs(request: SearchRequest, platform: str = "linkedin"):
    """Search for jobs across platforms."""
    # Browser required for search
    if not BROWSER_AVAILABLE or not browser_manager:
        raise HTTPException(
            status_code=503,
            detail="Browser automation not available on this deployment. Use local API for search."
        )
    
    search_config = SearchConfig(
        roles=request.roles,
        locations=request.locations,
        easy_apply_only=request.easy_apply_only,
        posted_within_days=request.posted_within_days,
        required_keywords=request.required_keywords,
        exclude_keywords=request.exclude_keywords,
        country=request.country
    )
    
    # Support linkedin and indeed for search
    if platform not in ["linkedin", "indeed"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Search only supported for: linkedin, indeed. Use job URL for greenhouse/workday/lever."
        )
    
    try:
        adapter = get_adapter(platform, browser_manager)
        jobs = await adapter.search_jobs(search_config)
        
        # Cache results
        cache_key = f"{platform}_{hash(str(request.dict()))}"
        state["jobs_cache"][cache_key] = jobs
        
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
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'adapter' in locals():
            await adapter.close()


# --- Application Endpoints ---

@app.post("/apply")
async def apply_to_job(
    request: ApplicationRequest,
    background_tasks: BackgroundTasks,
    user_id: str = "default"
):
    """Apply to a specific job."""
    # Browser required for applications
    if not BROWSER_AVAILABLE or not browser_manager:
        raise HTTPException(
            status_code=503,
            detail="Browser automation not available on this deployment. Use local API for applications."
        )
    
    # Check rate limit
    settings = get_user_settings(user_id)
    sent_24h = count_applications_last_24h(user_id)
    daily_limit = settings.get("daily_limit", DEFAULT_DAILY_LIMIT)
    
    if sent_24h >= daily_limit:
        raise HTTPException(
            status_code=429,
            detail=f"Daily limit reached ({daily_limit} applications per 24 hours). "
                   f"You've sent {sent_24h} applications. Try again later or increase your limit in settings."
        )
    
    resume = state["resumes"].get(user_id)
    profile = state["profiles"].get(user_id)
    
    if not resume:
        raise HTTPException(status_code=400, detail="Resume not uploaded")
    if not profile:
        raise HTTPException(status_code=400, detail="Profile not saved")
    
    # Generate cover letter if requested
    cover_letter = None
    if request.generate_cover_letter:
        # Would need job details - for now, use generic
        cover_letter = await kimi.generate_cover_letter(
            resume_summary=resume.raw_text[:2000],
            job_title="Position",
            company_name="Company",
            job_requirements="",
            tone=request.cover_letter_tone
        )
    
    # Auto-detect platform from URL
    platform = detect_platform_from_url(request.job_url)
    if platform == "unknown":
        raise HTTPException(
            status_code=400, 
            detail="Could not detect platform from URL. Supported: LinkedIn, Indeed, Greenhouse, Workday, Lever"
        )
    
    # Apply in background
    application_id = f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    async def do_apply():
        print(f"🔧 Starting application {application_id} for {request.job_url}")
        adapter = None
        try:
            adapter = get_adapter(platform, browser_manager)
            print(f"📄 Getting job details from {platform}...")
            
            # Get job details
            job = await adapter.get_job_details(request.job_url)
            print(f"✅ Got job: {job.title} at {job.company}")
            
            # Apply
            print(f"📝 Applying to job...")
            result = await adapter.apply_to_job(
                job=job,
                resume=resume,
                profile=profile,
                cover_letter=cover_letter,
                auto_submit=request.auto_submit
            )
            print(f"✅ Application result: {result.status.value} - {result.message}")
            
            # Store result
            state["applications"].append({
                "id": application_id,
                "user_id": user_id,
                "job_url": request.job_url,
                "job_title": job.title,
                "company": job.company,
                "platform": platform,
                "status": result.status.value,
                "message": result.message,
                "screenshot": result.screenshot_path,
                "timestamp": datetime.now().isoformat()
            })
            print(f"💾 Stored application result")
            
        except Exception as e:
            import traceback
            error_msg = str(e)
            print(f"❌ Application error: {error_msg}")
            print(traceback.format_exc())
            
            state["applications"].append({
                "id": application_id,
                "user_id": user_id,
                "job_url": request.job_url,
                "platform": platform,
                "status": "error",
                "error": error_msg,
                "timestamp": datetime.now().isoformat()
            })
        finally:
            if adapter:
                await adapter.close()
                print(f"🔒 Closed adapter")
    
    background_tasks.add_task(do_apply)
    
    return {
        "message": "Application started",
        "application_id": application_id,
        "status": "processing"
    }


@app.get("/applications")
async def get_applications(user_id: str = "default"):
    """Get all applications."""
    return {"applications": state["applications"]}


@app.get("/applications/{application_id}")
async def get_application(application_id: str):
    """Get specific application status."""
    for app in state["applications"]:
        if app["id"] == application_id:
            return app
    raise HTTPException(status_code=404, detail="Application not found")


# --- AI Endpoints ---

@app.post("/ai/generate-cover-letter")
async def generate_cover_letter(
    job_title: str,
    company_name: str,
    job_requirements: str = "",
    company_research: str = "",
    tone: str = "professional",
    user_id: str = "default"
):
    """Generate a cover letter for a specific job."""
    resume = state["resumes"].get(user_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    cover_letter = await kimi.generate_cover_letter(
        resume_summary=resume.raw_text[:3000],
        job_title=job_title,
        company_name=company_name,
        job_requirements=job_requirements,
        company_research=company_research,
        tone=tone
    )
    
    return {"cover_letter": cover_letter}


@app.post("/ai/answer-question")
async def answer_question(
    question: str,
    user_id: str = "default"
):
    """Answer a job application question using resume context."""
    resume = state["resumes"].get(user_id)
    profile = state["profiles"].get(user_id)
    
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    answer = await kimi.answer_application_question(
        question=question,
        resume_context=resume.raw_text[:2000],
        existing_answers=profile.custom_answers if profile else None
    )
    
    return {"question": question, "answer": answer}


# --- Startup/Shutdown ---

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    await browser_manager.close_all()


# Run with: uvicorn api.main:app --reload --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
