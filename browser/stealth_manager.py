"""
BrowserBase Stealth Browser Manager with Local Fallback
Handles anti-detection, captcha solving, and human-like interactions.
Updated with current user agents and improved stealth patches.

Features:
- Primary: BrowserBase cloud sessions with residential proxies
- Fallback: Local Playwright browsers with stealth patches
- Automatic fallback when BrowserBase is at capacity
- Screenshot capture on success/failure
- HAR and video recording for debugging
"""

import os
import random
import asyncio
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from pathlib import Path

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


@dataclass
class SessionConfig:
    """Configuration for a browser session."""
    platform: str
    record_video: bool = True
    record_har: bool = True
    capture_screenshots: bool = True
    screenshot_dir: str = "/tmp/browser_screenshots"
    video_dir: str = "/tmp/browser_videos"
    har_dir: str = "/tmp/browser_har"


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
    config: SessionConfig = None
    video_path: Optional[str] = None
    har_path: Optional[str] = None


class StealthBrowserManager:
    """
    Manages stealth browser sessions with BrowserBase primary and local fallback.
    Handles fingerprinting, proxies, and human-like behavior.
    """

    def __init__(self, prefer_local: bool = False, max_bb_sessions: int = 10, 
                 record_video: bool = False, record_har: bool = False):
        """
        Initialize the browser manager.
        
        Args:
            prefer_local: If True, prefer local browsers even if BrowserBase is available.
            max_bb_sessions: Maximum concurrent BrowserBase sessions.
            record_video: Enable video recording for debugging.
            record_har: Enable HAR (network) recording for debugging.
        """
        creds = load_browserbase_creds()
        self.api_key = creds.get("BROWSERBASE_API_KEY")
        self.project_id = creds.get("BROWSERBASE_PROJECT_ID")
        self.bb = Browserbase(api_key=self.api_key) if self.api_key and BROWSERBASE_SDK_AVAILABLE else None
        self.prefer_local = prefer_local
        self.active_sessions: Dict[str, BrowserSession] = {}
        self.playwright = None
        self._browserbase_failed = False
        
        # Recording settings
        self.record_video = record_video
        self.record_har = record_har
        
        # Create directories
        self.screenshot_dir = Path("/tmp/browser_screenshots")
        self.video_dir = Path("/tmp/browser_videos")
        self.har_dir = Path("/tmp/browser_har")
        
        for dir_path in [self.screenshot_dir, self.video_dir, self.har_dir]:
            dir_path.mkdir(exist_ok=True)

    async def initialize(self):
        """Initialize Playwright instance."""
        if not self.playwright:
            self.playwright = await async_playwright().start()

    async def create_stealth_session(
        self,
        platform: str,
        use_proxy: bool = True,
        force_local: bool = False,
        record_video: bool = None,
        record_har: bool = None
    ) -> BrowserSession:
        """
        Create a fingerprint-randomized session for specific platform.
        
        Args:
            platform: Platform identifier (linkedin, workday, etc.)
            use_proxy: Whether to use proxy
            force_local: Force using local browser
            record_video: Override default video recording setting
            record_har: Override default HAR recording setting
        """
        await self.initialize()
        
        # Determine recording settings
        should_record_video = record_video if record_video is not None else self.record_video
        should_record_har = record_har if record_har is not None else self.record_har
        
        # Try BrowserBase first (unless forced local)
        if not force_local and not self.prefer_local and self.bb:
            try:
                session = await self._create_browserbase_session(platform, use_proxy)
                print(f"[Browser] ✅ BrowserBase session created: {session.session_id}")
                return session
            except Exception as e:
                error_msg = str(e)
                if is_capacity_error(error_msg):
                    print(f"[Browser] ❌ BrowserBase at capacity, falling back to local...")
                else:
                    print(f"[Browser] ❌ BrowserBase error ({error_msg[:50]}...), falling back...")
        
        # Fallback to local browser
        return await self._create_local_session(platform, use_proxy, should_record_video, should_record_har)

    async def _create_browserbase_session(
        self,
        platform: str,
        use_proxy: bool = True
    ) -> BrowserSession:
        """Create a BrowserBase cloud session with CAPTCHA solving."""
        # Try Advanced Stealth first
        try:
            session = self.bb.sessions.create(
                project_id=self.project_id,
                proxies=use_proxy,
                browser_settings={
                    "advancedStealth": True,
                    "solveCaptchas": True,
                },
            )
            print("[Browser] ✅ BrowserBase Advanced Stealth session created")
        except Exception as e:
            error_msg = str(e).lower()
            if "enterprise" in error_msg or "scale" in error_msg or "plan" in error_msg:
                print("[Browser] ⚠️  Advanced Stealth not available, using Basic Stealth...")
                session = self.bb.sessions.create(
                    project_id=self.project_id,
                    proxies=use_proxy,
                    browser_settings={
                        "solveCaptchas": True,
                    },
                )
                print("[Browser] ✅ BrowserBase Basic Stealth session created")
            else:
                raise

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
        use_proxy: bool = True,
        record_video: bool = False,
        record_har: bool = False
    ) -> BrowserSession:
        """Create a local browser session with stealth patches and optional recording."""
        print("[Browser] Using local browser session with stealth patches")

        # Random viewport and user agent
        viewport = random.choice(VIEWPORTS)
        user_agent = random.choice(USER_AGENTS)

        # Build launch args
        launch_args = [
            f"--window-size={viewport['width']},{viewport['height']}",
            "--disable-blink-features=AutomationControlled",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
        ]

        # Try to add proxy
        proxy_config = None
        if use_proxy:
            try:
                from browser.proxy_config import get_proxy_for_local_browser
                proxy_config = get_proxy_for_local_browser()
                if proxy_config:
                    print(f"[Browser] ✅ Proxy enabled for local browser")
                    launch_args.append(f"--proxy-server={proxy_config['server']}")
                else:
                    print("[Browser] ⚠️  No proxy configured for local browser")
            except Exception as e:
                print(f"[Browser] ⚠️  Proxy config error: {e}")

        # Launch browser
        browser = await self.playwright.chromium.launch(
            headless=True,
            args=launch_args
        )

        # Create context with stealth settings and recording options
        context_args = {
            "viewport": viewport,
            "user_agent": user_agent,
            "locale": "en-US",
            "timezone_id": "America/New_York",
            "permissions": ["geolocation"],
            "color_scheme": "light",
        }
        
        # Add recording options
        if record_video:
            video_path = self.video_dir / f"{platform}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            video_path.mkdir(exist_ok=True)
            context_args["record_video_dir"] = str(video_path)
            context_args["record_video_size"] = {"width": viewport["width"], "height": viewport["height"]}
        
        if proxy_config and proxy_config.get("username"):
            context_args["proxy"] = proxy_config

        context = await browser.new_context(**context_args)
        
        # Enable HAR recording if requested
        har_path = None
        if record_har:
            har_path = str(self.har_dir / f"{platform}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.har")
            await context.route_from_har(har_path, update=True)

        # Add stealth init script
        await context.add_init_script(self._get_stealth_script())

        page = await context.new_page()
        session_id = f"local_{platform}_{random.randint(1000, 9999)}"
        
        # Set up video path tracking
        video_path_str = None
        if record_video:
            video_path_str = str(video_path)

        browser_session = BrowserSession(
            session_id=session_id,
            browser=browser,
            context=context,
            page=page,
            platform=platform,
            connect_url="local",
            mode=BrowserMode.LOCAL,
            video_path=video_path_str,
            har_path=har_path
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

    async def capture_screenshot(self, page: Page, name: str, full_page: bool = True) -> str:
        """Capture a screenshot with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.png"
        filepath = self.screenshot_dir / filename
        
        try:
            await page.screenshot(path=str(filepath), full_page=full_page)
            print(f"[Browser] Screenshot saved: {filepath}")
            return str(filepath)
        except Exception as e:
            print(f"[Browser] Screenshot failed: {e}")
            return ""

    async def capture_element_screenshot(self, page: Page, selector: str, name: str) -> str:
        """Capture screenshot of a specific element."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_element_{timestamp}.png"
        filepath = self.screenshot_dir / filename
        
        try:
            element = page.locator(selector).first
            if await element.count() > 0:
                await element.screenshot(path=str(filepath))
                print(f"[Browser] Element screenshot saved: {filepath}")
                return str(filepath)
        except Exception as e:
            print(f"[Browser] Element screenshot failed: {e}")
        return ""

    async def wait_for_cloudflare(self, page: Page, timeout: int = 15):
        """Wait for Cloudflare challenge to complete."""
        start_time = asyncio.get_event_loop().time()
        
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
                
                is_challenged = any(ind in title_lower for ind in challenge_indicators)
                
                if not is_challenged:
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

    async def close_session(self, session_id: str):
        """Close a browser session and cleanup."""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            
            # Capture final screenshot if page is still accessible
            try:
                await self.capture_screenshot(session.page, f"final_{session_id}")
            except:
                pass
            
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
            
        print("[Browser] All sessions closed and Playwright stopped")

    def get_stats(self) -> Dict[str, Any]:
        """Get browser manager statistics."""
        browserbase_count = sum(1 for s in self.active_sessions.values() if s.mode == BrowserMode.BROWSERBASE)
        local_count = sum(1 for s in self.active_sessions.values() if s.mode == BrowserMode.LOCAL)
        
        return {
            "total_sessions": len(self.active_sessions),
            "browserbase_sessions": browserbase_count,
            "local_sessions": local_count,
            "browserbase_available": self.bb is not None,
        }


async def test_stealth():
    """Test the stealth browser manager with fallback."""
    manager = StealthBrowserManager(record_video=True, record_har=True)

    try:
        # Test 1: Try BrowserBase (or fallback to local)
        print("=" * 50)
        print("Test 1: Creating stealth session (BrowserBase -> Local fallback)")
        session = await manager.create_stealth_session("test", use_proxy=True)
        page = session.page
        print(f"Session mode: {session.mode.value}")
        print(f"Session ID: {session.session_id}")

        print("[Test] Navigating to example.com...")
        await page.goto("https://example.com")
        print(f"[Test] Title: {await page.title()}")
        
        # Capture screenshot
        screenshot = await manager.capture_screenshot(page, "test_example")
        print(f"[Test] Screenshot: {screenshot}")

        await manager.close_session(session.session_id)

        # Print stats
        print("=" * 50)
        print("Final stats:", manager.get_stats())

    finally:
        await manager.close_all()


if __name__ == "__main__":
    asyncio.run(test_stealth())
