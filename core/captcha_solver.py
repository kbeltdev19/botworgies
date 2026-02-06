"""
CAPTCHA Solver - Capsolver Integration
Fallback for when BrowserBase's built-in CAPTCHA solving doesn't work
"""

import os
import asyncio
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Capsolver API
CAPSOLVER_API_KEY = os.getenv("CAPSOLVER_API_KEY", "")
CAPSOLVER_API_URL = "https://api.capsolver.com"


class CaptchaSolver:
    """
    Capsolver CAPTCHA solving service integration.
    
    Usage:
        solver = CaptchaSolver()
        result = await solver.solve_recaptcha_v2(
            site_key="6Lc...",
            page_url="https://example.com"
        )
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or CAPSOLVER_API_KEY
        
    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key)
    
    async def solve_recaptcha_v2(self, site_key: str, page_url: str) -> Optional[str]:
        """
        Solve reCAPTCHA v2 using Capsolver.
        
        Args:
            site_key: The reCAPTCHA site key
            page_url: The URL of the page with CAPTCHA
            
        Returns:
            The CAPTCHA token or None if failed
        """
        if not self.api_key:
            logger.warning("Capsolver API key not configured")
            return None
            
        try:
            import aiohttp
            
            # Create task
            async with aiohttp.ClientSession() as session:
                payload = {
                    "clientKey": self.api_key,
                    "task": {
                        "type": "ReCaptchaV2TaskProxyLess",
                        "websiteKey": site_key,
                        "websiteURL": page_url,
                    }
                }
                
                logger.info(f"[Capsolver] Creating reCAPTCHA v2 task for {page_url}")
                async with session.post(
                    f"{CAPSOLVER_API_URL}/createTask",
                    json=payload
                ) as resp:
                    data = await resp.json()
                    
                if data.get("errorId") != 0:
                    logger.error(f"[Capsolver] Create task failed: {data}")
                    return None
                    
                task_id = data["taskId"]
                logger.info(f"[Capsolver] Task created: {task_id}")
                
                # Poll for result
                for attempt in range(60):  # Max 60 seconds
                    await asyncio.sleep(2)
                    
                    result_payload = {
                        "clientKey": self.api_key,
                        "taskId": task_id
                    }
                    
                    async with session.post(
                        f"{CAPSOLVER_API_URL}/getTaskResult",
                        json=result_payload
                    ) as resp:
                        result = await resp.json()
                    
                    if result.get("errorId") != 0:
                        logger.error(f"[Capsolver] Get result failed: {result}")
                        return None
                    
                    status = result.get("status")
                    if status == "ready":
                        token = result.get("solution", {}).get("gRecaptchaResponse")
                        logger.info("[Capsolver] CAPTCHA solved successfully")
                        return token
                    elif status == "processing":
                        continue
                    else:
                        logger.error(f"[Capsolver] Unexpected status: {status}")
                        return None
                        
                logger.error("[Capsolver] Timeout waiting for solution")
                return None
                
        except Exception as e:
            logger.error(f"[Capsolver] Error solving CAPTCHA: {e}")
            return None
    
    async def solve_recaptcha_v3(self, site_key: str, page_url: str, action: str = "verify") -> Optional[str]:
        """Solve reCAPTCHA v3."""
        if not self.api_key:
            return None
            
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                payload = {
                    "clientKey": self.api_key,
                    "task": {
                        "type": "ReCaptchaV3TaskProxyLess",
                        "websiteKey": site_key,
                        "websiteURL": page_url,
                        "pageAction": action,
                    }
                }
                
                logger.info(f"[Capsolver] Creating reCAPTCHA v3 task for {page_url}")
                async with session.post(
                    f"{CAPSOLVER_API_URL}/createTask",
                    json=payload
                ) as resp:
                    data = await resp.json()
                    
                if data.get("errorId") != 0:
                    return None
                    
                task_id = data["taskId"]
                
                # Poll for result
                for _ in range(60):
                    await asyncio.sleep(2)
                    
                    result_payload = {
                        "clientKey": self.api_key,
                        "taskId": task_id
                    }
                    
                    async with session.post(
                        f"{CAPSOLVER_API_URL}/getTaskResult",
                        json=result_payload
                    ) as resp:
                        result = await resp.json()
                    
                    if result.get("status") == "ready":
                        return result.get("solution", {}).get("gRecaptchaResponse")
                        
                return None
                
        except Exception as e:
            logger.error(f"[Capsolver] Error: {e}")
            return None


# Global instance
_captcha_solver: Optional[CaptchaSolver] = None


def get_captcha_solver() -> CaptchaSolver:
    """Get or create global CAPTCHA solver instance."""
    global _captcha_solver
    if _captcha_solver is None:
        _captcha_solver = CaptchaSolver()
    return _captcha_solver
