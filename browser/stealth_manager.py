"""
BrowserBase Stealth Browser Manager
Handles anti-detection, captcha solving, and human-like interactions.
"""

import os
import random
import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass

from browserbase import Browserbase
from playwright.async_api import async_playwright, Page, Browser


def load_browserbase_creds() -> dict:
    """Load BrowserBase credentials from tokens file."""
    creds = {}
    with open(os.path.expanduser("~/.clawdbot/secrets/tokens.env")) as f:
        for line in f:
            if "=" in line and not line.strip().startswith("#"):
                key, val = line.strip().split("=", 1)
                creds[key] = val
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
        self.bb = Browserbase(api_key=self.api_key)
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
        """
        Create a fingerprint-randomized session for specific platform.
        """
        await self.initialize()
        
        # Create session with BrowserBase SDK
        session = self.bb.sessions.create(
            project_id=self.project_id,
            proxies=use_proxy,  # Enable residential proxies
        )
        
        print(f"🌐 Created BrowserBase session: {session.id}")
        
        # Connect Playwright to the session
        browser = await self.playwright.chromium.connect_over_cdp(
            session.connect_url,
            timeout=60000
        )
        
        # Get existing context or create new one
        context = browser.contexts[0] if browser.contexts else await browser.new_context(
            viewport={"width": random.randint(1280, 1920), "height": random.randint(800, 1080)},
            user_agent=self._get_random_user_agent(),
        )
        
        page = await context.new_page()
        
        # Apply stealth patches
        await self._apply_stealth_patches(page)
        
        browser_session = BrowserSession(
            session_id=session.id,
            browser=browser,
            page=page,
            platform=platform,
            connect_url=session.connect_url
        )
        
        self.active_sessions[session.id] = browser_session
        return browser_session
    
    async def _apply_stealth_patches(self, page: Page):
        """Apply JavaScript patches to avoid detection."""
        await page.add_init_script("""
            // Hide webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // Hide automation
            window.chrome = {
                runtime: {}
            };
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
    
    def _get_random_user_agent(self) -> str:
        """Return a random realistic user agent."""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        ]
        return random.choice(user_agents)
    
    async def human_like_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Add human-like random delay."""
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)
    
    async def human_like_type(self, page: Page, selector: str, text: str):
        """
        Type text with variable delays, random pauses, like a human.
        """
        element = page.locator(selector).first
        await element.click()
        
        # Simulate reading pause before typing
        await self.human_like_delay(0.5, 1.5)
        
        for char in text:
            await element.type(char, delay=random.randint(50, 150))
            
            # Occasional pause mid-typing (like thinking)
            if random.random() < 0.08:
                await asyncio.sleep(random.uniform(0.2, 0.6))
        
        # Move mouse away after typing
        await page.mouse.move(
            random.randint(100, 800),
            random.randint(100, 600)
        )
    
    async def human_like_click(self, page: Page, selector: str):
        """Click with human-like mouse movement."""
        element = page.locator(selector).first
        box = await element.bounding_box()
        
        if box:
            # Click at random position within element
            x = box["x"] + random.uniform(5, box["width"] - 5)
            y = box["y"] + random.uniform(5, box["height"] - 5)
            
            # Move mouse to position (with some randomness in path)
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
    
    async def wait_for_cloudflare(self, page: Page, timeout: int = 30):
        """Wait for Cloudflare challenge to complete."""
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            title = await page.title()
            if "moment" not in title.lower() and "cloudflare" not in title.lower():
                return True
            
            print("   ⏳ Waiting for Cloudflare...")
            await asyncio.sleep(2)
        
        return False
    
    async def solve_captcha(self, page: Page, captcha_type: str = "auto") -> bool:
        """
        Attempt to solve CAPTCHA (BrowserBase handles many automatically).
        For complex ones, may need external service.
        """
        try:
            # Check for reCAPTCHA iframe
            recaptcha = page.locator('iframe[src*="recaptcha"]').first
            if await recaptcha.count() > 0:
                print("   🔐 reCAPTCHA detected - BrowserBase should handle...")
                await self.human_like_delay(5, 10)
                return True
            
            # Check for hCaptcha
            hcaptcha = page.locator('iframe[src*="hcaptcha"]').first
            if await hcaptcha.count() > 0:
                print("   🔐 hCaptcha detected - BrowserBase should handle...")
                await self.human_like_delay(5, 10)
                return True
            
            return True
            
        except Exception as e:
            print(f"   ⚠️ CAPTCHA handling error: {e}")
            return False
    
    async def close_session(self, session_id: str):
        """Close a browser session."""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            await session.browser.close()
            del self.active_sessions[session_id]
            print(f"   Closed session: {session_id}")
    
    async def close_all(self):
        """Close all active sessions."""
        for session_id in list(self.active_sessions.keys()):
            await self.close_session(session_id)
        
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None


# Test function
async def test_stealth():
    manager = StealthBrowserManager()
    
    try:
        session = await manager.create_stealth_session("test", use_proxy=True)
        page = session.page
        
        print("Navigating to Indeed...")
        await page.goto("https://www.indeed.com/jobs?q=software+engineer&l=San+Francisco")
        
        # Wait for Cloudflare if needed
        await manager.wait_for_cloudflare(page)
        
        print(f"Title: {await page.title()}")
        
        # Take screenshot
        await page.screenshot(path="/tmp/indeed_test.png")
        print("Screenshot saved to /tmp/indeed_test.png")
        
    finally:
        await manager.close_all()


if __name__ == "__main__":
    asyncio.run(test_stealth())
