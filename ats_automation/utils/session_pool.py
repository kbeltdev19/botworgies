"""
Session Pool Manager for BrowserBase

Manages a pool of reusable BrowserBase sessions to reduce overhead
"""

import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import time


@dataclass
class PooledSession:
    """A session in the pool"""
    session_id: str
    platform: str
    created_at: datetime
    last_used: datetime
    use_count: int = 0
    session_data: Dict[str, Any] = None
    
    @property
    def is_expired(self, max_age_minutes: int = 30) -> bool:
        """Check if session is expired"""
        return datetime.now() - self.created_at > timedelta(minutes=max_age_minutes)
    
    @property
    def is_stale(self, max_idle_minutes: int = 5) -> bool:
        """Check if session has been idle too long"""
        return datetime.now() - self.last_used > timedelta(minutes=max_idle_minutes)


class SessionPool:
    """
    Manages a pool of BrowserBase sessions
    
    Benefits:
    - Reduces session creation overhead
    - Maintains warm connections
    - Handles session lifecycle (creation, reuse, cleanup)
    """
    
    def __init__(
        self,
        browser_manager,
        max_size: int = 50,
        min_size: int = 5,
        max_session_age_minutes: int = 30,
        max_idle_minutes: int = 5
    ):
        self.browser = browser_manager
        self.max_size = max_size
        self.min_size = min_size
        self.max_session_age = max_session_age_minutes
        self.max_idle = max_idle_minutes
        
        # Pool storage
        self._available: asyncio.Queue = asyncio.Queue()
        self._in_use: Dict[str, PooledSession] = {}
        self._all_sessions: Dict[str, PooledSession] = {}
        
        # Stats
        self.stats = {
            'created': 0,
            'reused': 0,
            'expired': 0,
            'errors': 0
        }
        
        self._lock = asyncio.Lock()
        self._maintenance_task = None
    
    async def initialize(self, platform: str = "generic"):
        """Initialize the pool with minimum sessions"""
        print(f"🔄 Initializing session pool with {self.min_size} sessions...")
        
        for i in range(self.min_size):
            try:
                session = await self._create_session(platform)
                if session:
                    await self._available.put(session.session_id)
            except Exception as e:
                print(f"⚠️ Failed to create initial session {i+1}: {e}")
        
        # Start maintenance task
        self._maintenance_task = asyncio.create_task(self._maintenance_loop())
        
        print(f"✅ Session pool initialized: {self._available.qsize()} sessions ready")
    
    async def acquire(self, platform: str = "generic", timeout: float = 30.0) -> Optional[Dict]:
        """
        Acquire a session from the pool
        
        Returns:
            Session data dict or None if timeout
        """
        async with self._lock:
            # Try to get from available
            if not self._available.empty():
                session_id = await asyncio.wait_for(
                    self._available.get(),
                    timeout=timeout
                )
                
                if session_id in self._all_sessions:
                    pooled = self._all_sessions[session_id]
                    
                    # Check if session is still valid
                    if not pooled.is_expired and not pooled.is_stale:
                        pooled.last_used = datetime.now()
                        pooled.use_count += 1
                        self._in_use[session_id] = pooled
                        self.stats['reused'] += 1
                        return pooled.session_data
                    else:
                        # Session expired, remove it
                        await self._destroy_session(session_id)
            
            # Need to create new session if under max size
            if len(self._all_sessions) < self.max_size:
                session = await self._create_session(platform)
                if session:
                    self._in_use[session.session_id] = session
                    return session.session_data
        
        # Wait for a session to become available
        try:
            session_id = await asyncio.wait_for(
                self._available.get(),
                timeout=timeout
            )
            async with self._lock:
                if session_id in self._all_sessions:
                    pooled = self._all_sessions[session_id]
                    pooled.last_used = datetime.now()
                    pooled.use_count += 1
                    self._in_use[session_id] = pooled
                    self.stats['reused'] += 1
                    return pooled.session_data
        except asyncio.TimeoutError:
            print("⚠️ Timeout waiting for available session")
            return None
    
    async def release(self, session_id: str):
        """Return a session to the pool"""
        async with self._lock:
            if session_id in self._in_use:
                pooled = self._in_use.pop(session_id)
                
                # Check if session is still valid
                if pooled.is_expired or pooled.is_stale:
                    await self._destroy_session(session_id)
                else:
                    pooled.last_used = datetime.now()
                    await self._available.put(session_id)
    
    async def _create_session(self, platform: str) -> Optional[PooledSession]:
        """Create a new BrowserBase session"""
        try:
            session_data = await self.browser.create_stealth_session(platform)
            session_id = session_data['session_id']
            
            pooled = PooledSession(
                session_id=session_id,
                platform=platform,
                created_at=datetime.now(),
                last_used=datetime.now(),
                session_data=session_data
            )
            
            self._all_sessions[session_id] = pooled
            self.stats['created'] += 1
            
            return pooled
        except Exception as e:
            print(f"❌ Failed to create session: {e}")
            self.stats['errors'] += 1
            return None
    
    async def _destroy_session(self, session_id: str):
        """Destroy a session"""
        try:
            await self.browser.close_session(session_id)
        except:
            pass
        
        if session_id in self._all_sessions:
            del self._all_sessions[session_id]
        if session_id in self._in_use:
            del self._in_use[session_id]
    
    async def _maintenance_loop(self):
        """Background task to maintain pool health"""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                await self._cleanup_expired()
                await self._ensure_min_size()
            except Exception as e:
                print(f"⚠️ Maintenance error: {e}")
    
    async def _cleanup_expired(self):
        """Remove expired sessions"""
        async with self._lock:
            expired = [
                sid for sid, session in self._all_sessions.items()
                if session.is_expired or session.is_stale
            ]
            
            for sid in expired:
                await self._destroy_session(sid)
                self.stats['expired'] += 1
            
            if expired:
                print(f"🧹 Cleaned up {len(expired)} expired sessions")
    
    async def _ensure_min_size(self):
        """Ensure pool has minimum number of sessions"""
        current_size = len(self._all_sessions)
        if current_size < self.min_size:
            needed = self.min_size - current_size
            print(f"🔄 Adding {needed} sessions to maintain minimum")
            
            for _ in range(needed):
                session = await self._create_session("generic")
                if session:
                    await self._available.put(session.session_id)
    
    async def close_all(self):
        """Close all sessions and cleanup"""
        if self._maintenance_task:
            self._maintenance_task.cancel()
            try:
                await self._maintenance_task
            except asyncio.CancelledError:
                pass
        
        async with self._lock:
            # Close all sessions
            for sid in list(self._all_sessions.keys()):
                await self._destroy_session(sid)
        
        print(f"📊 Pool stats: {self.stats}")
        print("✅ Session pool closed")
    
    def get_stats(self) -> Dict:
        """Get pool statistics"""
        return {
            'available': self._available.qsize(),
            'in_use': len(self._in_use),
            'total': len(self._all_sessions),
            **self.stats
        }
