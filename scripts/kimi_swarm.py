#!/usr/bin/env python3
"""
Kimi Swarm - Parallel code generation using Moonshot API.
Generates all job applier improvements simultaneously.
"""

import asyncio
import aiohttp
import os
import json
from pathlib import Path

MOONSHOT_API_KEY = os.environ.get("MOONSHOT_API_KEY")
MOONSHOT_URL = "https://api.moonshot.ai/v1/chat/completions"

TASKS = {
    "browser_pool": {
        "file": "core/browser_pool.py",
        "prompt": """Create a Python file for BrowserPool class managing concurrent Playwright browsers.

Requirements:
- Manage 10-20 concurrent browser instances
- acquire() - get available browser, wait if none free
- release(browser) - return browser to pool
- Health checking every 60 seconds
- Auto-restart crashed browsers
- Memory limit 500MB per browser
- Graceful shutdown with cleanup
- Use asyncio.Semaphore for concurrency

Include complete implementation with docstrings and usage example at bottom.
Output ONLY the Python code, no explanations."""
    },
    "job_discovery": {
        "file": "core/job_discovery.py",
        "prompt": """Create a Python file for JobDiscoveryService for continuous job scraping.

Requirements:
- Runs as background asyncio task
- Scrapes LinkedIn public, Greenhouse API, HN Jobs
- Configurable interval (default 30 min)
- Deduplicates using SQLite database
- JobQueue class for pending jobs
- Tracks job freshness, removes stale (>7 days)
- Event callbacks for new jobs found
- Graceful start/stop

Include complete implementation with docstrings.
Output ONLY the Python code, no explanations."""
    },
    "captcha_solver": {
        "file": "core/captcha_solver.py",
        "prompt": """Create a Python file for CaptchaSolver with 2Captcha and Anti-Captcha support.

Requirements:
- detect_captcha(page) - check if CAPTCHA present on Playwright page
- solve_recaptcha_v2(sitekey, page_url) -> token
- solve_hcaptcha(sitekey, page_url) -> token  
- solve_image_captcha(base64_image) -> text
- Support both 2Captcha and Anti-Captcha APIs
- Fallback to second provider on failure
- Rate limiting (max 10 concurrent solves)
- Cost tracking per solve
- Async implementation

Environment vars: TWOCAPTCHA_API_KEY, ANTICAPTCHA_API_KEY
Include complete implementation with docstrings.
Output ONLY the Python code, no explanations."""
    },
    "proxy_manager": {
        "file": "core/proxy_manager.py",
        "prompt": """Create a Python file for ProxyManager handling rotating residential proxies.

Requirements:
- Support multiple providers: Bright Data, IPRoyal, generic list
- get_proxy() -> returns next proxy in rotation
- mark_failed(proxy) -> blacklist for 1 hour
- mark_success(proxy) -> boost priority
- Health check proxies periodically
- Sticky sessions (same IP for multi-page flow)
- Geographic targeting (country codes)
- get_playwright_context_options(proxy) -> dict for browser context
- Load proxies from file or API

Include complete implementation with docstrings.
Output ONLY the Python code, no explanations."""
    },
    "platform_balancer": {
        "file": "core/platform_balancer.py",
        "prompt": """Create a Python file for PlatformBalancer distributing job applications.

Requirements:
- Daily quotas: linkedin=50, greenhouse=500, lever=200, direct=250
- get_next_platform() -> platform with available quota
- get_next_job(platform) -> job from that platform's queue
- track_application(platform, job_id) -> decrement quota
- reset_quotas() -> called daily at midnight
- Priority weights (prefer high-success platforms)
- Automatic backoff when quota < 10%
- Stats: applications_today, success_rate per platform
- Persistent state in SQLite

Include complete implementation with docstrings.
Output ONLY the Python code, no explanations."""
    },
    "session_manager": {
        "file": "core/session_manager.py", 
        "prompt": """Create a Python file for SessionManager handling authenticated sessions.

Requirements:
- Store sessions for multiple platforms (LinkedIn, Greenhouse, etc.)
- add_session(platform, cookies, metadata)
- get_session(platform) -> returns valid session, rotates if needed
- validate_session(session) -> async check if still authenticated
- rotate_session(platform) -> switch to next available
- Encrypt cookies at rest (Fernet)
- Session health monitoring (mark unhealthy on auth failure)
- Export/import sessions as JSON
- SQLite storage with encryption key from env

Include complete implementation with docstrings.
Output ONLY the Python code, no explanations."""
    },
    "error_handler": {
        "file": "core/error_handler.py",
        "prompt": """Create a Python file for ErrorHandler with retry logic and circuit breakers.

Requirements:
- Error categories: NETWORK, AUTH, CAPTCHA, RATE_LIMIT, FORM_ERROR, UNKNOWN
- @retry decorator with exponential backoff
- CircuitBreaker class (open after 5 failures, reset after 60s)
- DeadLetterQueue for permanently failed jobs
- handle_error(error, context) -> returns action (RETRY, SKIP, ABORT)
- Recovery strategies per error type
- Metrics: error_count by type, retry_count, dlq_size
- Alert callback for critical failures
- Integration with job pipeline

Include complete implementation with docstrings.
Output ONLY the Python code, no explanations."""
    }
}


async def call_kimi(session, task_name, task_info):
    """Call Kimi API for a single task."""
    headers = {
        "Authorization": f"Bearer {MOONSHOT_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "moonshot-v1-8k",
        "messages": [
            {"role": "system", "content": "You are an expert Python developer. Output only clean, production-ready Python code."},
            {"role": "user", "content": task_info["prompt"]}
        ],
        "temperature": 0.3
    }
    
    print(f"[{task_name}] Starting...")
    
    try:
        async with session.post(MOONSHOT_URL, headers=headers, json=payload, timeout=120) as resp:
            if resp.status != 200:
                error = await resp.text()
                print(f"[{task_name}] API Error: {resp.status} - {error[:100]}")
                return task_name, None
            
            data = await resp.json()
            code = data["choices"][0]["message"]["content"]
            
            # Clean up code (remove markdown if present)
            if code.startswith("```python"):
                code = code[9:]
            if code.startswith("```"):
                code = code[3:]
            if code.endswith("```"):
                code = code[:-3]
            
            print(f"[{task_name}] ✅ Generated {len(code)} chars")
            return task_name, code.strip()
            
    except asyncio.TimeoutError:
        print(f"[{task_name}] ❌ Timeout")
        return task_name, None
    except Exception as e:
        print(f"[{task_name}] ❌ Error: {e}")
        return task_name, None


async def main():
    print("=" * 60)
    print("KIMI SWARM - Parallel Code Generation")
    print("=" * 60)
    print(f"Tasks: {len(TASKS)}")
    print()
    
    if not MOONSHOT_API_KEY:
        print("ERROR: MOONSHOT_API_KEY not set")
        return
    
    # Create core directory
    core_dir = Path(__file__).parent.parent / "core"
    core_dir.mkdir(exist_ok=True)
    
    # Run all tasks in parallel
    async with aiohttp.ClientSession() as session:
        tasks = [
            call_kimi(session, name, info) 
            for name, info in TASKS.items()
        ]
        
        results = await asyncio.gather(*tasks)
    
    # Save results
    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    success = 0
    for task_name, code in results:
        if code:
            file_path = core_dir / TASKS[task_name]["file"].replace("core/", "")
            file_path.write_text(code)
            print(f"✅ {task_name} -> {file_path}")
            success += 1
        else:
            print(f"❌ {task_name} - FAILED")
    
    print()
    print(f"Generated: {success}/{len(TASKS)} files")


if __name__ == "__main__":
    asyncio.run(main())
