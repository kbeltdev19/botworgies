"""
BrowserBase Manager for ATS Automation
Handles stealth sessions, proxies, and captcha solving
"""

import os
import asyncio
import random
from typing import Optional, Dict, Any
from browserbase import Browserbase


class BrowserBaseManager:
    """Manages BrowserBase sessions for ATS automation"""
    
    def __init__(self):
        self.api_key = os.getenv("BROWSERBASE_API_KEY")
        self.project_id = os.getenv("BROWSERBASE_PROJECT_ID")
        
        if not self.api_key or not self.project_id:
            raise ValueError("BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID required")
        
        self.bb = Browserbase(api_key=self.api_key)
        self.active_sessions: Dict[str, Dict] = {}
    
    async def create_stealth_session(
        self, 
        platform: str = "generic",
        use_proxy: bool = True
    ) -> Dict[str, Any]:
        """
        Create optimized BrowserBase session for specific ATS platform
        
        Args:
            platform: 'workday', 'taleo', 'icims', 'successfactors', 'adp', 'dice', 'generic'
            use_proxy: Whether to use residential proxy
        """
        try:
            # Create BrowserBase session
            session = self.bb.sessions.create(
                project_id=self.project_id
            )
            
            # Import playwright here to avoid issues if not installed
            from playwright.async_api import async_playwright
            
            playwright = await async_playwright().start()
            browser = await playwright.chromium.connect_over_cdp(session.connect_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()
            
            # Inject additional stealth scripts
            await page.add_init_script("""
                // Hide webdriver
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Fake plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {name: 'Chrome PDF Plugin'},
                        {name: 'Chrome PDF Viewer'},
                        {name: 'Native Client'}
                    ]
                });
                
                // Fake chrome object
                window.chrome = window.chrome || {};
                window.chrome.runtime = window.chrome.runtime || {};
                
                // Override permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({state: Notification.permission}) :
                        originalQuery(parameters)
                );
            """)
            
            session_data = {
                "browser": browser,
                "context": context,
                "page": page,
                "session_id": session.id,
                "platform": platform,
                "playwright": playwright,
                "connect_url": session.connect_url
            }
            
            self.active_sessions[session.id] = session_data
            
            return session_data
            
        except Exception as e:
            print(f"Error creating BrowserBase session: {e}")
            raise
    
    async def solve_captcha_if_present(
        self, 
        session_id: str, 
        page,
        timeout: int = 10
    ) -> bool:
        """
        Check for and handle CAPTCHA using BrowserBase's built-in solving
        
        Returns True if no CAPTCHA or CAPTCHA solved successfully
        """
        captcha_selectors = [
            '.g-recaptcha',
            '[data-sitekey]',
            '.h-captcha',
            'iframe[src*="recaptcha"]',
            'iframe[src*="captcha"]',
            '.cf-turnstile',
            '#challenge-running'
        ]
        
        try:
            for selector in captcha_selectors:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    print(f"CAPTCHA detected ({selector}), waiting for BrowserBase solving...")
                    
                    # BrowserBase handles CAPTCHA automatically in most cases
                    # Just wait longer for it to be solved
                    for _ in range(timeout):
                        await asyncio.sleep(1)
                        still_there = await page.query_selector(selector)
                        if not still_there or not await still_there.is_visible():
                            print("CAPTCHA solved!")
                            return True
                    
                    print("CAPTCHA still present after timeout")
                    return False
            
            return True  # No CAPTCHA found
            
        except Exception as e:
            print(f"CAPTCHA detection error: {e}")
            return True  # Assume OK on error
    
    async def get_session(self, session_id: str) -> Optional[Dict]:
        """Get active session by ID"""
        return self.active_sessions.get(session_id)
    
    async def close_session(self, session_id: str):
        """Clean up BrowserBase session"""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            try:
                # Close browser
                if "browser" in session:
                    await session["browser"].close()
                
                # Close playwright
                if "playwright" in session:
                    await session["playwright"].stop()
                
                # Delete BrowserBase session (API may not support this, ignore errors)
                try:
                    pass  # BrowserBase sessions auto-expire
                except:
                    pass
                
            except Exception as e:
                print(f"Error closing session {session_id}: {e}")
            finally:
                del self.active_sessions[session_id]
    
    async def close_all_sessions(self):
        """Close all active sessions"""
        session_ids = list(self.active_sessions.keys())
        for session_id in session_ids:
            await self.close_session(session_id)
    
    def get_active_session_count(self) -> int:
        """Get number of active sessions"""
        return len(self.active_sessions)
    
    async def take_screenshot(self, session_id: str, path: Optional[str] = None) -> str:
        """Take screenshot of session"""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        if not path:
            import time
            path = f"screenshots/ats_{session_id}_{int(time.time())}.png"
        
        await session["page"].screenshot(path=path)
        return path
