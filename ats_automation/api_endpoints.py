"""
FastAPI endpoints for ATS automation
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncio

from .models import UserProfile, ApplicationResult, ATSPlatform, DiceJob
from .ats_router import ATSRouter


# Pydantic models for API requests/responses
class ProfileRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str
    resume_path: str
    resume_text: str = ""
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    github_url: Optional[str] = None
    salary_expectation: Optional[str] = None
    years_experience: Optional[int] = None
    skills: List[str] = []
    work_history: List[Dict] = []
    education: List[Dict] = []
    custom_answers: Dict[str, str] = {}


class ApplyRequest(BaseModel):
    job_url: str
    profile: ProfileRequest
    ai_api_key: Optional[str] = None


class BatchApplyRequest(BaseModel):
    job_urls: List[str]
    profile: ProfileRequest
    concurrent: int = 3
    ai_api_key: Optional[str] = None


class DiceSearchRequest(BaseModel):
    query: str
    location: str = ""
    remote: bool = False
    job_type: str = ""  # contract, fulltime
    max_jobs: int = 10
    profile: ProfileRequest


class ApplyResponse(BaseModel):
    success: bool
    platform: str
    job_id: str
    status: str
    confirmation_number: Optional[str] = None
    error_message: Optional[str] = None
    fields_filled: int = 0
    total_fields: int = 0
    session_id: Optional[str] = None


class PlatformDetectResponse(BaseModel):
    url: str
    platform: str
    confidence: str


# Create FastAPI router (not app - this is meant to be included in main app)
from fastapi import APIRouter
router = APIRouter(prefix="/ats", tags=["ATS Automation"])


@router.post("/detect", response_model=PlatformDetectResponse)
async def detect_platform(url: str):
    """
    Detect which ATS platform a job URL uses
    """
    try:
        # Create dummy profile for router
        dummy_profile = UserProfile(
            first_name="Test",
            last_name="User",
            email="test@example.com",
            phone="555-555-5555",
            resume_path="/tmp/test.pdf"
        )
        
        ats_router = ATSRouter(dummy_profile)
        platform = await ats_router.detect_platform(url)
        
        confidence = "high" if platform != ATSPlatform.UNKNOWN else "low"
        
        return PlatformDetectResponse(
            url=url,
            platform=platform.value,
            confidence=confidence
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apply", response_model=ApplyResponse)
async def apply_to_job(request: ApplyRequest, background_tasks: BackgroundTasks):
    """
    Apply to a single job
    
    Auto-detects ATS platform and routes to appropriate handler
    """
    try:
        profile = UserProfile(
            first_name=request.profile.first_name,
            last_name=request.profile.last_name,
            email=request.profile.email,
            phone=request.profile.phone,
            resume_path=request.profile.resume_path,
            resume_text=request.profile.resume_text,
            linkedin_url=request.profile.linkedin_url,
            portfolio_url=request.profile.portfolio_url,
            github_url=request.profile.github_url,
            salary_expectation=request.profile.salary_expectation,
            years_experience=request.profile.years_experience,
            skills=request.profile.skills,
            work_history=request.profile.work_history,
            education=request.profile.education,
            custom_answers=request.profile.custom_answers
        )
        
        ats_router = ATSRouter(profile, request.ai_api_key)
        result = await ats_router.apply(request.job_url)
        
        # Cleanup in background
        background_tasks.add_task(ats_router.cleanup)
        
        return ApplyResponse(
            success=result.success,
            platform=result.platform.value,
            job_id=result.job_id,
            status=result.status,
            confirmation_number=result.confirmation_number,
            error_message=result.error_message,
            fields_filled=result.fields_filled,
            total_fields=result.total_fields,
            session_id=result.session_id
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apply/batch")
async def apply_to_jobs_batch(request: BatchApplyRequest):
    """
    Apply to multiple jobs concurrently
    
    - max 10 concurrent applications recommended
    - Respects rate limits automatically
    """
    try:
        profile = UserProfile(
            first_name=request.profile.first_name,
            last_name=request.profile.last_name,
            email=request.profile.email,
            phone=request.profile.phone,
            resume_path=request.profile.resume_path,
            resume_text=request.profile.resume_text,
            linkedin_url=request.profile.linkedin_url,
            portfolio_url=request.profile.portfolio_url,
            github_url=request.profile.github_url,
            salary_expectation=request.profile.salary_expectation,
            years_experience=request.profile.years_experience,
            skills=request.profile.skills,
            work_history=request.profile.work_history,
            education=request.profile.education,
            custom_answers=request.profile.custom_answers
        )
        
        ats_router = ATSRouter(profile, request.ai_api_key)
        
        results = await ats_router.apply_batch(
            request.job_urls,
            concurrent=request.concurrent
        )
        
        # Cleanup
        await ats_router.cleanup()
        
        # Format results
        return {
            "total": len(results),
            "successful": sum(1 for r in results if isinstance(r, ApplicationResult) and r.success),
            "failed": sum(1 for r in results if isinstance(r, ApplicationResult) and not r.success),
            "results": [
                {
                    "success": r.success if isinstance(r, ApplicationResult) else False,
                    "platform": r.platform.value if isinstance(r, ApplicationResult) else "unknown",
                    "job_url": r.job_url if isinstance(r, ApplicationResult) else "",
                    "status": r.status if isinstance(r, ApplicationResult) else "error",
                    "error": r.error_message if isinstance(r, ApplicationResult) else str(r)
                }
                for r in results
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dice/search")
async def search_dice_jobs(request: DiceSearchRequest):
    """
    Search for jobs on Dice.com
    
    Returns jobs with Easy Apply flag
    """
    try:
        profile = UserProfile(
            first_name=request.profile.first_name,
            last_name=request.profile.last_name,
            email=request.profile.email,
            phone=request.profile.phone,
            resume_path=request.profile.resume_path
        )
        
        from .handlers.dice import DiceHandler
        from .browserbase_manager import BrowserBaseManager
        
        browser = BrowserBaseManager()
        dice = DiceHandler(browser, profile)
        
        jobs = await dice.search_jobs(
            query=request.query,
            location=request.location,
            remote=request.remote,
            job_type=request.job_type,
            max_results=request.max_jobs
        )
        
        await browser.close_all_sessions()
        
        return {
            "total_found": len(jobs),
            "easy_apply_count": sum(1 for j in jobs if j.easy_apply),
            "jobs": [
                {
                    "id": j.id,
                    "title": j.title,
                    "company": j.company,
                    "location": j.location,
                    "url": j.url,
                    "easy_apply": j.easy_apply,
                    "remote": j.remote,
                    "job_type": j.job_type
                }
                for j in jobs
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dice/apply")
async def apply_to_dice_jobs(request: DiceSearchRequest):
    """
    Search Dice and auto-apply to Easy Apply jobs
    
    Only applies to jobs marked as Easy Apply
    """
    try:
        profile = UserProfile(
            first_name=request.profile.first_name,
            last_name=request.profile.last_name,
            email=request.profile.email,
            phone=request.profile.phone,
            resume_path=request.profile.resume_path,
            resume_text=request.profile.resume_text,
            linkedin_url=request.profile.linkedin_url,
            portfolio_url=request.profile.portfolio_url,
            github_url=request.profile.github_url,
            salary_expectation=request.profile.salary_expectation,
            years_experience=request.profile.years_experience,
            skills=request.profile.skills,
            work_history=request.profile.work_history,
            education=request.profile.education,
            custom_answers=request.profile.custom_answers
        )
        
        ats_router = ATSRouter(profile)
        results = await ats_router.search_and_apply_dice(
            query=request.query,
            location=request.location,
            remote=request.remote,
            max_jobs=request.max_jobs
        )
        
        await ats_router.cleanup()
        
        return {
            "total_applied": len(results),
            "successful": sum(1 for r in results if r.success),
            "results": [
                {
                    "success": r.success,
                    "job_url": r.job_url,
                    "status": r.status,
                    "error": r.error_message
                }
                for r in results
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/handlers")
async def list_handlers():
    """List available ATS handlers"""
    try:
        dummy_profile = UserProfile(
            first_name="Test",
            last_name="User",
            email="test@example.com",
            phone="555-555-5555",
            resume_path="/tmp/test.pdf"
        )
        
        ats_router = ATSRouter(dummy_profile)
        stats = ats_router.get_handler_stats()
        
        return {
            "handlers": stats["available_handlers"],
            "supported_platforms": [
                "workday", "taleo", "icims", "successfactors",
                "adp", "greenhouse", "lever", "angellist", "dice"
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check for ATS automation service"""
    try:
        # Check BrowserBase connectivity
        from .browserbase_manager import BrowserBaseManager
        browser = BrowserBaseManager()
        
        return {
            "status": "healthy",
            "browserbase_connected": True,
            "active_sessions": browser.get_active_session_count()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# Function to include in main FastAPI app
def include_ats_routes(app: FastAPI):
    """Include ATS routes in main FastAPI application"""
    app.include_router(router)
