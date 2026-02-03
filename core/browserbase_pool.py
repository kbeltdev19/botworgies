"""
BrowserBase Pool with Local Browser Fallback

100 concurrent cloud browser sessions with automatic fallback to local browsers.

Features:
- Primary: BrowserBase cloud with stealth mode + proxies
- Fallback: Local Playwright browsers when BrowserBase is at capacity
- Seamless failover with consistent interface
- Automatic retry with cooldown for BrowserBase recovery

Docs:
- https://docs.browserbase.com/features/stealth-mode
- https://docs.browserbase.com/features/proxies
"""

import asyncio
import os
import random
import logging
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# BrowserBase SDK
try:
    from browserbase import Browserbase
    BROWSERBASE_SDK_AVAILABLE = True
except ImportError:
    BROWSERBASE_SDK_AVAILABLE = False

logger = logging.getLogger(__name__)


class BrowserMode(Enum):
    """Browser session mode."""
    BROWSERBASE = "browserbase"
    LOCAL = "local"


@dataclass
class BrowserSession:
    """A browser session (BrowserBase or local)."""
    session_id: str
    browser: Browser
    context: BrowserContext
    page: Page
    mode: BrowserMode
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)
    request_count: int = 0
    in_use: bool = False


# Error indicators for BrowserBase capacity issues
BROWSERBASE_CAPACITY_ERRORS = [
    "rate limit", "too many requests", "capacity exceeded",
    "quota exceeded", "concurrent sessions limit", "429", "503",
    "resource exhausted", "payment required", "limit exceeded",
]


def is_capacity_error(error_msg: str) -> bool:
    """Check if error is a BrowserBase capacity/rate limit error."""
    error_lower = str(error_msg).lower()
    return any(indicator in error_lower for indicator in BROWSERBASE_CAPACITY_ERRORS)


# Stealth JavaScript patches for local browsers
STEALTH_SCRIPT = """
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

# User agents for local browsers
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1680, "height": 1050},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
]


class BrowserBasePool:
    """
    Pool of browser sessions with BrowserBase primary and local fallback.
    
    Usage:
        pool = BrowserBasePool(max_browserbase=100, max_local=20)
        await pool.initialize()
        
        session = await pool.acquire()
        # Use session.page for automation
        await pool.release(session)
        
        await pool.shutdown()
    """
    
    def __init__(
        self,
        max_browserbase: int = 100,
        max_local: int = 20,
        api_key: str = None,
        project_id: str = None,
        session_timeout: int = 300,
        max_requests_per_session: int = 50,
        prefer_local: bool = False,
        browserbase_cooldown_minutes: int = 5,
    ):
        self.max_browserbase = max_browserbase
        self.max_local = max_local
        self.api_key = api_key or os.environ.get("BROWSERBASE_API_KEY")
        self.project_id = project_id or os.environ.get("BROWSERBASE_PROJECT_ID")
        self.session_timeout = session_timeout
        self.max_requests_per_session = max_requests_per_session
        self.prefer_local = prefer_local
        self.browserbase_cooldown_minutes = browserbase_cooldown_minutes
        
        self._sessions: Dict[str, BrowserSession] = {}
        self._available: asyncio.Queue = asyncio.Queue()
        self._lock = asyncio.Lock()
        self._playwright = None
        self._initialized = False
        
        # BrowserBase state
        self._browserbase_available = (
            self.api_key is not None and 
            self.project_id is not None and 
            BROWSERBASE_SDK_AVAILABLE
        )
        self._browserbase_failed_at: Optional[datetime] = None
        self._bb = Browserbase(api_key=self.api_key) if self._browserbase_available else None
        
        # Session counters
        self._browserbase_count = 0
        self._local_count = 0
        
        # Stats
        self._stats = {
            "browserbase_created": 0,
            "local_created": 0,
            "sessions_recycled": 0,
            "total_requests": 0,
            "fallbacks_to_local": 0,
        }
    
    @property
    def browserbase_enabled(self) -> bool:
        """Check if BrowserBase is currently enabled."""
        if not self._browserbase_available:
            return False
        if self._browserbase_failed_at:
            # Check if cooldown has expired
            cooldown = timedelta(minutes=self.browserbase_cooldown_minutes)
            if datetime.now() - self._browserbase_failed_at > cooldown:
                logger.info("BrowserBase cooldown expired, retrying...")
                self._browserbase_failed_at = None
                return True
            return False
        return True
    
    async def initialize(self, initial_sessions: int = 5):
        """Initialize the pool with some sessions."""
        if self._initialized:
            return
        
        self._playwright = await async_playwright().start()
        
        # Create initial sessions
        logger.info(f"Initializing browser pool with {initial_sessions} sessions...")
        
        for _ in range(initial_sessions):
            asyncio.create_task(self._create_session_async())
        
        # Wait a bit for initial sessions
        await asyncio.sleep(2)
        
        self._initialized = True
        logger.info(f"Browser pool initialized: {len(self._sessions)} sessions ready")
    
    async def _create_session_async(self):
        """Async wrapper to create session."""
        session = await self._create_session()
        if session:
            await self._available.put(session.session_id)
    
    async def _create_session(self) -> Optional[BrowserSession]:
        """Create a new browser session (BrowserBase or local)."""
        # Try BrowserBase first (unless disabled)
        if not self.prefer_local and self.browserbase_enabled and self._browserbase_count < self.max_browserbase:
            try:
                session = await self._create_browserbase_session()
                if session:
                    return session
            except Exception as e:
                if is_capacity_error(str(e)):
                    logger.warning(f"BrowserBase at capacity: {e}")
                    self._browserbase_failed_at = datetime.now()
                    self._stats["fallbacks_to_local"] += 1
                else:
                    logger.error(f"BrowserBase error: {e}")
        
        # Fallback to local browser
        if self._local_count < self.max_local:
            return await self._create_local_session()
        
        logger.error("All browser resources exhausted (BrowserBase + Local)")
        return None
    
    async def _create_browserbase_session(self) -> Optional[BrowserSession]:
        """Create a BrowserBase cloud session with stealth + proxies."""
        try:
            bb_session = self._bb.sessions.create(
                project_id=self.project_id,
                proxies=True,
                browser_settings={
                    "advancedStealth": True,
                    "solveCaptchas": True,
                },
            )
            
            # Connect via Playwright CDP
            browser = await self._playwright.chromium.connect_over_cdp(
                bb_session.connect_url,
                timeout=60000
            )
            
            context = await browser.new_context()
            page = await context.new_page()
            
            session = BrowserSession(
                session_id=bb_session.id,
                browser=browser,
                context=context,
                page=page,
                mode=BrowserMode.BROWSERBASE,
            )
            
            async with self._lock:
                self._sessions[bb_session.id] = session
                self._browserbase_count += 1
                self._stats["browserbase_created"] += 1
            
            logger.debug(f"Created BrowserBase session: {bb_session.id}")
            return session
            
        except Exception as e:
            logger.error(f"Failed to create BrowserBase session: {e}")
            raise
    
    async def _create_local_session(self) -> Optional[BrowserSession]:
        """Create a local browser session with stealth patches."""
        try:
            viewport = random.choice(VIEWPORTS)
            user_agent = random.choice(USER_AGENTS)
            
            launch_args = [
                f"--window-size={viewport['width']},{viewport['height']}",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
            ]
            
            browser = await self._playwright.chromium.launch(
                headless=True,
                args=launch_args
            )
            
            context = await browser.new_context(
                viewport=viewport,
                user_agent=user_agent,
                locale="en-US",
                timezone_id="America/New_York",
            )
            
            await context.add_init_script(STEALTH_SCRIPT)
            
            page = await context.new_page()
            session_id = f"local_{datetime.now().strftime('%H%M%S')}_{random.randint(1000, 9999)}"
            
            session = BrowserSession(
                session_id=session_id,
                browser=browser,
                context=context,
                page=page,
                mode=BrowserMode.LOCAL,
            )
            
            async with self._lock:
                self._sessions[session_id] = session
                self._local_count += 1
                self._stats["local_created"] += 1
            
            logger.debug(f"Created local browser session: {session_id}")
            return session
            
        except Exception as e:
            logger.error(f"Failed to create local browser session: {e}")
            return None
    
    async def acquire(self, timeout: float = 30.0) -> BrowserSession:
        """
        Acquire a browser session from the pool.
        
        Returns a session or raises TimeoutError.
        """
        start = datetime.now()
        
        while True:
            # Check for available session
            try:
                session_id = await asyncio.wait_for(
                    self._available.get(),
                    timeout=5.0
                )
                
                session = self._sessions.get(session_id)
                
                if session and not session.in_use:
                    # Check if session needs recycling
                    if session.request_count >= self.max_requests_per_session:
                        await self._recycle_session(session)
                        continue
                    
                    session.in_use = True
                    session.last_used = datetime.now()
                    session.request_count += 1
                    self._stats["total_requests"] += 1
                    
                    logger.debug(f"Acquired session: {session_id} ({session.mode.value})")
                    return session
                    
            except asyncio.TimeoutError:
                pass
            
            # Check total timeout
            elapsed = (datetime.now() - start).total_seconds()
            if elapsed > timeout:
                # Try to create new session
                session = await self._create_session()
                if session:
                    session.in_use = True
                    return session
                
                raise TimeoutError("No browser sessions available")
            
            # Create more sessions if needed and under limits
            total_sessions = self._browserbase_count + self._local_count
            max_total = self.max_browserbase + self.max_local
            
            if total_sessions < max_total and self._available.empty():
                asyncio.create_task(self._create_session_async())
    
    async def release(self, session: BrowserSession):
        """Release a session back to the pool."""
        session.in_use = False
        session.last_used = datetime.now()
        await self._available.put(session.session_id)
        logger.debug(f"Released session: {session.session_id}")
    
    async def _recycle_session(self, session: BrowserSession):
        """Recycle a session (close and create new)."""
        try:
            await session.context.close()
            await session.browser.close()
            
            async with self._lock:
                del self._sessions[session.session_id]
                if session.mode == BrowserMode.BROWSERBASE:
                    self._browserbase_count -= 1
                else:
                    self._local_count -= 1
            
            # Create replacement session
            new_session = await self._create_session()
            if new_session:
                await self._available.put(new_session.session_id)
                self._stats["sessions_recycled"] += 1
                
        except Exception as e:
            logger.error(f"Error recycling session: {e}")
    
    async def shutdown(self):
        """Shutdown all sessions."""
        logger.info("Shutting down browser pool...")
        
        for session in list(self._sessions.values()):
            try:
                await session.context.close()
                await session.browser.close()
            except:
                pass
        
        self._sessions.clear()
        self._browserbase_count = 0
        self._local_count = 0
        
        if self._playwright:
            await self._playwright.stop()
        
        self._initialized = False
        logger.info("Browser pool shutdown complete")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        browserbase_in_use = sum(1 for s in self._sessions.values() if s.mode == BrowserMode.BROWSERBASE and s.in_use)
        local_in_use = sum(1 for s in self._sessions.values() if s.mode == BrowserMode.LOCAL and s.in_use)
        
        return {
            **self._stats,
            "active_sessions": len(self._sessions),
            "available_sessions": self._available.qsize(),
            "browserbase_count": self._browserbase_count,
            "browserbase_available": self.browserbase_enabled,
            "local_count": self._local_count,
            "browserbase_in_use": browserbase_in_use,
            "local_in_use": local_in_use,
            "max_browserbase": self.max_browserbase,
            "max_local": self.max_local,
        }
    
    async def scale_up(self, count: int = 10):
        """Add more sessions to the pool."""
        logger.info(f"Scaling up: creating {count} new sessions")
        tasks = [self._create_session_async() for _ in range(count)]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    def force_local_mode(self, duration_minutes: int = 30):
        """Force local browser mode for a duration."""
        logger.warning(f"Forcing local browser mode for {duration_minutes} minutes")
        self._browserbase_failed_at = datetime.now()


# Convenience function
async def create_browser_pool(
    max_browserbase: int = 100,
    max_local: int = 20,
    prefer_local: bool = False
) -> BrowserBasePool:
    """Create and initialize a browser pool."""
    pool = BrowserBasePool(
        max_browserbase=max_browserbase,
        max_local=max_local,
        prefer_local=prefer_local
    )
    await pool.initialize(initial_sessions=min(5, max_local + max_browserbase))
    return pool


# Backwards compatibility alias
BrowserBasePool = BrowserBasePool


# Example usage
if __name__ == "__main__":
    async def test():
        # Test with fallback
        pool = await create_browser_pool(max_browserbase=10, max_local=5)
        
        print(f"Pool stats: {pool.get_stats()}")
        
        # Acquire multiple sessions
        sessions = []
        for i in range(5):
            try:
                session = await pool.acquire(timeout=10)
                sessions.append(session)
                print(f"Acquired: {session.session_id} ({session.mode.value})")
                
                # Use page
                await session.page.goto("https://example.com")
                print(f"  Title: {await session.page.title()}")
            except TimeoutError:
                print(f"Failed to acquire session {i}")
        
        # Release sessions
        for session in sessions:
            await pool.release(session)
        
        print(f"\nFinal stats: {pool.get_stats()}")
        
        # Shutdown
        await pool.shutdown()
    
    asyncio.run(test())
