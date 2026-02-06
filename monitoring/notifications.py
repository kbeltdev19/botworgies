#!/usr/bin/env python3
"""
Notifications: Slack/Discord webhooks and optional SMTP email.

Design goals:
- Zero-config by default (no notifications if not configured).
- Non-blocking (network calls are best-effort).
- Safety: do not include secrets; keep payloads minimal.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class NotificationConfig:
    slack_webhook_url: str = os.getenv("SLACK_WEBHOOK_URL", "")
    discord_webhook_url: str = os.getenv("DISCORD_WEBHOOK_URL", "")

    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str = os.getenv("SMTP_USERNAME", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_tls: bool = os.getenv("SMTP_TLS", "true").lower() == "true"
    smtp_from: str = os.getenv("SMTP_FROM", "")


class NotificationManager:
    def __init__(self, config: Optional[NotificationConfig] = None):
        self.config = config or NotificationConfig()

    def enabled(self) -> bool:
        return bool(self.config.slack_webhook_url or self.config.discord_webhook_url or self.config.smtp_host)

    async def _post_json(self, url: str, payload: dict) -> bool:
        if not url:
            return False
        try:
            timeout = aiohttp.ClientTimeout(total=12)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as resp:
                    if 200 <= resp.status < 300:
                        return True
                    text = await resp.text()
                    logger.warning(f"Webhook failed ({resp.status}): {text[:200]}")
                    return False
        except Exception as e:
            logger.warning(f"Webhook error: {e}")
            return False

    async def notify_application(self, event: dict, *, slack_url: str = "", discord_url: str = ""):
        """
        Send a normalized application event to Slack/Discord.

        Expected `event` keys (best-effort):
        - user_id, application_id, platform, job_title, company, job_url, status, message, error
        """
        status = str(event.get("status") or "").lower()
        title = str(event.get("job_title") or "(unknown)")
        company = str(event.get("company") or "(unknown)")
        platform = str(event.get("platform") or "(unknown)")
        job_url = str(event.get("job_url") or "")
        application_id = str(event.get("application_id") or "")

        line = f"[{platform}] {status}: {title} @ {company}"
        if application_id:
            line += f" ({application_id})"

        details = {
            "text": line,
            "job_url": job_url,
            "status": status,
            "platform": platform,
            "company": company,
            "job_title": title,
            "error": event.get("error"),
            "message": event.get("message"),
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Slack: simple text payload
        slack_payload = {"text": f"{line}\n{job_url}".strip()}

        # Discord: content payload
        discord_payload = {"content": f"{line}\n{job_url}".strip()}

        # Prefer per-user overrides, else env
        slack = slack_url or self.config.slack_webhook_url
        discord = discord_url or self.config.discord_webhook_url

        await asyncio.gather(
            self._post_json(slack, slack_payload) if slack else asyncio.sleep(0),
            self._post_json(discord, discord_payload) if discord else asyncio.sleep(0),
            return_exceptions=True,
        )

        # Keep structured detail in logs for debugging.
        logger.info(f"Notification event: {json.dumps(details, ensure_ascii=True)[:800]}")

    async def send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Send a plain-text email via SMTP. Best-effort."""
        if not (self.config.smtp_host and self.config.smtp_from and to_email):
            return False

        msg = EmailMessage()
        msg["From"] = self.config.smtp_from
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)

        def _send():
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=20) as s:
                if self.config.smtp_tls:
                    s.starttls()
                if self.config.smtp_username:
                    s.login(self.config.smtp_username, self.config.smtp_password)
                s.send_message(msg)

        try:
            await asyncio.to_thread(_send)
            return True
        except Exception as e:
            logger.warning(f"Email send failed: {e}")
            return False


notifications = NotificationManager()

