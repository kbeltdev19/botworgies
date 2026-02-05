"""
Proxy configuration for local browser sessions.
Add your proxy provider credentials here.
"""

import os
from typing import Optional, Dict, Any

# Proxy provider settings
PROXY_PROVIDERS = {
    "brightdata": {
        "host": os.getenv("BRIGHTDATA_HOST", "brd.superproxy.io"),
        "port": os.getenv("BRIGHTDATA_PORT", "22225"),
        "username": os.getenv("BRIGHTDATA_USER", ""),
        "password": os.getenv("BRIGHTDATA_PASS", ""),
    },
    "oxylabs": {
        "host": os.getenv("OXYLABS_HOST", "pr.oxylabs.io"),
        "port": os.getenv("OXYLABS_PORT", "7777"),
        "username": os.getenv("OXYLABS_USER", ""),
        "password": os.getenv("OXYLABS_PASS", ""),
    },
    "smartproxy": {
        "host": os.getenv("SMARTPROXY_HOST", "gate.smartproxy.com"),
        "port": os.getenv("SMARTPROXY_PORT", "7000"),
        "username": os.getenv("SMARTPROXY_USER", ""),
        "password": os.getenv("SMARTPROXY_PASS", ""),
    },
}

def get_proxy_url(provider: str = "brightdata") -> Optional[str]:
    """Get proxy URL for specified provider."""
    config = PROXY_PROVIDERS.get(provider)
    if not config or not config["username"]:
        return None
    
    return f"http://{config['username']}:{config['password']}@{config['host']}:{config['port']}"

def get_proxy_for_local_browser() -> Optional[Dict[str, str]]:
    """Get proxy configuration for local Playwright browser."""
    proxy_url = get_proxy_url("brightdata") or get_proxy_url("oxylabs") or get_proxy_url("smartproxy")
    
    if not proxy_url:
        return None
    
    # Parse proxy URL
    from urllib.parse import urlparse
    parsed = urlparse(proxy_url)
    
    return {
        "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
        "username": parsed.username,
        "password": parsed.password,
    }
