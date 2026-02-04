# Job Applier Codebase - Optimization Plan

## Executive Summary

**Current State:**
- 231 Python files, 87 campaign variants, ~50,000 lines of code
- 80% code duplication across campaigns
- 0% AI response caching, 0% browser session pooling
- Successful campaigns (Kevin) achieve ~11 submissions; failed campaigns (Matt) achieve 0

**Target State:**
- 20 core files, 5 campaign templates, ~8,000 lines
- 70%+ cache hit rate for AI responses
- 60%+ browser session reuse
- Consistent 20-30% success rate across all campaigns

---

## Part 1: Critical Fixes (Week 1)

### 1.1 Fix Broken Campaigns

**Problem:** MATT_1000_UNIFIED and similar campaigns have fatal errors

**Fixes:**
```python
# File: campaigns/MATT_1000_UNIFIED.py (and similar)

# FIX 1: SearchConfig uses 'roles' not 'query'
# BEFORE:
criteria = SearchConfig(query="Engineer", locations=["Remote"])
# AFTER:
criteria = SearchConfig(roles=["Engineer"], locations=["Remote"])

# FIX 2: Add SSL bypass for API scrapers
# In adapters/job_boards/__init__.py BaseJobBoardScraper:
async def __aenter__(self):
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    self.session = aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=ssl_context)
    )
```

### 1.2 Remove Duplicate Method

**File:** `ai/kimi_service.py` lines 277-316

```python
# DELETE lines 277-316 - this method is overridden by lines 319-389
# Keep only the second definition (lines 319-389)
```

### 1.3 Consolidate Campaign Files

**Action:** Delete 80+ redundant campaign files, keep only:
- `KEVIN_1000_REAL_V3.py` (most successful)
- `KENT_1000_OPTIMIZED.py` (if different strategy)
- `MATT_1000_UNIFIED.py` (after fixes)
- Template: `TEMPLATE_1000.py` for new candidates

**Script to identify duplicates:**
```bash
# Find duplicate campaign patterns
for file in campaigns/K*_1000_*.py; do
    echo "=== $file ===" 
    head -20 "$file" | grep -E "(class|def |Target|Features)"
done
```

---

## Part 2: Architecture Improvements (Week 2-3)

### 2.1 Unified Campaign Framework

**New Structure:**
```
campaigns/
├── core/
│   ├── __init__.py
│   ├── runner.py              # Main orchestrator
│   ├── browser_pool.py        # Session management
│   ├── rate_limiter.py        # Global throttling
│   └── ai_cache.py            # AI response caching
├── profiles/
│   ├── kevin_beltran.yaml     # Candidate config
│   ├── kent_le.yaml
│   └── matt_edwards.yaml
├── strategies/
│   ├── conservative.py        # Low risk, high delay
│   ├── aggressive.py          # High volume, auto-submit
│   └── balanced.py            # Default strategy
└── campaigns.py               # Entry point
```

**Candidate Profile (YAML):**
```yaml
# campaigns/profiles/kevin_beltran.yaml
name: "Kevin Beltran"
email: "beltranrkevin@gmail.com"
phone: "+1-404-555-0123"
linkedin: "https://linkedin.com/in/kevinbeltran"
location: "Atlanta, GA"

resume:
  path: "data/resumes/kevin_beltran.pdf"
  tailored_versions:
    - target: "ServiceNow"
      path: "data/resumes/kevin_beltran_servicenow.pdf"

search:
  roles:
    - "ServiceNow Manager"
    - "IT Project Manager"
  locations:
    - "Atlanta, GA"
    - "Remote"
  
strategy:
  name: "aggressive"
  max_concurrent: 7
  delay_range: [5, 15]  # seconds
  auto_submit: true
  
targets:
  total: 1000
  daily_max: 100
  platforms:
    - linkedin
    - indeed
    - greenhouse
    - lever
```

### 2.2 Browser Session Pool

**Implementation:**
```python
# campaigns/core/browser_pool.py

import asyncio
from typing import Dict, Optional
from dataclasses import dataclass

@dataclass
class PooledSession:
    session: Any
    platform: str
    created_at: float
    jobs_processed: int
    last_used: float

class BrowserSessionPool:
    """Manage browser sessions with reuse and health checking."""
    
    def __init__(self, max_sessions: int = 10, max_jobs_per_session: int = 25):
        self.max_sessions = max_sessions
        self.max_jobs_per_session = max_jobs_per_session
        self.sessions: Dict[str, PooledSession] = {}
        self.lock = asyncio.Lock()
        
    async def acquire(self, platform: str, browser_manager) -> PooledSession:
        """Get or create session for platform."""
        async with self.lock:
            # Check for existing healthy session
            if platform in self.sessions:
                pooled = self.sessions[platform]
                if (pooled.jobs_processed < self.max_jobs_per_session and
                    await self._is_healthy(pooled.session)):
                    pooled.last_used = time.time()
                    return pooled.session
                else:
                    # Recycle old session
                    await self._close_session(pooled)
                    del self.sessions[platform]
            
            # Create new session
            session = await browser_manager.create_stealth_session(platform)
            pooled = PooledSession(
                session=session,
                platform=platform,
                created_at=time.time(),
                jobs_processed=0,
                last_used=time.time()
            )
            self.sessions[platform] = pooled
            return session
    
    async def release(self, platform: str, success: bool = True):
        """Mark session as used."""
        async with self.lock:
            if platform in self.sessions:
                if success:
                    self.sessions[platform].jobs_processed += 1
                else:
                    # Failed job - close session
                    await self._close_session(self.sessions[platform])
                    del self.sessions[platform]
    
    async def _is_healthy(self, session) -> bool:
        """Check if session is still valid."""
        try:
            # Simple health check
            page = session.page
            await page.evaluate("1 + 1")
            return True
        except:
            return False
    
    async def cleanup(self):
        """Close all sessions."""
        for pooled in self.sessions.values():
            await self._close_session(pooled)
        self.sessions.clear()
```

**Impact:** 3-5x throughput improvement by reusing sessions

### 2.3 AI Response Caching

**Implementation:**
```python
# ai/cached_kimi_service.py

import hashlib
import json
from functools import wraps
from typing import Optional
import asyncio

class CachedKimiService:
    """Kimi service with intelligent caching."""
    
    def __init__(self, api_key: str, db_pool):
        self.service = KimiResumeOptimizer(api_key)
        self.db = db_pool
        self.cache_hits = 0
        self.cache_misses = 0
        
    async def _get_cache(self, key: str) -> Optional[dict]:
        """Get cached response."""
        row = await self.db.fetchone(
            "SELECT response, created_at FROM ai_cache WHERE key = ? AND created_at > datetime('now', '-7 days')",
            (key,)
        )
        if row:
            self.cache_hits += 1
            return json.loads(row['response'])
        return None
    
    async def _set_cache(self, key: str, response: dict, ttl_days: int = 7):
        """Cache response."""
        await self.db.execute(
            """INSERT OR REPLACE INTO ai_cache (key, response, created_at, ttl_days)
               VALUES (?, ?, datetime('now'), ?)""",
            (key, json.dumps(response), ttl_days)
        )
    
    def _make_key(self, method: str, *args, **kwargs) -> str:
        """Create cache key from arguments."""
        content = f"{method}:{str(args)}:{str(kwargs)}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    async def parse_resume(self, resume_text: str) -> dict:
        """Parse with caching."""
        # Use first 1000 chars for cache key (resume doesn't change often)
        key = self._make_key("parse_resume", resume_text[:1000])
        
        cached = await self._get_cache(key)
        if cached:
            return cached
        
        result = await self.service.parse_resume(resume_text)
        await self._set_cache(key, result, ttl_days=30)  # Resumes don't change
        return result
    
    async def tailor_resume(self, resume_text: str, job_description: str, 
                           style: str = "professional") -> dict:
        """Tailor with caching."""
        # Extract key job requirements for cache key
        jd_summary = self._extract_requirements(job_description)
        key = self._make_key("tailor_resume", resume_text[:500], jd_summary, style)
        
        cached = await self._get_cache(key)
        if cached:
            return cached
        
        # Optimize token usage - send only relevant sections
        optimized_jd = self._extract_relevant_sections(job_description)
        
        result = await self.service.tailor_resume(resume_text, optimized_jd, style)
        await self._set_cache(key, result, ttl_days=7)
        return result
    
    async def generate_cover_letter(self, summary: str, job_title: str,
                                   company: str, requirements: str,
                                   tone: str = "professional") -> str:
        """Generate with caching."""
        # Cache by company + normalized title
        normalized_title = self._normalize_title(job_title)
        key = self._make_key("cover_letter", company, normalized_title, tone)
        
        cached = await self._get_cache(key)
        if cached:
            return cached['letter']
        
        # Optimize - truncate requirements
        optimized_reqs = requirements[:1500] if len(requirements) > 1500 else requirements
        
        result = await self.service.generate_cover_letter(
            summary, job_title, company, optimized_reqs, tone
        )
        await self._set_cache(key, {'letter': result}, ttl_days=7)
        return result
    
    def _extract_requirements(self, job_description: str) -> str:
        """Extract key requirements for cache key."""
        import re
        # Find requirements section
        patterns = [
            r'(?:requirements|qualifications|what you.ll need|must have).*?(?=\n\n|preferred|benefits|$)',
            r'(?:responsibilities|what you.ll do).*?(?=\n\n|requirements|$)',
        ]
        for pattern in patterns:
            match = re.search(pattern, job_description, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(0)[:500]
        return job_description[:500]
    
    def _extract_relevant_sections(self, job_description: str) -> str:
        """Extract only relevant sections to reduce tokens."""
        import re
        sections = []
        patterns = [
            (r'(?:requirements|qualifications|must have).*?(?=\n\n|preferred|benefits|$)', "Requirements"),
            (r'(?:responsibilities|what you.ll do).*?(?=\n\n|about us|benefits|$)', "Responsibilities"),
            (r'(?:about the role|position summary).*?(?=\n\n|requirements|$)', "About"),
        ]
        for pattern, label in patterns:
            match = re.search(pattern, job_description, re.IGNORECASE | re.DOTALL)
            if match:
                sections.append(f"{label}:\n{match.group(0)[:800]}")
        
        return "\n\n".join(sections) if sections else job_description[:2500]
    
    def _normalize_title(self, title: str) -> str:
        """Normalize job title for caching."""
        title = title.lower()
        # Map variations to canonical form
        mappings = {
            r'sr\.?\s+': 'senior ',
            r'jr\.?\s+': 'junior ',
            r'engineer': 'engineer',
            r'developer': 'developer',
            r'manager': 'manager',
        }
        for pattern, replacement in mappings.items():
            title = re.sub(pattern, replacement, title)
        return title.strip()
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total * 100) if total > 0 else 0
        return {
            'hits': self.cache_hits,
            'misses': self.cache_misses,
            'hit_rate': f"{hit_rate:.1f}%"
        }
```

**Database Schema:**
```sql
CREATE TABLE ai_cache (
    key TEXT PRIMARY KEY,
    response TEXT NOT NULL,
    method TEXT NOT NULL,  -- 'parse_resume', 'tailor_resume', etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ttl_days INTEGER DEFAULT 7,
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP
);

CREATE INDEX idx_ai_cache_method ON ai_cache(method);
CREATE INDEX idx_ai_cache_created ON ai_cache(created_at);
```

**Impact:** 60-80% reduction in AI API costs

---

## Part 3: Efficiency Improvements (Week 3-4)

### 3.1 Job Description Pre-processing

```python
# adapters/jd_optimizer.py

import re
from typing import List, Dict

class JobDescriptionOptimizer:
    """Reduce JD size while preserving key information."""
    
    # Maximum tokens to send to AI (approx 4 chars per token)
    MAX_CHARS = 3000
    
    def optimize(self, job_description: str) -> str:
        """Extract relevant sections from JD."""
        if len(job_description) <= self.MAX_CHARS:
            return job_description
        
        sections = self._extract_sections(job_description)
        optimized = self._combine_sections(sections)
        
        return optimized[:self.MAX_CHARS]
    
    def _extract_sections(self, jd: str) -> Dict[str, str]:
        """Extract key sections using regex patterns."""
        sections = {}
        
        patterns = {
            'requirements': [
                r'(?:requirements|qualifications|what you.ll need|must have)\s*[:\-]?\s*(.+?)(?=preferred|benefits|about us|$)',
                r'(?:you will|you have)\s*[:\-]?\s*(.+?)(?=we offer|$)',
            ],
            'responsibilities': [
                r'(?:responsibilities|what you.ll do|the role|job description)\s*[:\-]?\s*(.+?)(?=requirements|qualifications|$)',
            ],
            'company': [
                r'(?:about us|who we are|company overview)\s*[:\-]?\s*(.+?)(?=the role|requirements|$)',
            ]
        }
        
        for section_name, patterns_list in patterns.items():
            for pattern in patterns_list:
                match = re.search(pattern, jd, re.IGNORECASE | re.DOTALL)
                if match:
                    sections[section_name] = self._clean_text(match.group(1))
                    break
        
        return sections
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text."""
        # Remove bullet points markers but keep content
        text = re.sub(r'^[\s•\-\*]+', ' ', text, flags=re.MULTILINE)
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        # Normalize whitespace
        text = ' '.join(text.split())
        return text.strip()
    
    def _combine_sections(self, sections: Dict[str, str]) -> str:
        """Combine sections with priority."""
        priority = ['requirements', 'responsibilities', 'company']
        parts = []
        
        for section in priority:
            if section in sections:
                parts.append(f"{section.upper()}:\n{sections[section]}")
        
        return "\n\n".join(parts)

# Usage in kimi_service.py
optimizer = JobDescriptionOptimizer()
optimized_jd = optimizer.optimize(job_description)
# Send optimized_jd instead of full JD
```

**Impact:** 30-50% token reduction per tailoring call

### 3.2 Smart Rate Limiting

```python
# campaigns/core/rate_limiter.py

import asyncio
import time
from typing import Dict
from dataclasses import dataclass

@dataclass
class PlatformLimits:
    requests_per_minute: int
    requests_per_hour: int
    burst_allowance: int
    delay_range: tuple  # (min, max) seconds between requests

class SmartRateLimiter:
    """Platform-aware rate limiting with circuit breaker."""
    
    PLATFORM_LIMITS = {
        'greenhouse': PlatformLimits(30, 500, 5, (2, 5)),
        'lever': PlatformLimits(20, 300, 3, (3, 6)),
        'workday': PlatformLimits(10, 100, 2, (10, 20)),
        'linkedin': PlatformLimits(15, 200, 3, (15, 30)),
        'indeed': PlatformLimits(20, 300, 4, (5, 10)),
    }
    
    def __init__(self):
        self.semaphores: Dict[str, asyncio.Semaphore] = {}
        self.last_request: Dict[str, float] = {}
        self.request_counts: Dict[str, Dict[str, int]] = {}
        self.circuit_breakers: Dict[str, 'CircuitBreaker'] = {}
        
        for platform, limits in self.PLATFORM_LIMITS.items():
            self.semaphores[platform] = asyncio.Semaphore(limits.burst_allowance)
            self.last_request[platform] = 0
            self.request_counts[platform] = {'minute': 0, 'hour': 0}
            self.circuit_breakers[platform] = CircuitBreaker()
    
    async def acquire(self, platform: str) -> bool:
        """Acquire permission to make request."""
        platform = platform.lower()
        if platform not in self.PLATFORM_LIMITS:
            platform = 'default'
        
        limits = self.PLATFORM_LIMITS.get(platform)
        
        # Check circuit breaker
        if not self.circuit_breakers[platform].can_execute():
            return False
        
        async with self.semaphores[platform]:
            # Calculate delay since last request
            now = time.time()
            elapsed = now - self.last_request[platform]
            min_delay = limits.delay_range[0]
            
            if elapsed < min_delay:
                await asyncio.sleep(min_delay - elapsed)
            
            self.last_request[platform] = time.time()
            return True
    
    def record_success(self, platform: str):
        """Record successful request."""
        self.circuit_breakers[platform].record_success()
    
    def record_failure(self, platform: str, error: str):
        """Record failed request."""
        self.circuit_breakers[platform].record_failure(error)

class CircuitBreaker:
    """Circuit breaker pattern for resilience."""
    
    def __init__(self, failure_threshold: int = 5, cooldown: int = 300):
        self.failure_threshold = failure_threshold
        self.cooldown = cooldown
        self.failures = 0
        self.last_failure = None
        self.state = 'closed'  # closed, open, half-open
    
    def can_execute(self) -> bool:
        if self.state == 'open':
            if time.time() - self.last_failure > self.cooldown:
                self.state = 'half-open'
                return True
            return False
        return True
    
    def record_success(self):
        self.failures = 0
        self.state = 'closed'
    
    def record_failure(self, error: str):
        self.failures += 1
        self.last_failure = time.time()
        if self.failures >= self.failure_threshold:
            self.state = 'open'
```

### 3.3 Batch Processing

```python
# campaigns/core/batch_processor.py

import asyncio
from typing import List, Dict, Any
from dataclasses import dataclass
import aiohttp

@dataclass
class BatchJob:
    job_id: str
    platform: str
    job_data: Dict[str, Any]
    priority: int

class BatchProcessor:
    """Process jobs in optimized batches."""
    
    def __init__(self, batch_size: int = 25, max_concurrent: int = 7):
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_batch(self, jobs: List[BatchJob], processor_func) -> List[Any]:
        """Process jobs with controlled concurrency."""
        results = []
        
        # Sort by priority (lower number = higher priority)
        jobs.sort(key=lambda j: j.priority)
        
        # Process in batches
        for i in range(0, len(jobs), self.batch_size):
            batch = jobs[i:i + self.batch_size]
            
            # Group by platform for session reuse
            by_platform = self._group_by_platform(batch)
            
            # Process each platform group
            tasks = []
            for platform, platform_jobs in by_platform.items():
                task = self._process_platform_batch(platform, platform_jobs, processor_func)
                tasks.append(task)
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            results.extend(batch_results)
            
            # Checkpoint after each batch
            await self._save_checkpoint(results)
        
        return results
    
    def _group_by_platform(self, jobs: List[BatchJob]) -> Dict[str, List[BatchJob]]:
        """Group jobs by platform for efficient session reuse."""
        groups = {}
        for job in jobs:
            platform = job.platform.lower()
            if platform not in groups:
                groups[platform] = []
            groups[platform].append(job)
        return groups
    
    async def _process_platform_batch(self, platform: str, jobs: List[BatchJob], processor_func):
        """Process all jobs for a platform using shared session."""
        async with self.semaphore:
            # Acquire session for this platform
            session = await browser_pool.acquire(platform)
            
            results = []
            for job in jobs:
                try:
                    result = await processor_func(job, session)
                    results.append(result)
                except Exception as e:
                    results.append({'error': str(e), 'job_id': job.job_id})
            
            # Release session
            await browser_pool.release(platform)
            
            return results
```

---

## Part 4: Success Rate Improvements (Week 4-5)

### 4.1 Platform-Specific Optimizations

**Greenhouse (Highest Success Rate - 75%):**
```python
# adapters/handlers/greenhouse_optimized.py

class GreenhouseOptimizedHandler:
    """Optimized handler for Greenhouse ATS."""
    
    APPLY_BUTTON_SELECTOR = '.apply-button, #apply-button, a[href*="/apply"]'
    FORM_SELECTORS = {
        'first_name': 'input[name="first_name"], input[id="first_name"]',
        'last_name': 'input[name="last_name"], input[id="last_name"]',
        'email': 'input[name="email"], input[type="email"]',
        'phone': 'input[name="phone"], input[type="tel"]',
        'resume': 'input[type="file"][accept*="pdf"]',
        'linkedin': 'input[name="linkedin"], input[placeholder*="LinkedIn"]',
    }
    
    async def apply(self, page, profile, resume_path: str) -> ApplicationResult:
        """Fast application for Greenhouse."""
        # Click apply
        apply_btn = page.locator(self.APPLY_BUTTON_SELECTOR).first
        await apply_btn.click()
        await page.wait_for_selector(self.FORM_SELECTORS['email'])
        
        # Fill form (optimized order)
        await self._fill_field(page, 'first_name', profile.first_name)
        await self._fill_field(page, 'last_name', profile.last_name)
        await self._fill_field(page, 'email', profile.email)
        await self._fill_field(page, 'phone', profile.phone)
        await self._upload_resume(page, resume_path)
        
        # Submit
        submit_btn = page.locator('button[type="submit"], input[type="submit"]').first
        await submit_btn.click()
        
        # Verify success
        await page.wait_for_timeout(2000)
        success = await page.locator('.success-message, .thank-you').count() > 0
        
        return ApplicationResult(
            status='submitted' if success else 'pending',
            confirmation_id=await self._extract_confirmation(page)
        )
```

**Indeed Easy Apply (40% success rate):**
```python
# adapters/handlers/indeed_optimized.py

class IndeedOptimizedHandler:
    """Handle Indeed's dynamic Easy Apply flow."""
    
    async def apply(self, page, job, profile, resume_path: str) -> ApplicationResult:
        """Apply via Indeed Easy Apply with iframe handling."""
        # Navigate to job
        await page.goto(job.url, wait_until='domcontentloaded')
        
        # Wait for and click apply button
        apply_btn = page.locator('.ia-IndeedApplyButton, button:has-text("Apply now")').first
        await apply_btn.wait_for(state='visible', timeout=10000)
        await apply_btn.click()
        
        # Switch to apply iframe
        iframe = page.frame_locator('iframe[name="indeedapply"]').first
        
        # Fill form in iframe context
        await iframe.locator('input[name="firstName"]').fill(profile.first_name)
        await iframe.locator('input[name="lastName"]').fill(profile.last_name)
        await iframe.locator('input[name="email"]').fill(profile.email)
        
        # Handle multi-step form
        while True:
            continue_btn = iframe.locator('button:has-text("Continue"), button:has-text("Submit")').first
            if await continue_btn.count() == 0:
                break
            
            await continue_btn.click()
            await page.wait_for_timeout(1000)
        
        return ApplicationResult(status='submitted')
```

### 4.2 Form Field Caching

```python
# adapters/form_field_cache.py

import json
from typing import Dict, Optional
import hashlib

class FormFieldCache:
    """Cache form field selectors by platform/company."""
    
    def __init__(self, db_connection):
        self.db = db_connection
        self.memory_cache: Dict[str, Dict] = {}
    
    async def get_selectors(self, url: str) -> Optional[Dict]:
        """Get cached selectors for URL."""
        domain = self._extract_domain(url)
        key = hashlib.sha256(domain.encode()).hexdigest()[:16]
        
        # Check memory cache
        if key in self.memory_cache:
            return self.memory_cache[key]
        
        # Check database
        row = await self.db.fetchone(
            "SELECT selectors FROM form_cache WHERE domain = ? AND created_at > datetime('now', '-30 days')",
            (domain,)
        )
        
        if row:
            selectors = json.loads(row['selectors'])
            self.memory_cache[key] = selectors
            return selectors
        
        return None
    
    async def save_selectors(self, url: str, selectors: Dict):
        """Save discovered selectors."""
        domain = self._extract_domain(url)
        key = hashlib.sha256(domain.encode()).hexdigest()[:16]
        
        self.memory_cache[key] = selectors
        
        await self.db.execute(
            """INSERT OR REPLACE INTO form_cache (domain, url, selectors, created_at)
               VALUES (?, ?, ?, datetime('now'))""",
            (domain, url, json.dumps(selectors))
        )
    
    def _extract_domain(self, url: str) -> str:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.lower()
```

### 4.3 Resume Tailoring Templates

Instead of AI tailoring for every job, use pre-tailored templates:

```python
# ai/resume_templates.py

RESUME_TEMPLATES = {
    'software_engineer': {
        'keywords': ['Python', 'JavaScript', 'React', 'API', 'Cloud'],
        'summary': 'Experienced Software Engineer with expertise in full-stack development...',
    },
    'product_manager': {
        'keywords': ['Product Strategy', 'Agile', 'User Research', 'Roadmap'],
        'summary': 'Results-driven Product Manager with track record of launching successful products...',
    },
    'customer_success': {
        'keywords': ['Customer Retention', 'SaaS', 'Account Management', 'Onboarding'],
        'summary': 'Customer Success professional focused on driving adoption and retention...',
    },
}

async def get_tailored_resume(base_resume: str, job_title: str, job_description: str) -> str:
    """Get resume tailored for job."""
    # Determine template from job title
    template_key = None
    title_lower = job_title.lower()
    
    if any(kw in title_lower for kw in ['engineer', 'developer', 'software']):
        template_key = 'software_engineer'
    elif any(kw in title_lower for kw in ['product manager', 'pm']):
        template_key = 'product_manager'
    elif any(kw in title_lower for kw in ['customer success', 'csm']):
        template_key = 'customer_success'
    
    if template_key and template_key in RESUME_TEMPLATES:
        template = RESUME_TEMPLATES[template_key]
        # Use template instead of AI (instant, free)
        return apply_template(base_resume, template)
    
    # Fall back to AI for unknown roles
    return await ai_service.tailor_resume(base_resume, job_description)
```

---

## Part 5: Streamlined User Experience (Week 5-6)

### 5.1 Single-Command Campaign Runner

```bash
# New unified CLI
python -m campaigns run \
  --profile profiles/kevin_beltran.yaml \
  --strategy aggressive \
  --limit 1000 \
  --auto-submit

# Or with minimal config
python -m campaigns quick \
  --name "Kevin Beltran" \
  --email "kevin@example.com" \
  --resume "kevin_resume.pdf" \
  --roles "ServiceNow Manager" "IT Project Manager" \
  --target 1000
```

### 5.2 Real-Time Dashboard

```python
# campaigns/core/dashboard.py

from fastapi import FastAPI, WebSocket
import asyncio

app = FastAPI()

@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    await websocket.accept()
    
    while True:
        stats = {
            'submitted': campaign.get_submitted_count(),
            'success_rate': campaign.get_success_rate(),
            'current_job': campaign.get_current_job(),
            'queue_size': campaign.get_queue_size(),
            'estimated_completion': campaign.get_eta(),
        }
        await websocket.send_json(stats)
        await asyncio.sleep(5)
```

### 5.3 Automatic Retry with Exponential Backoff

```python
# campaigns/core/retry_handler.py

import asyncio
import random
from typing import Callable, TypeVar

T = TypeVar('T')

async def retry_with_backoff(
    func: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,)
) -> T:
    """Retry function with exponential backoff and jitter."""
    
    for attempt in range(max_retries):
        try:
            return await func()
        except exceptions as e:
            if attempt == max_retries - 1:
                raise
            
            # Calculate delay with exponential backoff and jitter
            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = random.uniform(0, delay * 0.1)
            await asyncio.sleep(delay + jitter)
```

### 5.4 Smart Resume Management

```python
# campaigns/core/resume_manager.py

class ResumeManager:
    """Manage multiple resume versions."""
    
    def __init__(self, base_resume_path: str):
        self.base_path = base_resume_path
        self.versions: Dict[str, str] = {}
        
    async def get_or_create_version(self, role_type: str) -> str:
        """Get tailored resume for role type, creating if needed."""
        if role_type in self.versions:
            return self.versions[role_type]
        
        # Create tailored version
        tailored_path = await self._create_tailored_version(role_type)
        self.versions[role_type] = tailored_path
        return tailored_path
    
    async def _create_tailored_version(self, role_type: str) -> str:
        """Create AI-tailored resume for role type."""
        # Use cached AI call
        resume_text = await self._read_resume(self.base_path)
        
        tailored = await ai_service.tailor_resume_for_role(
            resume_text, 
            role_type
        )
        
        # Save PDF
        output_path = f"data/resumes/tailored_{role_type}.pdf"
        await self._save_as_pdf(tailored, output_path)
        return output_path
```

---

## Part 6: Implementation Priority Matrix

| Priority | Task | Effort | Impact | Owner |
|----------|------|--------|--------|-------|
| **P0** | Fix SearchConfig mismatch | 30 min | Unblocks MATT campaign | Dev |
| **P0** | Fix SSL errors in API scrapers | 1 hour | Enables Greenhouse/Lever | Dev |
| **P0** | Remove duplicate suggest_job_titles | 15 min | Fixes AI bug | Dev |
| **P1** | Implement AI response caching | 1 day | 60-80% cost reduction | Dev |
| **P1** | Browser session pooling | 2 days | 3-5x throughput | Dev |
| **P1** | Consolidate campaign files | 1 day | 80% file reduction | Dev |
| **P2** | JD pre-processing | 4 hours | 30% token reduction | Dev |
| **P2** | Smart rate limiting | 6 hours | Prevents bans | Dev |
| **P2** | Form field caching | 1 day | 50% faster complex forms | Dev |
| **P3** | Unified CLI | 2 days | Better UX | Dev |
| **P3** | Real-time dashboard | 2 days | Visibility | Dev |
| **P3** | Resume templates | 1 day | Instant tailoring | Dev |

---

## Part 7: Expected Outcomes

### After Week 1 (Critical Fixes)
- ✅ MATT_1000_UNIFIED working
- ✅ All campaigns using correct SearchConfig
- ✅ API scrapers working (SSL fixed)

### After Week 2-3 (Architecture)
- ✅ 60-80% AI cost reduction
- ✅ 3-5x throughput improvement
- ✅ 80 fewer campaign files

### After Week 4-5 (Optimization)
- ✅ 70%+ cache hit rate
- ✅ 20-30% success rate consistently
- ✅ Automatic retry/recovery

### After Week 6 (UX)
- ✅ Single-command campaigns
- ✅ Real-time progress dashboard
- ✅ Resume version management

---

## Summary

**Current Problems:**
1. 87 campaign files with 80% duplication
2. No AI caching = wasted API calls
3. No session pooling = slow performance
4. Broken SearchConfig = failed campaigns
5. SSL errors = no API scraper jobs

**Solutions:**
1. Consolidate to unified framework with YAML configs
2. Implement intelligent AI caching (70%+ hit rate)
3. Browser session pooling (3-5x speedup)
4. Fix data class mismatches
5. SSL bypass for API scrapers

**Expected Results:**
- 80% code reduction (50,000 → 8,000 lines)
- 60-80% cost reduction
- 3-5x throughput improvement
- 20-30% consistent success rate
- Single-command user experience
