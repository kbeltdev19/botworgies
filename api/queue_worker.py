#!/usr/bin/env python3
"""
Persistent Queue Worker

Processes job_queue items for running campaigns:
- Enforces rolling daily limits (overall + per platform) via application_engine
- Retries failures up to max_attempts with exponential backoff + jitter
- Adds platform cooldowns when rate-limited

This worker is designed to run inside the FastAPI lifespan task.
"""

from __future__ import annotations

import asyncio
import os
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from api.application_engine import ApplyOptions, RateLimitError, apply_job_url
from api.database import (
    fetch_next_queue_item,
    get_campaign,
    mark_queue_item_completed,
    schedule_queue_retry,
    set_campaign_status,
)
from api.logging_config import logger
from adapters import detect_platform_from_url


def _platform_id(platform: Any) -> str:
    return platform.value if hasattr(platform, "value") else str(platform)


def _now() -> datetime:
    return datetime.now()


def _is_permanent_error(msg: str) -> bool:
    t = (msg or "").lower()
    return any(
        needle in t
        for needle in [
            "requires authentication",
            "unsupported job platform",
            "resume not uploaded",
            "profile not saved",
        ]
    )


@dataclass
class WorkerConfig:
    poll_interval_seconds: float = float(os.getenv("QUEUE_POLL_INTERVAL_SECONDS", "2.0"))
    base_retry_delay_seconds: float = float(os.getenv("QUEUE_BASE_RETRY_DELAY_SECONDS", "20.0"))
    max_retry_delay_seconds: float = float(os.getenv("QUEUE_MAX_RETRY_DELAY_SECONDS", "1800.0"))  # 30m

    # Human-like delays between attempts
    delay_min_seconds: float = float(os.getenv("QUEUE_DELAY_MIN_SECONDS", "4.0"))
    delay_max_seconds: float = float(os.getenv("QUEUE_DELAY_MAX_SECONDS", "12.0"))

    linkedin_delay_min_seconds: float = float(os.getenv("QUEUE_LINKEDIN_DELAY_MIN_SECONDS", "60.0"))
    linkedin_delay_max_seconds: float = float(os.getenv("QUEUE_LINKEDIN_DELAY_MAX_SECONDS", "180.0"))

    rate_limit_cooldown_seconds: float = float(os.getenv("QUEUE_RATE_LIMIT_COOLDOWN_SECONDS", "1800.0"))  # 30m


@dataclass
class QueueWorker:
    browser_manager: Any
    kimi: Any
    config: WorkerConfig = field(default_factory=WorkerConfig)
    worker_id: str = field(default_factory=lambda: f"worker_{uuid.uuid4().hex[:10]}")
    _task: Optional[asyncio.Task] = None
    _stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    _platform_cooldowns: dict[tuple[str, str], datetime] = field(default_factory=dict)

    def start(self):
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self.run_loop(), name=f"queue-worker:{self.worker_id}")
        logger.info(f"QueueWorker started: {self.worker_id}")

    async def stop(self):
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass
        logger.info(f"QueueWorker stopped: {self.worker_id}")

    async def run_loop(self):
        while not self._stop_event.is_set():
            try:
                item = await fetch_next_queue_item(self.worker_id)
                if not item:
                    await asyncio.sleep(self.config.poll_interval_seconds)
                    continue

                await self._process_item(item)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"QueueWorker loop error: {e}")
                await asyncio.sleep(2.0)

    async def _process_item(self, item: dict):
        queue_id = str(item["id"])
        user_id = str(item["user_id"])
        job_url = str(item["job_url"])

        platform_id = (item.get("platform") or "").strip()
        if not platform_id:
            platform_id = _platform_id(detect_platform_from_url(job_url))

        cooldown_key = (user_id, platform_id)
        cooldown_until = self._platform_cooldowns.get(cooldown_key)
        if cooldown_until and cooldown_until > _now():
            await schedule_queue_retry(
                queue_id,
                attempts=int(item.get("attempts") or 0),
                next_run_at=cooldown_until,
                last_error=f"Platform cooldown until {cooldown_until.isoformat()}",
            )
            return

        # Campaign config drives apply options.
        campaign_id = str(item.get("campaign_id") or "")
        camp = await get_campaign(campaign_id) if campaign_id else None
        camp_cfg = (camp or {}).get("config") or {}

        auto_submit = bool(camp_cfg.get("auto_submit", False))
        generate_cover_letter = bool(camp_cfg.get("generate_cover_letter", True))
        cover_letter_tone = str(camp_cfg.get("cover_letter_tone") or "professional")

        # Human-like jitter between jobs.
        if platform_id == "linkedin":
            await asyncio.sleep(
                random.uniform(self.config.linkedin_delay_min_seconds, self.config.linkedin_delay_max_seconds)
            )
        else:
            await asyncio.sleep(random.uniform(self.config.delay_min_seconds, self.config.delay_max_seconds))

        attempts = int(item.get("attempts") or 0)
        max_attempts = int(item.get("max_attempts") or 3)

        try:
            record = await apply_job_url(
                user_id=user_id,
                job_url=job_url,
                browser_manager=self.browser_manager,
                kimi=self.kimi,
                options=ApplyOptions(
                    auto_submit=auto_submit,
                    generate_cover_letter=generate_cover_letter,
                    cover_letter_tone=cover_letter_tone,
                    campaign_id=campaign_id or None,
                    queue_item_id=queue_id,
                ),
            )

            # Terminal outcomes: submitted / pending_review / external_application / etc.
            await mark_queue_item_completed(
                queue_id,
                application_id=record.get("id"),
                status="completed",
            )

        except RateLimitError as e:
            err = str(e)
            # Cool down this platform and retry later.
            cooldown = _now() + timedelta(seconds=self.config.rate_limit_cooldown_seconds + random.uniform(0, 90))
            self._platform_cooldowns[cooldown_key] = cooldown

            # If we hit a daily limit, it's usually better to pause the campaign to avoid churn.
            if "daily limit" in err.lower() and campaign_id:
                await set_campaign_status(campaign_id, "paused", last_error=err)

            if attempts + 1 >= max_attempts:
                await mark_queue_item_completed(queue_id, status="failed", last_error=err)
                if campaign_id:
                    await set_campaign_status(campaign_id, "paused", last_error=f"Rate limited: {err}")
                return

            backoff = self._compute_backoff_seconds(attempts + 1, is_rate_limit=True)
            await schedule_queue_retry(
                queue_id,
                attempts=attempts + 1,
                next_run_at=_now() + timedelta(seconds=backoff),
                last_error=err,
            )

        except Exception as e:
            err = str(e)
            if _is_permanent_error(err) or attempts + 1 >= max_attempts:
                await mark_queue_item_completed(queue_id, status="failed", last_error=err)
                if campaign_id:
                    await set_campaign_status(campaign_id, "paused", last_error=err)
                return

            backoff = self._compute_backoff_seconds(attempts + 1, is_rate_limit=False)
            await schedule_queue_retry(
                queue_id,
                attempts=attempts + 1,
                next_run_at=_now() + timedelta(seconds=backoff),
                last_error=err,
            )

    def _compute_backoff_seconds(self, attempt_number: int, *, is_rate_limit: bool) -> float:
        base = self.config.base_retry_delay_seconds
        if is_rate_limit:
            base *= 3
        exp = min(self.config.max_retry_delay_seconds, base * (2 ** max(0, attempt_number - 1)))
        jitter = random.uniform(0, min(30.0, exp * 0.15))
        return float(min(self.config.max_retry_delay_seconds, exp + jitter))

