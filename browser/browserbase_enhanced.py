"""
Enhanced BrowserBase Integration with Better Error Handling

Provides detailed diagnostics and fallback mechanisms for BrowserBase.
"""

import os
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

from browserbase import Browserbase

logger = logging.getLogger(__name__)


@dataclass
class BrowserBaseDiagnostics:
    """Diagnostics for BrowserBase connection issues."""
    api_key_configured: bool
    project_id_configured: bool
    sdk_available: bool
    can_connect: bool
    plan_type: Optional[str]
    features_available: list
    error_message: Optional[str]


class BrowserBaseEnhanced:
    """
    Enhanced BrowserBase client with diagnostics and better error handling.
    """
    
    def __init__(self, api_key: Optional[str] = None, project_id: Optional[str] = None):
        self.api_key = api_key or os.getenv("BROWSERBASE_API_KEY")
        self.project_id = project_id or os.getenv("BROWSERBASE_PROJECT_ID")
        self.client = None
        
        if self.api_key:
            try:
                self.client = Browserbase(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize BrowserBase: {e}")
    
    async def diagnose(self) -> BrowserBaseDiagnostics:
        """Run diagnostics on BrowserBase configuration."""
        diagnostics = BrowserBaseDiagnostics(
            api_key_configured=bool(self.api_key),
            project_id_configured=bool(self.project_id),
            sdk_available=self._check_sdk(),
            can_connect=False,
            plan_type=None,
            features_available=[],
            error_message=None
        )
        
        if not diagnostics.api_key_configured:
            diagnostics.error_message = "BROWSERBASE_API_KEY not set"
            return diagnostics
        
        if not diagnostics.sdk_available:
            diagnostics.error_message = "BrowserBase SDK not installed"
            return diagnostics
        
        # Try to connect and get account info
        try:
            # Try creating a minimal session to test connectivity
            test_session = self.client.sessions.create(
                project_id=self.project_id,
                proxies=True
            )
            
            diagnostics.can_connect = True
            diagnostics.features_available.append("basic_sessions")
            
            # Clean up test session
            self.client.sessions.delete(test_session.id)
            
            # Try advanced features
            try:
                adv_session = self.client.sessions.create(
                    project_id=self.project_id,
                    proxies=True,
                    browser_settings={"advancedStealth": True}
                )
                diagnostics.features_available.append("advanced_stealth")
                self.client.sessions.delete(adv_session.id)
            except Exception as e:
                if "plan" in str(e).lower() or "enterprise" in str(e).lower():
                    diagnostics.plan_type = "basic"
                logger.debug(f"Advanced Stealth not available: {e}")
            
            if not diagnostics.plan_type:
                diagnostics.plan_type = "enterprise"
                
        except Exception as e:
            diagnostics.error_message = str(e)
            logger.error(f"BrowserBase connection failed: {e}")
        
        return diagnostics
    
    def _check_sdk(self) -> bool:
        """Check if BrowserBase SDK is available."""
        try:
            from browserbase import Browserbase
            return True
        except ImportError:
            return False
    
    async def create_session(self, platform: str, use_proxy: bool = True, 
                            advanced_stealth: bool = False) -> Any:
        """
        Create a BrowserBase session with proper error handling.
        
        Args:
            platform: Platform identifier
            use_proxy: Use residential proxy
            advanced_stealth: Try to use advanced stealth features
            
        Returns:
            BrowserBase session object
            
        Raises:
            Exception: If session creation fails with details
        """
        if not self.client:
            raise Exception("BrowserBase client not initialized")
        
        if not self.project_id:
            raise Exception("BROWSERBASE_PROJECT_ID not set")
        
        # Build session configuration
        config = {
            "project_id": self.project_id,
            "proxies": use_proxy,
        }
        
        # Try with advanced stealth first if requested
        if advanced_stealth:
            try:
                config["browser_settings"] = {
                    "advancedStealth": True,
                    "solveCaptchas": True,
                }
                session = self.client.sessions.create(**config)
                logger.info(f"✅ BrowserBase Advanced Stealth session: {session.id}")
                return session
            except Exception as e:
                error_msg = str(e).lower()
                if any(keyword in error_msg for keyword in ["enterprise", "scale", "plan", "upgrade"]):
                    logger.info("⚠️  Advanced Stealth requires Enterprise plan, using Basic")
                else:
                    raise
        
        # Try basic stealth
        try:
            config["browser_settings"] = {
                "solveCaptchas": True,
            }
            session = self.client.sessions.create(**config)
            logger.info(f"✅ BrowserBase Basic Stealth session: {session.id}")
            return session
        except Exception as e:
            logger.error(f"❌ BrowserBase session creation failed: {e}")
            
            # Provide helpful error message
            error_msg = str(e)
            if "400" in error_msg:
                raise Exception(
                    f"BrowserBase 400 error. Common causes:\n"
                    f"  1. Invalid project ID: {self.project_id}\n"
                    f"  2. Project not active\n"
                    f"  3. Rate limits exceeded\n"
                    f"  4. Account restrictions\n"
                    f"\nOriginal error: {error_msg}"
                )
            raise
    
    def print_diagnostics(self, diagnostics: BrowserBaseDiagnostics):
        """Print diagnostic report."""
        print("\n" + "=" * 60)
        print("BROWSERBASE DIAGNOSTICS")
        print("=" * 60)
        
        status = "✅" if diagnostics.can_connect else "❌"
        
        print(f"\n{status} Connection Status")
        print(f"  API Key: {'✅ Configured' if diagnostics.api_key_configured else '❌ Missing'}")
        print(f"  Project ID: {'✅ Configured' if diagnostics.project_id_configured else '❌ Missing'}")
        print(f"  SDK: {'✅ Available' if diagnostics.sdk_available else '❌ Not installed'}")
        print(f"  Connection: {'✅ Working' if diagnostics.can_connect else '❌ Failed'}")
        
        if diagnostics.plan_type:
            print(f"\n  Plan Type: {diagnostics.plan_type.upper()}")
        
        if diagnostics.features_available:
            print(f"\n  Features:")
            for feature in diagnostics.features_available:
                print(f"    ✅ {feature}")
        
        if diagnostics.error_message:
            print(f"\n  Error: {diagnostics.error_message}")
        
        print("\n" + "=" * 60)


# Singleton instance
_bb_enhanced = None

def get_browserbase_client() -> BrowserBaseEnhanced:
    """Get or create singleton BrowserBase client."""
    global _bb_enhanced
    if _bb_enhanced is None:
        _bb_enhanced = BrowserBaseEnhanced()
    return _bb_enhanced


# Test function
async def test_browserbase():
    """Test BrowserBase connection."""
    bb = get_browserbase_client()
    
    print("Running BrowserBase diagnostics...\n")
    diagnostics = await bb.diagnose()
    bb.print_diagnostics(diagnostics)
    
    if diagnostics.can_connect:
        print("\nTrying to create test session...")
        try:
            session = await bb.create_session("test", use_proxy=True)
            print(f"✅ Session created: {session.id}")
            
            # Clean up
            bb.client.sessions.delete(session.id)
            print("✅ Session cleaned up")
        except Exception as e:
            print(f"❌ Failed: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_browserbase())
