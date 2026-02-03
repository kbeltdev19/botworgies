"""
BrowserBase Pool - 100 concurrent cloud browser sessions.

Uses BrowserBase's cloud infrastructure for massive parallelization.
No local resource constraints - all browsers run in the cloud.
"""

import asyncio
import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, field
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)

# BrowserBase connection URL format
BROWSERBASE_WS_URL = "wss://connect.browserbase.com?apiKey={api_key}&projectId={project_id}"


@dataclass
class BrowserSession:
    """A BrowserBase session."""
    session_id: str
    browser: Browser
    context: BrowserContext
    page: Page
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)
    request_count: int = 0
    in_use: bool = False


class BrowserBasePool:
    """
    Pool of 100 concurrent BrowserBase cloud sessions.
    
    Usage:
        pool = BrowserBasePool(max_sessions=100)
        await pool.initialize()
        
        session = await pool.acquire()
        # Use session.page for automation
        await pool.release(session)
        
        await pool.shutdown()
    """
    
    def __init__(
        self,
        max_sessions: int = 100,
        api_key: str = None,
        project_id: str = None,
        session_timeout: int = 300,  # 5 minutes
        max_requests_per_session: int = 50,  # Rotate after 50 requests
    ):
        self.max_sessions = max_sessions
        self.api_key = api_key or os.environ.get("BROWSERBASE_API_KEY")
        self.project_id = project_id or os.environ.get("BROWSERBASE_PROJECT_ID")
        self.session_timeout = session_timeout
        self.max_requests_per_session = max_requests_per_session
        
        self._sessions: Dict[str, BrowserSession] = {}
        self._available: asyncio.Queue = asyncio.Queue()
        self._lock = asyncio.Lock()
        self._playwright = None
        self._initialized = False
        
        # Stats
        self._stats = {
            "sessions_created": 0,
            "sessions_recycled": 0,
            "total_requests": 0,
        }
    
    @property
    def ws_url(self) -> str:
        """Get BrowserBase WebSocket URL."""
        return BROWSERBASE_WS_URL.format(
            api_key=self.api_key,
            project_id=self.project_id
        )
    
    async def initialize(self, initial_sessions: int = 10):
        """Initialize the pool with some sessions."""
        if self._initialized:
            return
        
        if not self.api_key or not self.project_id:
            raise ValueError("BrowserBase API key and project ID required")
        
        self._playwright = await async_playwright().start()
        
        # Create initial sessions
        logger.info(f"Initializing BrowserBase pool with {initial_sessions} sessions...")
        
        tasks = [self._create_session() for _ in range(initial_sessions)]
        sessions = await asyncio.gather(*tasks, return_exceptions=True)
        
        for session in sessions:
            if isinstance(session, BrowserSession):
                await self._available.put(session.session_id)
        
        self._initialized = True
        logger.info(f"BrowserBase pool initialized: {len(self._sessions)} sessions ready")
    
    async def _create_session(self) -> Optional[BrowserSession]:
        """Create a new BrowserBase session."""
        try:
            # Connect to BrowserBase
            browser = await self._playwright.chromium.connect_over_cdp(self.ws_url)
            
            # Create context with stealth settings
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="America/New_York",
            )
            
            # Create page
            page = await context.new_page()
            
            # Generate session ID
            session_id = f"bb_{datetime.now().strftime('%H%M%S')}_{len(self._sessions)}"
            
            session = BrowserSession(
                session_id=session_id,
                browser=browser,
                context=context,
                page=page,
            )
            
            async with self._lock:
                self._sessions[session_id] = session
                self._stats["sessions_created"] += 1
            
            logger.debug(f"Created BrowserBase session: {session_id}")
            return session
            
        except Exception as e:
            logger.error(f"Failed to create BrowserBase session: {e}")
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
                    
                    return session
                    
            except asyncio.TimeoutError:
                pass
            
            # Check total timeout
            if (datetime.now() - start).total_seconds() > timeout:
                # Try to create new session if under limit
                if len(self._sessions) < self.max_sessions:
                    session = await self._create_session()
                    if session:
                        session.in_use = True
                        return session
                
                raise TimeoutError("No browser sessions available")
            
            # Create more sessions if needed
            if len(self._sessions) < self.max_sessions and self._available.empty():
                asyncio.create_task(self._create_session())
    
    async def release(self, session: BrowserSession):
        """Release a session back to the pool."""
        session.in_use = False
        session.last_used = datetime.now()
        
        # Return to available queue
        await self._available.put(session.session_id)
        
        logger.debug(f"Released session: {session.session_id}")
    
    async def _recycle_session(self, session: BrowserSession):
        """Recycle a session (close and create new)."""
        try:
            # Close old session
            await session.context.close()
            await session.browser.close()
            
            async with self._lock:
                del self._sessions[session.session_id]
            
            # Create new session
            new_session = await self._create_session()
            if new_session:
                await self._available.put(new_session.session_id)
                self._stats["sessions_recycled"] += 1
                
        except Exception as e:
            logger.error(f"Error recycling session: {e}")
    
    async def shutdown(self):
        """Shutdown all sessions."""
        logger.info("Shutting down BrowserBase pool...")
        
        for session in list(self._sessions.values()):
            try:
                await session.context.close()
                await session.browser.close()
            except:
                pass
        
        self._sessions.clear()
        
        if self._playwright:
            await self._playwright.stop()
        
        self._initialized = False
        logger.info("BrowserBase pool shutdown complete")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            **self._stats,
            "active_sessions": len(self._sessions),
            "available_sessions": self._available.qsize(),
            "in_use_sessions": sum(1 for s in self._sessions.values() if s.in_use),
            "max_sessions": self.max_sessions,
        }
    
    async def scale_up(self, count: int = 10):
        """Add more sessions to the pool."""
        target = min(len(self._sessions) + count, self.max_sessions)
        to_create = target - len(self._sessions)
        
        if to_create > 0:
            logger.info(f"Scaling up: creating {to_create} new sessions")
            tasks = [self._create_session() for _ in range(to_create)]
            sessions = await asyncio.gather(*tasks, return_exceptions=True)
            
            for session in sessions:
                if isinstance(session, BrowserSession):
                    await self._available.put(session.session_id)


# Convenience function
async def create_browserbase_pool(max_sessions: int = 100) -> BrowserBasePool:
    """Create and initialize a BrowserBase pool."""
    pool = BrowserBasePool(max_sessions=max_sessions)
    await pool.initialize(initial_sessions=min(10, max_sessions))
    return pool


# Example usage
if __name__ == "__main__":
    async def test():
        pool = await create_browserbase_pool(max_sessions=100)
        
        print(f"Pool stats: {pool.get_stats()}")
        
        # Acquire session
        session = await pool.acquire()
        print(f"Acquired: {session.session_id}")
        
        # Use page
        await session.page.goto("https://example.com")
        print(f"Title: {await session.page.title()}")
        
        # Release
        await pool.release(session)
        
        # Shutdown
        await pool.shutdown()
    
    asyncio.run(test())
