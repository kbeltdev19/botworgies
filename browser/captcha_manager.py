"""
CAPTCHA Manager with CapSolver Integration
Handles Cloudflare and reCAPTCHA solving using CapSolver API
"""

import os
import asyncio
import base64
from typing import Optional, Dict, Any
from dataclasses import dataclass
from playwright.async_api import Page


@dataclass
class CaptchaResult:
    """Result of CAPTCHA solving attempt."""
    success: bool
    token: Optional[str] = None
    solution: Optional[str] = None
    cost: float = 0.0
    solve_time: float = 0.0
    error: Optional[str] = None


class CapSolverManager:
    """
    CapSolver CAPTCHA solving integration.
    Supports: Cloudflare Turnstile, reCAPTCHA v2/v3, hCaptcha
    """
    
    API_URL = "https://api.capsolver.com"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("CAPSOLVER_API_KEY")
        self.total_cost = 0.0
        self.solved_count = 0
        self.failed_count = 0
        
    def is_configured(self) -> bool:
        """Check if CapSolver is properly configured."""
        return self.api_key is not None and len(self.api_key) > 10
    
    async def solve_cloudflare_turnstile(
        self, 
        page_url: str, 
        site_key: Optional[str] = None,
        timeout: int = 120
    ) -> CaptchaResult:
        """
        Solve Cloudflare Turnstile CAPTCHA.
        
        Cost: ~$0.002 per solve
        """
        import aiohttp
        import time
        
        if not self.is_configured():
            return CaptchaResult(success=False, error="CapSolver API key not configured")
        
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                # Create task
                create_url = f"{self.API_URL}/createTask"
                task_data = {
                    "clientKey": self.api_key,
                    "task": {
                        "type": "AntiCloudflareTask",
                        "websiteURL": page_url,
                        "proxy": ""  # Using CapSolver's proxy
                    }
                }
                
                # If we have a site_key, use Turnstile task instead
                if site_key:
                    task_data["task"] = {
                        "type": "AntiTurnstileTaskProxyLess",
                        "websiteURL": page_url,
                        "websiteKey": site_key
                    }
                
                async with session.post(create_url, json=task_data) as resp:
                    result = await resp.json()
                
                if result.get("errorId") != 0:
                    self.failed_count += 1
                    return CaptchaResult(
                        success=False,
                        error=f"CapSolver create error: {result.get('errorDescription')}"
                    )
                
                task_id = result["taskId"]
                
                # Poll for result
                result_url = f"{self.API_URL}/getTaskResult"
                
                for _ in range(timeout // 2):
                    await asyncio.sleep(2)
                    
                    async with session.post(result_url, json={
                        "clientKey": self.api_key,
                        "taskId": task_id
                    }) as resp:
                        result = await resp.json()
                    
                    if result.get("status") == "ready":
                        solve_time = time.time() - start_time
                        solution = result.get("solution", {})
                        token = solution.get("token") or solution.get("gRecaptchaResponse")
                        
                        self.solved_count += 1
                        self.total_cost += 0.002  # Approximate cost
                        
                        return CaptchaResult(
                            success=True,
                            token=token,
                            solution=str(solution),
                            cost=0.002,
                            solve_time=solve_time
                        )
                    
                    if result.get("errorId") != 0:
                        self.failed_count += 1
                        return CaptchaResult(
                            success=False,
                            error=f"CapSolver error: {result.get('errorDescription')}"
                        )
                
                self.failed_count += 1
                return CaptchaResult(success=False, error="CapSolver timeout")
                
        except Exception as e:
            self.failed_count += 1
            return CaptchaResult(success=False, error=str(e))
    
    async def solve_recaptcha_v2(
        self, 
        page_url: str, 
        site_key: str,
        timeout: int = 120
    ) -> CaptchaResult:
        """
        Solve reCAPTCHA v2.
        
        Cost: ~$0.003 per solve
        """
        import aiohttp
        import time
        
        if not self.is_configured():
            return CaptchaResult(success=False, error="CapSolver API key not configured")
        
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                create_url = f"{self.API_URL}/createTask"
                task_data = {
                    "clientKey": self.api_key,
                    "task": {
                        "type": "ReCaptchaV2TaskProxyLess",
                        "websiteURL": page_url,
                        "websiteKey": site_key
                    }
                }
                
                async with session.post(create_url, json=task_data) as resp:
                    result = await resp.json()
                
                if result.get("errorId") != 0:
                    self.failed_count += 1
                    return CaptchaResult(
                        success=False,
                        error=f"CapSolver create error: {result.get('errorDescription')}"
                    )
                
                task_id = result["taskId"]
                result_url = f"{self.API_URL}/getTaskResult"
                
                for _ in range(timeout // 2):
                    await asyncio.sleep(2)
                    
                    async with session.post(result_url, json={
                        "clientKey": self.api_key,
                        "taskId": task_id
                    }) as resp:
                        result = await resp.json()
                    
                    if result.get("status") == "ready":
                        solve_time = time.time() - start_time
                        solution = result.get("solution", {})
                        token = solution.get("gRecaptchaResponse")
                        
                        self.solved_count += 1
                        self.total_cost += 0.003
                        
                        return CaptchaResult(
                            success=True,
                            token=token,
                            solution=str(solution),
                            cost=0.003,
                            solve_time=solve_time
                        )
                    
                    if result.get("errorId") != 0:
                        self.failed_count += 1
                        return CaptchaResult(
                            success=False,
                            error=f"CapSolver error: {result.get('errorDescription')}"
                        )
                
                self.failed_count += 1
                return CaptchaResult(success=False, error="CapSolver timeout")
                
        except Exception as e:
            self.failed_count += 1
            return CaptchaResult(success=False, error=str(e))
    
    async def detect_and_solve(self, page: Page) -> CaptchaResult:
        """
        Detect CAPTCHA type on page and solve it.
        
        Returns CaptchaResult with success status
        """
        page_url = page.url
        content = await page.content()
        content_lower = content.lower()
        
        # Check for Cloudflare Turnstile
        if 'cf-turnstile' in content_lower or 'cloudflare' in content_lower:
            # Try to find turnstile site key
            import re
            site_key_match = re.search(r'data-sitekey=["\']([^"\']+)["\']', content)
            site_key = site_key_match.group(1) if site_key_match else None
            
            print(f"[CapSolver] Cloudflare Turnstile detected, solving...")
            return await self.solve_cloudflare_turnstile(page_url, site_key)
        
        # Check for reCAPTCHA
        if 'g-recaptcha' in content_lower or 'google.com/recaptcha' in content_lower:
            import re
            site_key_match = re.search(r'data-sitekey=["\']([^"\']+)["\']', content)
            if site_key_match:
                site_key = site_key_match.group(1)
                print(f"[CapSolver] reCAPTCHA v2 detected, solving...")
                return await self.solve_recaptcha_v2(page_url, site_key)
        
        # Check for hCaptcha
        if 'h-captcha' in content_lower or 'hcaptcha.com' in content_lower:
            # hCaptcha support can be added similarly
            return CaptchaResult(success=False, error="hCaptcha not yet implemented")
        
        return CaptchaResult(success=False, error="No recognized CAPTCHA found")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get CAPTCHA solving statistics."""
        return {
            "solved": self.solved_count,
            "failed": self.failed_count,
            "total_cost_usd": round(self.total_cost, 4),
            "configured": self.is_configured()
        }


# Global instance
captcha_manager = CapSolverManager()


def get_captcha_manager() -> CapSolverManager:
    """Get the global CAPTCHA manager instance."""
    return captcha_manager
