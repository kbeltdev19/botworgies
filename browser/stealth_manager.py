"""
BrowserBase Stealth Browser Manager with Local Fallback
Handles anti-detection, captcha solving, and human-like interactions.
Updated with current user agents and improved stealth patches.

Features:
- Primary: BrowserBase cloud sessions with residential proxies
- Fallback: Local Playwright browsers with stealth patches
- Automatic fallback when BrowserBase is at capacity
"""

import os
import random
import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

# BrowserBase SDK (optional)
try:
    from browserbase import Browserbase
    BROWSERBASE_SDK_AVAILABLE = True
except ImportError:
    BROWSERBASE_SDK_AVAILABLE = False


class BrowserMode(Enum):
    """Browser session mode."""
    BROWSERBASE = "browserbase"
    LOCAL = "local"


# Updated user agents for 2025/2026
USER_AGENTS = [
    # Chrome 131 on Windows 11
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Chrome 130 on Windows 11
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Chrome 131 on macOS Sonoma
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Safari 17 on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    # Edge 131 on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    # Firefox 122 on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

# Viewport sizes for randomization
VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1680, "height": 1050},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
    {"width": 1280, "height": 800},
]

# Error indicators for BrowserBase capacity issues
BROWSERBASE_CAPACITY_ERRORS = [
    "rate limit",
    "too many requests",
    "capacity exceeded",
    "quota exceeded",
    "concurrent sessions limit",
    "429",
    "503",
    "resource exhausted",
]


def load_browserbase_creds() -> dict:
    """Load BrowserBase credentials from env vars or tokens file."""
    creds = {}

    if os.getenv("BROWSERBASE_API_KEY"):
        creds["BROWSERBASE_API_KEY"] = os.getenv("BROWSERBASE_API_KEY")
        creds["BROWSERBASE_PROJECT_ID"] = os.getenv("BROWSERBASE_PROJECT_ID", "")
        return creds

    try:
        with open(os.path.expanduser("~/.clawdbot/secrets/tokens.env")) as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    key, val = line.strip().split("=", 1)
                    creds[key] = val
    except FileNotFoundError:
        pass

    return creds


def is_capacity_error(error_msg: str) -> bool:
    """Check if error is a BrowserBase capacity/rate limit error."""
    error_lower = error_msg.lower()
    return any(indicator in error_lower for indicator in BROWSERBASE_CAPACITY_ERRORS)


@dataclass
class BrowserSession:
    """Represents an active browser session."""
    session_id: str
    browser: Browser
    context: BrowserContext
    page: Page
    platform: str
    connect_url: str
    mode: BrowserMode = BrowserMode.BROWSERBASE


class StealthBrowserManager:
    """
    Manages stealth browser sessions with BrowserBase primary and local fallback.
    Handles fingerprinting, proxies, and human-like behavior.
    """

    def __init__(self, prefer_local: bool = False):
        """
        Initialize the browser manager.
        
        Args:
            prefer_local: If True, prefer local browsers even if BrowserBase is available.
        """
        creds = load_browserbase_creds()
        self.api_key = creds.get("BROWSERBASE_API_KEY")
        self.project_id = creds.get("BROWSERBASE_PROJECT_ID")
        self.bb = Browserbase(api_key=self.api_key) if self.api_key and BROWSERBASE_SDK_AVAILABLE else None
        self.prefer_local = prefer_local
        self.active_sessions: Dict[str, BrowserSession] = {}
        self.playwright = None
        self._browserbase_failed = False  # Track if BrowserBase is failing

    async def initialize(self):
        """Initialize Playwright instance."""
        if not self.playwright:
            self.playwright = await async_playwright().start()

    async def create_stealth_session(
        self,
        platform: str,
        use_proxy: bool = True,
        force_local: bool = False
    ) -> BrowserSession:
        """
        Create a fingerprint-randomized session for specific platform.
        
        Falls back to local browser if BrowserBase is at capacity or unavailable.
        """
        await self.initialize()

        # Try BrowserBase first (unless forced local or already failed)
        if not force_local and not self.prefer_local and not self._browserbase_failed and self.bb:
            try:
                session = await self._create_browserbase_session(platform, use_proxy)
                print(f"[Browser] Created BrowserBase session: {session.session_id}")
                return session
            except Exception as e:
                error_msg = str(e)
                if is_capacity_error(error_msg):
                    print(f"[Browser] BrowserBase at capacity ({error_msg}), falling back to local browser...")
                    self._browserbase_failed = True  # Mark as failed to avoid repeated attempts
                else:
                    print(f"[Browser] BrowserBase error: {error_msg}, falling back to local browser...")

        # Fallback to local browser
        return await self._create_local_session(platform, use_proxy)

    async def _create_browserbase_session(
        self,
        platform: str,
        use_proxy: bool = True
    ) -> BrowserSession:
        """Create a BrowserBase cloud session with CAPTCHA solving enabled."""
        session = self.bb.sessions.create(
            project_id=self.project_id,
            proxies=use_proxy,
            browser_settings={
                "advancedStealth": True,
                "solveCaptchas": True,
            },
        )

        browser = await self.playwright.chromium.connect_over_cdp(
            session.connect_url,
            timeout=60000
        )

        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()

        browser_session = BrowserSession(
            session_id=session.id,
            browser=browser,
            context=context,
            page=page,
            platform=platform,
            connect_url=session.connect_url,
            mode=BrowserMode.BROWSERBASE
        )

        self.active_sessions[session.id] = browser_session
        return browser_session

    async def _create_local_session(
        self,
        platform: str,
        use_proxy: bool = True
    ) -> BrowserSession:
        """Create a local browser session with stealth patches."""
        print("[Browser] Using local browser session with stealth patches")

        # Random viewport and user agent
        viewport = random.choice(VIEWPORTS)
        user_agent = random.choice(USER_AGENTS)

        # Build launch args for local browser
        launch_args = [
            f"--window-size={viewport['width']},{viewport['height']}",
            "--disable-blink-features=AutomationControlled",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
        ]

        # Launch browser
        browser = await self.playwright.chromium.launch(
            headless=True,
            args=launch_args
        )

        # Create context with stealth settings
        context = await browser.new_context(
            viewport=viewport,
            user_agent=user_agent,
            locale="en-US",
            timezone_id="America/New_York",
            permissions=["geolocation"],
            color_scheme="light",
        )

        # Add stealth init script
        await context.add_init_script(self._get_stealth_script())

        page = await context.new_page()
        session_id = f"local_{platform}_{random.randint(1000, 9999)}"

        browser_session = BrowserSession(
            session_id=session_id,
            browser=browser,
            context=context,
            page=page,
            platform=platform,
            connect_url="local",
            mode=BrowserMode.LOCAL
        )

        self.active_sessions[session_id] = browser_session
        return browser_session

    def _get_stealth_script(self) -> str:
        """Get JavaScript stealth patches."""
        return """
            // Hide webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Mock realistic plugins array
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    const plugins = [
                        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                        { name: 'Native Client', filename: 'internal-nacl-plugin' }
                    ];
                    plugins.length = 3;
                    return plugins;
                }
            });

            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });

            // Mock platform
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32'
            });

            // Mock hardware concurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8
            });

            // Mock device memory
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8
            });

            // Hide automation indicators
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };

            // Override permissions API
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // Mock WebGL vendor and renderer
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) return 'Intel Inc.';
                if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                return getParameter.call(this, parameter);
            };

            // Prevent iframe detection
            Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
                get: function() {
                    return window;
                }
            });
        """

    async def human_like_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Add human-like random delay."""
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)

    async def human_like_type(self, page: Page, selector: str, text: str):
        """Type text with variable delays, like a human."""
        element = page.locator(selector).first
        await element.click()

        await self.human_like_delay(0.3, 0.8)

        for char in text:
            await element.type(char, delay=random.randint(50, 150))
            if random.random() < 0.05:
                await asyncio.sleep(random.uniform(0.2, 0.5))

        await page.mouse.move(
            random.randint(100, 800),
            random.randint(100, 600)
        )

    async def human_like_click(self, page: Page, selector: str):
        """Click with human-like mouse movement."""
        element = page.locator(selector).first
        box = await element.bounding_box()

        if box:
            x = box["x"] + random.uniform(5, box["width"] - 5)
            y = box["y"] + random.uniform(5, box["height"] - 5)
            await page.mouse.move(x, y)
            await self.human_like_delay(0.1, 0.3)
            await page.mouse.click(x, y)
        else:
            await element.click()

    async def human_like_scroll(self, page: Page, direction: str = "down", amount: int = None):
        """Scroll like a human would."""
        if amount is None:
            amount = random.randint(200, 500)

        if direction == "down":
            await page.evaluate(f"window.scrollBy(0, {amount})")
        else:
            await page.evaluate(f"window.scrollBy(0, -{amount})")

        await self.human_like_delay(0.5, 1.5)

    async def wait_for_cloudflare(self, page: Page, timeout: int = 15):
        """Wait for Cloudflare challenge to complete."""
        start_time = asyncio.get_event_loop().time()
        
        # Known Cloudflare challenge indicators
        challenge_indicators = [
            "just a moment",
            "checking your browser",
            "please wait",
            "cloudflare",
            "ddos protection",
            "verify you are human",
        ]

        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                title = await page.title()
                title_lower = title.lower()
                
                # Check if we're past the challenge
                is_challenged = any(ind in title_lower for ind in challenge_indicators)
                
                if not is_challenged:
                    # Also check for challenge div
                    challenge_div = page.locator('#challenge-running, #cf-wrapper, .cf-browser-verification').first
                    if await challenge_div.count() == 0:
                        return True
                
                print(f"[Browser] Waiting for Cloudflare... (title: {title[:40]})")
                await asyncio.sleep(2)
            except Exception as e:
                print(f"[Browser] Cloudflare check error: {e}")
                await asyncio.sleep(1)

        print("[Browser] Cloudflare timeout - proceeding anyway")
        return False

    async def solve_captcha(self, page: Page, captcha_type: str = "auto") -> bool:
        """
        Attempt to solve CAPTCHA using CapSolver if available.
        Falls back to waiting if CapSolver is not configured.
        """
        try:
            # Import here to avoid circular dependency
            from browser.captcha_manager import get_captcha_manager
            
            captcha_manager = get_captcha_manager()
            
            # Check if CapSolver is configured
            if not captcha_manager.is_configured():
                # Fallback: wait and hope
                recaptcha = page.locator('iframe[src*="recaptcha"]').first
                if await recaptcha.count() > 0:
                    print("[Browser] reCAPTCHA detected - waiting...")
                    await self.human_like_delay(5, 10)
                    return True

                hcaptcha = page.locator('iframe[src*="hcaptcha"]').first
                if await hcaptcha.count() > 0:
                    print("[Browser] hCaptcha detected - waiting...")
                    await self.human_like_delay(5, 10)
                    return True
                
                return True
            
            # Use CapSolver
            print("[Browser] Checking for CAPTCHA...")
            result = await captcha_manager.detect_and_solve(page)
            
            if result.success:
                print(f"[Browser] ✅ CAPTCHA solved in {result.solve_time:.1f}s (cost: ${result.cost:.4f})")
                
                # If we got a token, try to submit it
                if result.token:
                    # Find and fill the CAPTCHA response field
                    try:
                        # Common response field names
                        response_selectors = [
                            'textarea[name="g-recaptcha-response"]',
                            'textarea[id="g-recaptcha-response"]',
                            'input[name="cf-turnstile-response"]',
                            '[name="cf-turnstile-response"]'
                        ]
                        
                        for selector in response_selectors:
                            field = page.locator(selector).first
                            if await field.count() > 0:
                                await field.fill(result.token)
                                print(f"[Browser] Filled CAPTCHA response")
                                break
                    except Exception as e:
                        print(f"[Browser] Could not fill CAPTCHA response: {e}")
                
                return True
            else:
                print(f"[Browser] ❌ CAPTCHA solve failed: {result.error}")
                return False

        except Exception as e:
            print(f"[Browser] CAPTCHA handling error: {e}")
            return False
    
    async def handle_cloudflare_with_captcha_solver(self, page: Page, timeout: int = 60) -> bool:
        """
        Handle Cloudflare challenge with CapSolver support.
        More aggressive than wait_for_cloudflare - actually tries to solve.
        """
        start_time = asyncio.get_event_loop().time()
        
        challenge_indicators = [
            "just a moment",
            "checking your browser", 
            "please wait",
            "cloudflare",
            "ddos protection",
            "verify you are human",
            "challenge"
        ]
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                title = await page.title()
                content = await page.content()
                title_lower = title.lower()
                content_lower = content.lower()
                
                # Check if we're still on challenge page
                is_challenged = any(ind in title_lower for ind in challenge_indicators)
                has_challenge_div = await page.locator(
                    '#challenge-running, #cf-wrapper, .cf-browser-verification, .turnstile'
                ).count() > 0
                
                if not is_challenged and not has_challenge_div:
                    return True
                
                # Try to solve with CapSolver
                from browser.captcha_manager import get_captcha_manager
                captcha_manager = get_captcha_manager()
                
                if captcha_manager.is_configured() and has_challenge_div:
                    print(f"[Browser] Cloudflare challenge detected, attempting CAPTCHA solve...")
                    result = await captcha_manager.solve_cloudflare_turnstile(page.url)
                    
                    if result.success and result.token:
                        # Inject the token
                        await page.evaluate(f"""
                            () => {{
                                const turnstileFields = document.querySelectorAll('[name="cf-turnstile-response"]');
                                turnstileFields.forEach(f => f.value = "{result.token}");
                                // Trigger any form submission
                                const forms = document.querySelectorAll('form');
                                forms.forEach(f => f.dispatchEvent(new Event('submit')));
                            }}
                        """)
                        print("[Browser] Injected CAPTCHA token, waiting for redirect...")
                        await asyncio.sleep(5)
                        continue
                
                print(f"[Browser] Waiting for Cloudflare... ({title[:40]})")
                await asyncio.sleep(3)
                
            except Exception as e:
                print(f"[Browser] Cloudflare handle error: {e}")
                await asyncio.sleep(2)
        
        return False

    async def close_session(self, session_id: str):
        """Close a browser session."""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            try:
                await session.context.close()
                await session.browser.close()
            except Exception:
                pass
            del self.active_sessions[session_id]
            print(f"[Browser] Closed session: {session_id}")

    async def close_all(self):
        """Close all active sessions."""
        for session_id in list(self.active_sessions.keys()):
            await self.close_session(session_id)

        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception:
                pass
            self.playwright = None

    def get_stats(self) -> Dict[str, Any]:
        """Get browser manager statistics."""
        browserbase_count = sum(1 for s in self.active_sessions.values() if s.mode == BrowserMode.BROWSERBASE)
        local_count = sum(1 for s in self.active_sessions.values() if s.mode == BrowserMode.LOCAL)
        
        return {
            "total_sessions": len(self.active_sessions),
            "browserbase_sessions": browserbase_count,
            "local_sessions": local_count,
            "browserbase_available": self.bb is not None and not self._browserbase_failed,
            "browserbase_failed": self._browserbase_failed,
        }

    def reset_browserbase_status(self):
        """Reset BrowserBase failed status (to retry BrowserBase after a cooldown)."""
        self._browserbase_failed = False
        print("[Browser] Reset BrowserBase status - will retry on next session creation")


async def test_stealth():
    """Test the stealth browser manager with fallback."""
    manager = StealthBrowserManager()

    try:
        # Test 1: Try BrowserBase (or fallback to local)
        print("=" * 50)
        print("Test 1: Creating stealth session (BrowserBase -> Local fallback)")
        session = await manager.create_stealth_session("test", use_proxy=True)
        page = session.page
        print(f"Session mode: {session.mode.value}")
        print(f"Session ID: {session.session_id}")

        print("[Test] Navigating to Indeed...")
        await page.goto("https://www.indeed.com/jobs?q=software+engineer&l=San+Francisco")
        await manager.wait_for_cloudflare(page)
        print(f"[Test] Title: {await page.title()}")

        await page.screenshot(path="/tmp/indeed_test.png")
        print("[Test] Screenshot saved to /tmp/indeed_test.png")

        await manager.close_session(session.session_id)

        # Test 2: Force local browser
        print("=" * 50)
        print("Test 2: Creating local browser session (forced)")
        session = await manager.create_stealth_session("test", use_proxy=True, force_local=True)
        page = session.page
        print(f"Session mode: {session.mode.value}")

        print("[Test] Navigating to example.com...")
        await page.goto("https://example.com")
        print(f"[Test] Title: {await page.title()}")

        await page.screenshot(path="/tmp/example_local.png")
        print("[Test] Screenshot saved to /tmp/example_local.png")

        # Print stats
        print("=" * 50)
        print("Final stats:", manager.get_stats())

    finally:
        await manager.close_all()


if __name__ == "__main__":
    asyncio.run(test_stealth())
