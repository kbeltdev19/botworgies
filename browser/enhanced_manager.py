#!/usr/bin/env python3
"""
Enhanced BrowserBase Manager with Full Proxy and CAPTCHA Handling

Features:
- BrowserBase residential proxies (automatic)
- BrowserBase built-in CAPTCHA solving
- Session persistence and rotation
- Advanced error recovery
- Concurrent session management
"""

import os
import random
import asyncio
import time
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

# BrowserBase SDK
try:
    from browserbase import Browserbase
    BROWSERBASE_SDK_AVAILABLE = True
except ImportError:
    BROWSERBASE_SDK_AVAILABLE = False


class CaptchaStatus(Enum):
    """CAPTCHA solving status."""
    NOT_PRESENT = "not_present"
    DETECTED = "detected"
    SOLVING = "solving"
    SOLVED = "solved"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class CaptchaResult:
    """Result of CAPTCHA solving attempt."""
    status: CaptchaStatus
    type: Optional[str] = None  # recaptcha, hcaptcha, cloudflare, etc.
    solve_time: float = 0.0
    error_message: Optional[str] = None


@dataclass
class ProxyConfig:
    """Proxy configuration."""
    enabled: bool = True
    type: str = "residential"  # residential, datacenter
    country: str = "US"
    state: Optional[str] = None
    city: Optional[str] = None
    sticky: bool = True  # Keep same IP for session


@dataclass
class SessionMetrics:
    """Metrics for a browser session."""
    session_id: str
    created_at: datetime = field(default_factory=datetime.now)
    requests_made: int = 0
    captchas_encountered: int = 0
    captchas_solved: int = 0
    errors: List[Dict] = field(default_factory=list)
    last_used: Optional[datetime] = None
    total_duration: float = 0.0


class EnhancedBrowserManager:
    """
    Enhanced BrowserBase manager with full proxy and CAPTCHA handling.
    Optimized for high-volume job applications.
    """
    
    def __init__(
        self,
        max_concurrent_sessions: int = 50,
        captcha_timeout: int = 120,
        enable_captcha_solving: bool = True,
        proxy_config: Optional[ProxyConfig] = None
    ):
        self.max_concurrent_sessions = max_concurrent_sessions
        self.captcha_timeout = captcha_timeout
        self.enable_captcha_solving = enable_captcha_solving
        self.proxy_config = proxy_config or ProxyConfig()
        
        # BrowserBase setup
        self.api_key = os.getenv("BROWSERBASE_API_KEY")
        self.project_id = os.getenv("BROWSERBASE_PROJECT_ID", "")
        self.bb = Browserbase(api_key=self.api_key) if self.api_key and BROWSERBASE_SDK_AVAILABLE else None
        
        # Session management
        self.active_sessions: Dict[str, Any] = {}
        self.session_metrics: Dict[str, SessionMetrics] = {}
        self.playwright = None
        self._semaphore = asyncio.Semaphore(max_concurrent_sessions)
        
        # Session rotation
        self.session_rotation_interval = 300  # 5 minutes
        self._last_rotation = time.time()
        
        # Stats
        self.stats = {
            "total_sessions_created": 0,
            "total_captchas_solved": 0,
            "total_captchas_failed": 0,
            "total_requests": 0,
            "errors": []
        }
    
    async def initialize(self):
        """Initialize Playwright."""
        if not self.playwright:
            self.playwright = await async_playwright().start()
            print(f"[BrowserManager] Initialized with max {self.max_concurrent_sessions} concurrent sessions")
    
    async def create_session(
        self,
        platform: str = "generic",
        use_proxy: bool = True,
        solve_captcha: bool = True,
        timeout: int = 60000
    ) -> Dict[str, Any]:
        """
        Create a new BrowserBase session with full features.
        
        Args:
            platform: Platform identifier (linkedin, indeed, etc.)
            use_proxy: Use BrowserBase residential proxy
            solve_captcha: Enable CAPTCHA solving
            timeout: Connection timeout
        
        Returns:
            Session dict with browser, context, page, and metadata
        """
        async with self._semaphore:
            await self.initialize()
            
            if not self.bb:
                raise RuntimeError("BrowserBase not available. Check BROWSERBASE_API_KEY.")
            
            try:
                # Build BrowserBase session config
                session_config = {
                    "project_id": self.project_id,
                }
                
                # Add proxy configuration
                if use_proxy and self.proxy_config.enabled:
                    session_config["proxies"] = True
                    # BrowserBase uses residential proxies by default
                    # Advanced proxy config can be added here if needed
                
                # Add CAPTCHA solving
                if solve_captcha and self.enable_captcha_solving:
                    # BrowserBase handles CAPTCHA automatically when proxies=True
                    pass
                
                # Create BrowserBase session
                start_time = time.time()
                bb_session = self.bb.sessions.create(**session_config)
                
                # Connect via CDP
                browser = await self.playwright.chromium.connect_over_cdp(
                    bb_session.connect_url,
                    timeout=timeout
                )
                
                # Get or create context
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                
                # Create page
                page = await context.new_page()
                
                # Build session object
                session = {
                    "session_id": bb_session.id,
                    "browser": browser,
                    "context": context,
                    "page": page,
                    "platform": platform,
                    "connect_url": bb_session.connect_url,
                    "created_at": datetime.now(),
                    "solve_captcha": solve_captcha,
                    "proxy_enabled": use_proxy
                }
                
                # Track metrics
                self.active_sessions[bb_session.id] = session
                self.session_metrics[bb_session.id] = SessionMetrics(
                    session_id=bb_session.id
                )
                self.stats["total_sessions_created"] += 1
                
                connect_time = time.time() - start_time
                print(f"[BrowserManager] Created session {bb_session.id[:8]}... for {platform} (connect: {connect_time:.2f}s)")
                
                return session
                
            except Exception as e:
                error_msg = str(e)
                self.stats["errors"].append({
                    "time": datetime.now().isoformat(),
                    "error": error_msg,
                    "platform": platform
                })
                print(f"[BrowserManager] Failed to create session: {error_msg}")
                raise
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get an active session by ID."""
        return self.active_sessions.get(session_id)
    
    async def check_captcha(self, page: Page) -> CaptchaResult:
        """
        Check if CAPTCHA is present and get its status.
        BrowserBase automatically solves CAPTCHAs, but we check status.
        """
        start_time = time.time()
        
        # Check for common CAPTCHA indicators
        captcha_selectors = [
            'iframe[src*="recaptcha"]',
            'iframe[src*="hcaptcha"]',
            '.g-recaptcha',
            '#recaptcha',
            '[data-captcha]',
            '.cf-turnstile',
            '#challenge-running',
            '.cf-browser-verification'
        ]
        
        captcha_type = None
        captcha_present = False
        
        for selector in captcha_selectors:
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    captcha_present = True
                    if 'recaptcha' in selector:
                        captcha_type = 'recaptcha'
                    elif 'hcaptcha' in selector:
                        captcha_type = 'hcaptcha'
                    elif 'cf-' in selector or 'challenge' in selector:
                        captcha_type = 'cloudflare'
                    break
            except:
                continue
        
        if not captcha_present:
            return CaptchaResult(status=CaptchaStatus.NOT_PRESENT)
        
        # CAPTCHA detected - BrowserBase should auto-solve with proxies enabled
        # Wait a bit and check if it's resolved
        print(f"[BrowserManager] CAPTCHA detected ({captcha_type}) - waiting for auto-solve...")
        
        solve_start = time.time()
        while time.time() - solve_start < self.captcha_timeout:
            # Re-check if CAPTCHA is still present
            still_present = False
            for selector in captcha_selectors:
                try:
                    element = page.locator(selector).first
                    if await element.count() > 0:
                        still_present = True
                        break
                except:
                    continue
            
            if not still_present:
                solve_time = time.time() - solve_start
                print(f"[BrowserManager] CAPTCHA solved in {solve_time:.1f}s")
                return CaptchaResult(
                    status=CaptchaStatus.SOLVED,
                    type=captcha_type,
                    solve_time=solve_time
                )
            
            await asyncio.sleep(2)
        
        # Timeout
        return CaptchaResult(
            status=CaptchaStatus.TIMEOUT,
            type=captcha_type,
            solve_time=time.time() - solve_start,
            error_message="CAPTCHA solve timeout"
        )
    
    async def wait_for_load(
        self,
        page: Page,
        url: str,
        wait_for_captcha: bool = True,
        timeout: int = 60000
    ) -> Dict[str, Any]:
        """
        Navigate to URL and wait for load, handling CAPTCHA if present.
        
        Returns:
            Dict with success status, load time, and CAPTCHA result
        """
        start_time = time.time()
        
        try:
            # Navigate
            response = await page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            
            # Wait for network idle
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except:
                pass  # Network idle is optional
            
            load_time = time.time() - start_time
            
            # Check for CAPTCHA if requested
            captcha_result = None
            if wait_for_captcha:
                captcha_result = await self.check_captcha(page)
                
                if captcha_result.status == CaptchaStatus.TIMEOUT:
                    return {
                        "success": False,
                        "load_time": load_time,
                        "captcha_result": captcha_result,
                        "error": "CAPTCHA solve timeout"
                    }
            
            return {
                "success": True,
                "load_time": load_time,
                "captcha_result": captcha_result,
                "status_code": response.status if response else None
            }
            
        except Exception as e:
            return {
                "success": False,
                "load_time": time.time() - start_time,
                "captcha_result": None,
                "error": str(e)
            }
    
    async def human_like_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Human-like random delay."""
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)
    
    async def human_like_type(self, page: Page, selector: str, text: str, clear_first: bool = True):
        """Type text like a human with variable delays."""
        element = page.locator(selector).first
        
        # Click to focus
        await element.click()
        await self.human_like_delay(0.2, 0.5)
        
        # Clear if needed
        if clear_first:
            await element.fill("")
            await self.human_like_delay(0.1, 0.3)
        
        # Type with variable delays
        for char in text:
            await element.type(char, delay=random.randint(30, 120))
            
            # Occasional pause (typo correction simulation)
            if random.random() < 0.03:
                await asyncio.sleep(random.uniform(0.3, 0.8))
        
        # Random mouse movement
        await page.mouse.move(
            random.randint(100, 800),
            random.randint(100, 600)
        )
    
    async def human_like_click(self, page: Page, selector: str, delay_after: bool = True):
        """Click with human-like behavior."""
        element = page.locator(selector).first
        
        # Get element position
        box = await element.bounding_box()
        if box:
            # Click within element bounds (not always center)
            x = box["x"] + random.uniform(5, max(6, box["width"] - 5))
            y = box["y"] + random.uniform(5, max(6, box["height"] - 5))
            
            # Move mouse
            await page.mouse.move(x, y)
            await self.human_like_delay(0.1, 0.3)
            
            # Click
            await page.mouse.click(x, y)
        else:
            await element.click()
        
        if delay_after:
            await self.human_like_delay(0.5, 1.5)
    
    async def scroll_like_human(self, page: Page, amount: int = None):
        """Scroll with human-like behavior."""
        if amount is None:
            amount = random.randint(200, 600)
        
        # Multiple small scrolls instead of one big jump
        remaining = amount
        while remaining > 0:
            scroll_chunk = min(remaining, random.randint(50, 150))
            await page.evaluate(f"window.scrollBy(0, {scroll_chunk})")
            remaining -= scroll_chunk
            await asyncio.sleep(random.uniform(0.1, 0.3))
        
        await self.human_like_delay(0.3, 0.8)
    
    async def smart_wait(
        self,
        page: Page,
        selector: str,
        timeout: int = 10000,
        poll_interval: float = 0.5
    ) -> bool:
        """Smart wait for element with polling."""
        start_time = time.time()
        
        while time.time() - start_time < timeout / 1000:
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    # Check if visible
                    if await element.is_visible():
                        return True
            except:
                pass
            
            await asyncio.sleep(poll_interval)
        
        return False
    
    async def close_session(self, session_id: str):
        """Close a session and clean up."""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            
            try:
                # Update metrics
                if session_id in self.session_metrics:
                    metrics = self.session_metrics[session_id]
                    metrics.total_duration = (datetime.now() - metrics.created_at).total_seconds()
                
                # Close browser
                await session["context"].close()
                await session["browser"].close()
                
                print(f"[BrowserManager] Closed session {session_id[:8]}...")
                
            except Exception as e:
                print(f"[BrowserManager] Error closing session: {e}")
            
            finally:
                del self.active_sessions[session_id]
    
    async def close_all_sessions(self):
        """Close all active sessions."""
        session_ids = list(self.active_sessions.keys())
        for session_id in session_ids:
            await self.close_session(session_id)
        
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        
        print(f"[BrowserManager] All sessions closed")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive stats."""
        return {
            "active_sessions": len(self.active_sessions),
            "total_sessions_created": self.stats["total_sessions_created"],
            "total_captchas_solved": self.stats["total_captchas_solved"],
            "total_captchas_failed": self.stats["total_captchas_failed"],
            "total_requests": self.stats["total_requests"],
            "error_count": len(self.stats["errors"]),
            "recent_errors": self.stats["errors"][-5:] if self.stats["errors"] else []
        }
    
    async def rotate_sessions_if_needed(self):
        """Rotate sessions periodically to avoid detection."""
        if time.time() - self._last_rotation > self.session_rotation_interval:
            print("[BrowserManager] Performing session rotation...")
            
            # Close oldest sessions
            sessions_by_age = sorted(
                self.active_sessions.items(),
                key=lambda x: x[1]["created_at"]
            )
            
            # Close 20% of oldest sessions
            to_close = int(len(sessions_by_age) * 0.2)
            for session_id, _ in sessions_by_age[:to_close]:
                await self.close_session(session_id)
            
            self._last_rotation = time.time()


# Factory function for easy creation
async def create_browser_manager(max_sessions: int = 50) -> EnhancedBrowserManager:
    """Create and initialize an EnhancedBrowserManager."""
    manager = EnhancedBrowserManager(max_concurrent_sessions=max_sessions)
    await manager.initialize()
    return manager
