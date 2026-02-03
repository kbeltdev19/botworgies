"""
CAPTCHA Solving Service
Supports multiple providers: 2captcha, Anti-Captcha, CapSolver
"""

import os
import asyncio
import base64
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import aiohttp


class CaptchaType(Enum):
    RECAPTCHA_V2 = "recaptcha_v2"
    RECAPTCHA_V3 = "recaptcha_v3"
    HCAPTCHA = "hcaptcha"
    IMAGE_CAPTCHA = "image_captcha"
    TURNSTILE = "turnstile"


@dataclass
class CaptchaResult:
    """Result of CAPTCHA solving attempt."""
    success: bool
    solution: Optional[str] = None
    token: Optional[str] = None
    cost: float = 0.0
    solve_time_seconds: float = 0.0
    error_message: Optional[str] = None
    provider: str = ""


class CaptchaSolver:
    """Unified CAPTCHA solving interface."""
    
    def __init__(self, provider: str = "capsolver"):
        self.provider = provider.lower()
        self.api_key = self._get_api_key()
        self.session: Optional[aiohttp.ClientSession] = None
        
    def _get_api_key(self) -> Optional[str]:
        """Get API key from environment."""
        env_vars = {
            "2captcha": "TWOCAPTCHA_API_KEY",
            "anti-captcha": "ANTICAPTCHA_API_KEY",
            "capsolver": "CAPSOLVER_API_KEY"
        }
        return os.getenv(env_vars.get(self.provider, ""))
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def solve_recaptcha_v2(
        self,
        site_key: str,
        page_url: str,
        timeout: int = 120
    ) -> CaptchaResult:
        """Solve reCAPTCHA v2."""
        if self.provider == "2captcha":
            return await self._solve_2captcha("userrecaptcha", site_key, page_url, timeout)
        elif self.provider == "capsolver":
            return await self._solve_capsolver("ReCaptchaV2TaskProxyLess", site_key, page_url, timeout)
        else:
            return CaptchaResult(success=False, error_message=f"Provider {self.provider} not supported")
    
    async def solve_hcaptcha(
        self,
        site_key: str,
        page_url: str,
        timeout: int = 120
    ) -> CaptchaResult:
        """Solve hCaptcha."""
        if self.provider == "2captcha":
            return await self._solve_2captcha("hcaptcha", site_key, page_url, timeout)
        elif self.provider == "capsolver":
            return await self._solve_capsolver("HCaptchaTaskProxyLess", site_key, page_url, timeout)
        else:
            return CaptchaResult(success=False, error_message=f"Provider {self.provider} not supported")
    
    async def solve_image_captcha(
        self,
        image_base64: str,
        timeout: int = 60
    ) -> CaptchaResult:
        """Solve image CAPTCHA."""
        if self.provider == "2captcha":
            return await self._solve_image_2captcha(image_base64, timeout)
        else:
            return CaptchaResult(success=False, error_message="Image CAPTCHA not supported for this provider")
    
    async def _solve_2captcha(
        self,
        method: str,
        site_key: str,
        page_url: str,
        timeout: int
    ) -> CaptchaResult:
        """Solve using 2captcha API."""
        import time
        start_time = time.time()
        
        try:
            # Submit CAPTCHA
            submit_url = "http://2captcha.com/in.php"
            data = {
                "key": self.api_key,
                "method": method,
                "googlekey": site_key,
                "pageurl": page_url,
                "json": 1
            }
            
            async with self.session.post(submit_url, data=data) as resp:
                result = await resp.json()
                
            if result.get("status") != 1:
                return CaptchaResult(
                    success=False,
                    error_message=f"2captcha submit error: {result.get('request')}",
                    provider="2captcha"
                )
            
            captcha_id = result["request"]
            
            # Poll for result
            result_url = f"http://2captcha.com/res.php?key={self.api_key}&action=get&id={captcha_id}&json=1"
            
            for _ in range(timeout // 5):
                await asyncio.sleep(5)
                
                async with self.session.get(result_url) as resp:
                    result = await resp.json()
                
                if result.get("status") == 1:
                    solve_time = time.time() - start_time
                    return CaptchaResult(
                        success=True,
                        token=result["request"],
                        solve_time_seconds=solve_time,
                        cost=0.003,  # Approximate cost for reCAPTCHA
                        provider="2captcha"
                    )
                
                if result.get("request") != "CAPCHA_NOT_READY":
                    return CaptchaResult(
                        success=False,
                        error_message=f"2captcha error: {result.get('request')}",
                        provider="2captcha"
                    )
            
            return CaptchaResult(
                success=False,
                error_message="2captcha timeout",
                provider="2captcha"
            )
            
        except Exception as e:
            return CaptchaResult(
                success=False,
                error_message=str(e),
                provider="2captcha"
            )
    
    async def _solve_capsolver(
        self,
        task_type: str,
        site_key: str,
        page_url: str,
        timeout: int
    ) -> CaptchaResult:
        """Solve using CapSolver API."""
        import time
        start_time = time.time()
        
        try:
            # Create task
            create_url = "https://api.capsolver.com/createTask"
            task_data = {
                "clientKey": self.api_key,
                "task": {
                    "type": task_type,
                    "websiteURL": page_url,
                    "websiteKey": site_key
                }
            }
            
            async with self.session.post(create_url, json=task_data) as resp:
                result = await resp.json()
            
            if result.get("errorId") != 0:
                return CaptchaResult(
                    success=False,
                    error_message=f"CapSolver error: {result.get('errorDescription')}",
                    provider="capsolver"
                )
            
            task_id = result["taskId"]
            
            # Poll for result
            result_url = "https://api.capsolver.com/getTaskResult"
            
            for _ in range(timeout // 2):
                await asyncio.sleep(2)
                
                async with self.session.post(result_url, json={
                    "clientKey": self.api_key,
                    "taskId": task_id
                }) as resp:
                    result = await resp.json()
                
                if result.get("status") == "ready":
                    solve_time = time.time() - start_time
                    solution = result.get("solution", {})
                    return CaptchaResult(
                        success=True,
                        token=solution.get("gRecaptchaResponse") or solution.get("token"),
                        solve_time_seconds=solve_time,
                        cost=0.002,  # Approximate cost
                        provider="capsolver"
                    )
                
                if result.get("errorId") != 0:
                    return CaptchaResult(
                        success=False,
                        error_message=f"CapSolver error: {result.get('errorDescription')}",
                        provider="capsolver"
                    )
            
            return CaptchaResult(
                success=False,
                error_message="CapSolver timeout",
                provider="capsolver"
            )
            
        except Exception as e:
            return CaptchaResult(
                success=False,
                error_message=str(e),
                provider="capsolver"
            )
    
    async def _solve_image_2captcha(
        self,
        image_base64: str,
        timeout: int
    ) -> CaptchaResult:
        """Solve image CAPTCHA using 2captcha."""
        import time
        start_time = time.time()
        
        try:
            submit_url = "http://2captcha.com/in.php"
            data = {
                "key": self.api_key,
                "method": "base64",
                "body": image_base64,
                "json": 1
            }
            
            async with self.session.post(submit_url, data=data) as resp:
                result = await resp.json()
            
            if result.get("status") != 1:
                return CaptchaResult(
                    success=False,
                    error_message=f"Image CAPTCHA submit error: {result.get('request')}",
                    provider="2captcha"
                )
            
            captcha_id = result["request"]
            result_url = f"http://2captcha.com/res.php?key={self.api_key}&action=get&id={captcha_id}&json=1"
            
            for _ in range(timeout // 5):
                await asyncio.sleep(5)
                
                async with self.session.get(result_url) as resp:
                    result = await resp.json()
                
                if result.get("status") == 1:
                    solve_time = time.time() - start_time
                    return CaptchaResult(
                        success=True,
                        solution=result["request"],
                        solve_time_seconds=solve_time,
                        cost=0.001,  # Lower cost for image CAPTCHA
                        provider="2captcha"
                    )
            
            return CaptchaResult(
                success=False,
                error_message="Image CAPTCHA timeout",
                provider="2captcha"
            )
            
        except Exception as e:
            return CaptchaResult(
                success=False,
                error_message=str(e),
                provider="2captcha"
            )


class CaptchaDetector:
    """Detect CAPTCHA presence on web pages."""
    
    CAPTCHA_INDICATORS = [
        # reCAPTCHA
        'g-recaptcha',
        'google.com/recaptcha',
        'recaptcha/api.js',
        # hCaptcha
        'h-captcha',
        'hcaptcha.com',
        # Cloudflare Turnstile
        'cf-turnstile',
        'challenges.cloudflare',
        # General
        'captcha',
        'i\'m not a robot',
        'security check',
        'verify you are human'
    ]
    
    @classmethod
    def detect_in_html(cls, html: str) -> tuple:
        """Detect CAPTCHA type in HTML content."""
        html_lower = html.lower()
        
        if 'g-recaptcha' in html_lower or 'google.com/recaptcha' in html_lower:
            return True, CaptchaType.RECAPTCHA_V2
        elif 'h-captcha' in html_lower or 'hcaptcha.com' in html_lower:
            return True, CaptchaType.HCAPTCHA
        elif 'cf-turnstile' in html_lower or 'cloudflare' in html_lower:
            return True, CaptchaType.TURNSTILE
        elif 'captcha' in html_lower:
            return True, CaptchaType.IMAGE_CAPTCHA
        
        return False, None
    
    @classmethod
    def detect_site_key(cls, html: str, captcha_type: CaptchaType) -> Optional[str]:
        """Extract site key from HTML."""
        import re
        
        if captcha_type == CaptchaType.RECAPTCHA_V2:
            # Look for data-sitekey
            match = re.search(r'data-sitekey=["\']([^"\']+)["\']', html)
            if match:
                return match.group(1)
            
            # Look for render parameter
            match = re.search(r'recaptcha.*render=([^&\'"\s]+)', html)
            if match:
                return match.group(1)
                
        elif captcha_type == CaptchaType.HCAPTCHA:
            match = re.search(r'data-sitekey=["\']([^"\']+)["\']', html)
            if match:
                return match.group(1)
        
        return None


# Convenience functions
async def solve_recaptcha(site_key: str, page_url: str, provider: str = "capsolver") -> CaptchaResult:
    """Quick solve reCAPTCHA."""
    async with CaptchaSolver(provider) as solver:
        return await solver.solve_recaptcha_v2(site_key, page_url)


async def solve_hcaptcha(site_key: str, page_url: str, provider: str = "capsolver") -> CaptchaResult:
    """Quick solve hCaptcha."""
    async with CaptchaSolver(provider) as solver:
        return await solver.solve_hcaptcha(site_key, page_url)
