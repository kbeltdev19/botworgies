#!/usr/bin/env python3
"""
Application Engine

Shared logic for applying to a job URL, used by:
- /apply endpoints
- persistent queue worker (campaign autopilot)

Notes:
- Enforces overall + per-platform daily limits.
- Generates cover letters and answers only from provided resume/profile context.
"""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from api.auth import decrypt_sensitive_data
from api.config import config
from api.database import (
    count_applications_since,
    count_applications_since_by_platform,
    get_latest_resume,
    get_profile,
    get_settings,
    get_user_by_id,
    save_application,
)
from api.logging_config import logger, log_application
from monitoring.notifications import notifications

from adapters import (
    detect_platform_from_url,
    get_adapter,
    Resume,
    UserProfile,
)


DEFAULT_PLATFORM_DAILY_LIMITS: dict[str, int] = {
    "linkedin": int(os.getenv("LINKEDIN_DAILY_LIMIT_DEFAULT", "5")),
    "indeed": int(os.getenv("INDEED_DAILY_LIMIT_DEFAULT", "15")),
    "greenhouse": int(os.getenv("GREENHOUSE_DAILY_LIMIT_DEFAULT", "30")),
    "lever": int(os.getenv("LEVER_DAILY_LIMIT_DEFAULT", "30")),
    "company": int(os.getenv("COMPANY_DAILY_LIMIT_DEFAULT", "10")),
}


class RateLimitError(RuntimeError):
    pass


def _platform_id(platform: Any) -> str:
    return platform.value if hasattr(platform, "value") else str(platform)


def _looks_rate_limited(text: str) -> bool:
    t = (text or "").lower()
    return any(
        needle in t
        for needle in [
            "429",
            "too many requests",
            "rate limit",
            "temporarily blocked",
            "try again later",
        ]
    )


def _get_platform_daily_limits(settings: Optional[dict]) -> dict[str, int]:
    limits = dict(DEFAULT_PLATFORM_DAILY_LIMITS)
    raw = (settings or {}).get("platform_daily_limits_json")
    if raw:
        try:
            import json

            overrides = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(overrides, dict):
                for k, v in overrides.items():
                    if not k:
                        continue
                    try:
                        limits[str(k)] = int(v)
                    except Exception:
                        continue
        except Exception:
            pass
    return limits


@dataclass
class ApplyOptions:
    auto_submit: bool = False
    generate_cover_letter: bool = True
    cover_letter_tone: str = "professional"
    campaign_id: Optional[str] = None
    queue_item_id: Optional[str] = None
    application_id: Optional[str] = None


async def apply_job_url(
    *,
    user_id: str,
    job_url: str,
    browser_manager: Any,
    kimi: Any,
    options: ApplyOptions,
) -> dict[str, Any]:
    """
    Apply to a job URL, save an application record, and return the saved payload.
    Raises RateLimitError for rate-limit conditions (daily limits or platform throttles).
    """
    if not browser_manager:
        raise RuntimeError("Browser automation not available")

    settings = await get_settings(user_id) or {}

    # Overall daily limit
    daily_limit = int(settings.get("daily_limit", config.DEFAULT_DAILY_LIMIT))
    cutoff = datetime.now() - timedelta(hours=24)
    sent_24h = await count_applications_since(user_id, cutoff)
    if sent_24h >= daily_limit:
        raise RateLimitError(f"Daily limit reached ({daily_limit}). Sent: {sent_24h}.")

    # Resume + profile
    resume = await get_latest_resume(user_id)
    profile = await get_profile(user_id)
    if not resume:
        raise RuntimeError("Resume not uploaded")
    if not profile:
        raise RuntimeError("Profile not saved")

    platform = detect_platform_from_url(job_url)
    platform_id = _platform_id(platform)
    if platform_id == "unknown":
        raise RuntimeError("Unsupported job platform")

    # Per-platform daily limit
    limits = _get_platform_daily_limits(settings)
    plat_limit = limits.get(platform_id)
    if plat_limit is not None:
        plat_sent = await count_applications_since_by_platform(user_id, platform_id, cutoff)
        if plat_sent >= int(plat_limit):
            raise RateLimitError(
                f"Platform daily limit reached for {platform_id} ({plat_limit}). Sent: {plat_sent}."
            )

    linkedin_cookie = None
    if platform_id == "linkedin":
        if settings.get("linkedin_cookie_encrypted"):
            linkedin_cookie = decrypt_sensitive_data(settings["linkedin_cookie_encrypted"])
        else:
            raise RuntimeError("LinkedIn requires authentication. Add li_at cookie in settings.")

    adapter = None
    application_id = options.application_id or f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    started = datetime.now().isoformat()

    cover_letter = None
    job = None
    try:
        adapter = get_adapter(platform_id, browser_manager, session_cookie=linkedin_cookie, use_unified=False)
        job = await adapter.get_job_details(job_url)

        if options.generate_cover_letter:
            try:
                cover_letter = await kimi.generate_cover_letter(
                    resume_summary=(resume.get("raw_text") or "")[:2000],
                    job_title=getattr(job, "title", "Position") or "Position",
                    company_name=getattr(job, "company", "Company") or "Company",
                    job_requirements=(getattr(job, "description", "") or "")[:2000],
                    tone=options.cover_letter_tone,
                )
            except Exception as e:
                logger.warning(f"Cover letter generation failed: {e}")

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
            location=profile.get("location") or "",
            linkedin_url=profile.get("linkedin_url"),
            years_experience=profile.get("years_experience"),
            work_authorization=profile.get("work_authorization", "Yes"),
            sponsorship_required=profile.get("sponsorship_required", "No"),
            custom_answers=profile.get("custom_answers", {}) or {},
        )

        if hasattr(adapter, "apply_to_job"):
            result = await adapter.apply_to_job(
                job=job,
                resume=resume_obj,
                profile=profile_obj,
                cover_letter=cover_letter,
                auto_submit=options.auto_submit,
            )
        elif hasattr(adapter, "apply"):
            result = await adapter.apply(job=job, resume=resume_obj)
        else:
            raise RuntimeError("Adapter does not implement apply_to_job/apply")

        status_val = result.status.value if hasattr(result.status, "value") else str(result.status)

        record = {
            "id": application_id,
            "user_id": user_id,
            "job_url": job_url,
            "job_title": getattr(job, "title", None),
            "company": getattr(job, "company", None),
            "platform": platform_id,
            "status": status_val,
            "message": getattr(result, "message", "") or "",
            "error": getattr(result, "error", None),
            "screenshot_path": getattr(result, "screenshot_path", None),
            "timestamp": started,
            "campaign_id": options.campaign_id,
            "queue_item_id": options.queue_item_id,
        }

        await save_application(record)
        log_application(application_id, user_id, job_url, status_val, getattr(result, "error", None))

        # Best-effort notifications.
        try:
            await notifications.notify_application(
                {
                    "user_id": user_id,
                    "application_id": application_id,
                    "platform": platform_id,
                    "job_title": record.get("job_title"),
                    "company": record.get("company"),
                    "job_url": job_url,
                    "status": status_val,
                    "message": record.get("message"),
                    "error": record.get("error"),
                },
                slack_url=settings.get("slack_webhook_url") or "",
                discord_url=settings.get("discord_webhook_url") or "",
            )
        except Exception:
            pass

        # Treat obvious platform throttles as rate-limited for upstream scheduling.
        if _looks_rate_limited(record.get("message") or "") or _looks_rate_limited(record.get("error") or ""):
            raise RateLimitError(record.get("error") or record.get("message") or "Rate limited")

        return record

    except Exception as e:
        # Persist an error record for auditability.
        error_text = str(e)
        platform_id_for_record = platform_id if "platform_id" in locals() else "unknown"
        record = {
            "id": application_id,
            "user_id": user_id,
            "job_url": job_url,
            "job_title": getattr(job, "title", None) if job else None,
            "company": getattr(job, "company", None) if job else None,
            "platform": platform_id_for_record,
            "status": "error",
            "error": error_text,
            "timestamp": started,
            "campaign_id": options.campaign_id,
            "queue_item_id": options.queue_item_id,
        }
        try:
            await save_application(record)
            log_application(application_id, user_id, job_url, "error", error_text)
        except Exception:
            pass

        try:
            await notifications.notify_application(
                {
                    "user_id": user_id,
                    "application_id": application_id,
                    "platform": platform_id_for_record,
                    "job_title": record.get("job_title"),
                    "company": record.get("company"),
                    "job_url": job_url,
                    "status": "error",
                    "error": error_text,
                },
                slack_url=settings.get("slack_webhook_url") or "",
                discord_url=settings.get("discord_webhook_url") or "",
            )
        except Exception:
            pass

        if isinstance(e, RateLimitError) or _looks_rate_limited(error_text):
            raise RateLimitError(error_text)

        raise

    finally:
        try:
            if adapter and hasattr(adapter, "close"):
                await adapter.close()
        except Exception:
            pass
