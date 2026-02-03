"""
BrowserBase Stealth Browser Manager
Handles anti-detection, captcha solving, and human-like interactions.
Updated with current user agents and improved stealth patches.
"""

import os
import random
import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass

from browserbase import Browserbase
from playwright.async_api import async_playwright, Page, Browser


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


@dataclass
class BrowserSession:
    """Represents an active browser session."""
    session_id: str
    browser: Browser
    page: Page
    platform: str
    connect_url: str


class StealthBrowserManager:
    """
    Manages stealth browser sessions via BrowserBase.
    Handles fingerprinting, proxies, and human-like behavior.
    """

    def __init__(self):
        creds = load_browserbase_creds()
        self.api_key = creds.get("BROWSERBASE_API_KEY")
        self.project_id = creds.get("BROWSERBASE_PROJECT_ID")
        self.bb = Browserbase(api_key=self.api_key) if self.api_key else None
        self.active_sessions: Dict[str, BrowserSession] = {}
        self.playwright = None

    async def initialize(self):
        """Initialize Playwright instance."""
        if not self.playwright:
            self.playwright = await async_playwright().start()

    async def create_stealth_session(
        self,
        platform: str,
        use_proxy: bool = True
    ) -> BrowserSession:
        """Create a fingerprint-randomized session for specific platform."""
        await self.initialize()

        if self.bb:
            # Use BrowserBase for stealth session
            session = self.bb.sessions.create(
                project_id=self.project_id,
                proxies=use_proxy,
            )
            print(f"[Browser] Created BrowserBase session: {session.id}")

            browser = await self.playwright.chromium.connect_over_cdp(
                session.connect_url,
                timeout=60000
            )
            connect_url = session.connect_url
            session_id = session.id
        else:
            # Fallback to local browser for development
            print("[Browser] Using local browser (no BrowserBase credentials)")
            browser = await self.playwright.chromium.launch(headless=True)
            connect_url = "local"
            session_id = f"local_{random.randint(1000, 9999)}"

        # Random viewport and user agent
        viewport = random.choice(VIEWPORTS)
        user_agent = random.choice(USER_AGENTS)

        context = browser.contexts[0] if browser.contexts else await browser.new_context(
            viewport=viewport,
            user_agent=user_agent,
        )

        page = await context.new_page()

        # Apply stealth patches
        await self._apply_stealth_patches(page)

        browser_session = BrowserSession(
            session_id=session_id,
            browser=browser,
            page=page,
            platform=platform,
            connect_url=connect_url
        )

        self.active_sessions[session_id] = browser_session
        return browser_session

    async def _apply_stealth_patches(self, page: Page):
        """Apply JavaScript patches to avoid detection."""
        await page.add_init_script("""
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
        """)

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
        """Attempt to solve CAPTCHA (BrowserBase handles many automatically)."""
        try:
            recaptcha = page.locator('iframe[src*="recaptcha"]').first
            if await recaptcha.count() > 0:
                print("[Browser] reCAPTCHA detected - BrowserBase handling...")
                await self.human_like_delay(5, 10)
                return True

            hcaptcha = page.locator('iframe[src*="hcaptcha"]').first
            if await hcaptcha.count() > 0:
                print("[Browser] hCaptcha detected - BrowserBase handling...")
                await self.human_like_delay(5, 10)
                return True

            return True

        except Exception as e:
            print(f"[Browser] CAPTCHA handling error: {e}")
            return False

    async def close_session(self, session_id: str):
        """Close a browser session."""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            try:
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


async def test_stealth():
    """Test the stealth browser manager."""
    manager = StealthBrowserManager()

    try:
        session = await manager.create_stealth_session("test", use_proxy=True)
        page = session.page

        print("[Test] Navigating to Indeed...")
        await page.goto("https://www.indeed.com/jobs?q=software+engineer&l=San+Francisco")

        await manager.wait_for_cloudflare(page)

        print(f"[Test] Title: {await page.title()}")

        await page.screenshot(path="/tmp/indeed_test.png")
        print("[Test] Screenshot saved to /tmp/indeed_test.png")

    finally:
        await manager.close_all()


if __name__ == "__main__":
    asyncio.run(test_stealth())
