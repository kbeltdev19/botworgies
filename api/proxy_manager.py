"""
Residential Proxy Manager
Manages rotating residential proxies for anti-detection
"""

import os
import random
import asyncio
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import aiohttp


@dataclass
class ProxyConfig:
    """Proxy configuration."""
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    session_id: Optional[str] = None
    
    def to_url(self) -> str:
        """Convert to proxy URL format."""
        if self.username and self.password:
            return f"http://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"http://{self.host}:{self.port}"
    
    def to_playwright_format(self) -> Dict:
        """Convert to Playwright proxy format."""
        proxy = {
            "server": f"http://{self.host}:{self.port}"
        }
        if self.username:
            proxy["username"] = self.username
        if self.password:
            proxy["password"] = self.password
        return proxy


class ResidentialProxyManager:
    """
    Manages residential proxy rotation for job application automation.
    
    Supports providers:
    - Bright Data (Luminati)
    - Oxylabs
    - Smartproxy
    - IPRoyal
    """
    
    def __init__(self, provider: str = "brightdata"):
        self.provider = provider.lower()
        self.proxies: List[ProxyConfig] = []
        self.current_index = 0
        self.failed_proxies: set = set()
        self.proxy_stats: Dict[str, Dict] = {}
        
        self._load_credentials()
        self._initialize_proxies()
    
    def _load_credentials(self):
        """Load proxy credentials from environment."""
        env_map = {
            "brightdata": {
                "username": os.getenv("BRIGHTDATA_USERNAME"),
                "password": os.getenv("BRIGHTDATA_PASSWORD"),
                "host": os.getenv("BRIGHTDATA_HOST", "brd.superproxy.io"),
                "port": int(os.getenv("BRIGHTDATA_PORT", "22225"))
            },
            "oxylabs": {
                "username": os.getenv("OXYLABS_USERNAME"),
                "password": os.getenv("OXYLABS_PASSWORD"),
                "host": os.getenv("OXYLABS_HOST", "pr.oxylabs.io"),
                "port": int(os.getenv("OXYLABS_PORT", "7777"))
            },
            "smartproxy": {
                "username": os.getenv("SMARTPROXY_USERNAME"),
                "password": os.getenv("SMARTPROXY_PASSWORD"),
                "host": os.getenv("SMARTPROXY_HOST", "gate.smartproxy.com"),
                "port": int(os.getenv("SMARTPROXY_PORT", "7000"))
            },
            "iproyal": {
                "username": os.getenv("IPROYAL_USERNAME"),
                "password": os.getenv("IPROYAL_PASSWORD"),
                "host": os.getenv("IPROYAL_HOST", "geo.iproyal.com"),
                "port": int(os.getenv("IPROYAL_PORT", "12321"))
            }
        }
        
        self.credentials = env_map.get(self.provider, {})
    
    def _initialize_proxies(self):
        """Initialize proxy pool."""
        if not self.credentials.get("username"):
            print(f"⚠️  No credentials found for {self.provider}")
            return
        
        # Create proxy configurations for different countries
        countries = ["us", "gb", "ca", "au", "de"]  # Target countries
        
        for country in countries:
            for i in range(5):  # 5 sessions per country
                session_id = f"session_{country}_{i}_{datetime.now().timestamp()}"
                
                proxy = ProxyConfig(
                    host=self.credentials["host"],
                    port=self.credentials["port"],
                    username=self.credentials["username"],
                    password=self.credentials["password"],
                    country=country,
                    session_id=session_id
                )
                
                self.proxies.append(proxy)
                self.proxy_stats[session_id] = {
                    "uses": 0,
                    "failures": 0,
                    "last_used": None,
                    "country": country
                }
        
        print(f"✅ Initialized {len(self.proxies)} proxies from {self.provider}")
    
    def get_proxy(self, country: Optional[str] = None, for_platform: Optional[str] = None) -> Optional[ProxyConfig]:
        """
        Get next available proxy.
        
        Args:
            country: Preferred country code (e.g., 'us', 'gb')
            for_platform: Platform name for platform-specific rotation
        """
        if not self.proxies:
            return None
        
        # Filter by country if specified
        available = self.proxies
        if country:
            available = [p for p in available if p.country == country]
        
        # Filter out failed proxies
        available = [p for p in available if p.session_id not in self.failed_proxies]
        
        if not available:
            # Reset failed proxies if all failed
            self.failed_proxies.clear()
            available = self.proxies
        
        # Platform-specific logic
        if for_platform == "linkedin":
            # LinkedIn needs US residential proxies
            us_proxies = [p for p in available if p.country == "us"]
            if us_proxies:
                available = us_proxies
        
        # Round-robin selection
        proxy = available[self.current_index % len(available)]
        self.current_index += 1
        
        # Update stats
        if proxy.session_id in self.proxy_stats:
            self.proxy_stats[proxy.session_id]["uses"] += 1
            self.proxy_stats[proxy.session_id]["last_used"] = datetime.now().isoformat()
        
        return proxy
    
    def mark_failed(self, proxy: ProxyConfig, error: str):
        """Mark a proxy as failed."""
        if proxy.session_id:
            self.failed_proxies.add(proxy.session_id)
            if proxy.session_id in self.proxy_stats:
                self.proxy_stats[proxy.session_id]["failures"] += 1
        
        print(f"⚠️  Proxy marked as failed: {proxy.session_id} - {error}")
    
    def get_stats(self) -> Dict:
        """Get proxy usage statistics."""
        total_uses = sum(s["uses"] for s in self.proxy_stats.values())
        total_failures = sum(s["failures"] for s in self.proxy_stats.values())
        
        by_country = {}
        for session_id, stats in self.proxy_stats.items():
            country = stats["country"]
            if country not in by_country:
                by_country[country] = {"uses": 0, "failures": 0}
            by_country[country]["uses"] += stats["uses"]
            by_country[country]["failures"] += stats["failures"]
        
        return {
            "total_proxies": len(self.proxies),
            "failed_proxies": len(self.failed_proxies),
            "total_uses": total_uses,
            "total_failures": total_failures,
            "success_rate": (total_uses - total_failures) / total_uses if total_uses > 0 else 0,
            "by_country": by_country
        }
    
    async def test_proxy(self, proxy: ProxyConfig) -> bool:
        """Test if a proxy is working."""
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    "http://httpbin.org/ip",
                    proxy=proxy.to_url()
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        print(f"✅ Proxy test passed: {data.get('origin', 'unknown')}")
                        return True
                    return False
        except Exception as e:
            print(f"❌ Proxy test failed: {e}")
            return False


class PlatformProxyStrategy:
    """Platform-specific proxy strategies."""
    
    STRATEGIES = {
        "linkedin": {
            "preferred_countries": ["us", "gb", "ca"],
            "rotation_frequency": 5,  # Rotate every N requests
            "sticky_sessions": True,
            "description": "LinkedIn requires high-quality US residential proxies"
        },
        "indeed": {
            "preferred_countries": ["us"],
            "rotation_frequency": 10,
            "sticky_sessions": False,
            "description": "Indeed is less strict, can rotate more frequently"
        },
        "zip_recruiter": {
            "preferred_countries": ["us"],
            "rotation_frequency": 3,
            "sticky_sessions": True,
            "description": "ZipRecruiter blocks aggressively"
        },
        "glassdoor": {
            "preferred_countries": ["us", "gb"],
            "rotation_frequency": 5,
            "sticky_sessions": True,
            "description": "GlassDoor requires careful proxy management"
        }
    }
    
    def __init__(self, proxy_manager: ResidentialProxyManager):
        self.proxy_manager = proxy_manager
        self.request_counts: Dict[str, int] = {}
        self.sticky_sessions: Dict[str, ProxyConfig] = {}
    
    def get_proxy_for_platform(self, platform: str) -> Optional[ProxyConfig]:
        """Get proxy optimized for specific platform."""
        strategy = self.STRATEGIES.get(platform.lower(), {})
        
        # Check if we should use sticky session
        if strategy.get("sticky_sessions"):
            if platform in self.sticky_sessions:
                count = self.request_counts.get(platform, 0)
                if count < strategy.get("rotation_frequency", 5):
                    self.request_counts[platform] = count + 1
                    return self.sticky_sessions[platform]
        
        # Get new proxy
        countries = strategy.get("preferred_countries", ["us"])
        proxy = self.proxy_manager.get_proxy(
            country=random.choice(countries),
            for_platform=platform
        )
        
        # Update sticky session
        if strategy.get("sticky_sessions"):
            self.sticky_sessions[platform] = proxy
            self.request_counts[platform] = 1
        
        return proxy


# Convenience function for getting LinkedIn proxy
def get_linkedin_proxy() -> Optional[ProxyConfig]:
    """Get optimized proxy for LinkedIn."""
    manager = ResidentialProxyManager()
    strategy = PlatformProxyStrategy(manager)
    return strategy.get_proxy_for_platform("linkedin")


if __name__ == "__main__":
    # Test
    manager = ResidentialProxyManager()
    print(f"Proxy stats: {manager.get_stats()}")
    
    proxy = manager.get_proxy()
    if proxy:
        print(f"Got proxy: {proxy.country} - {proxy.session_id}")
