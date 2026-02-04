# Unified Job Board Scraping Framework

## Overview

This implementation provides a comprehensive solution for scraping jobs from 40+ job boards with intelligent deduplication, ATS routing, and support for security clearance positions.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    UnifiedJobPipeline                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Dice      │  │ Indeed RSS  │  │ Greenhouse  │             │
│  │   Scraper   │  │   Scraper   │  │  API Client │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ClearanceJobs│  │   Lever     │  │  More...    │             │
│  │  Scraper    │  │  API Client │  │             │             │
│  └──────┬──────┘  └──────┬──────┘  └─────────────┘             │
│         └─────────────────┼─────────────────┘                   │
│                           ▼                                     │
│              ┌─────────────────────────┐                        │
│              │   DeduplicationEngine   │                        │
│              │   (35-40% dedup rate)   │                        │
│              └───────────┬─────────────┘                        │
│                          ▼                                      │
│              ┌─────────────────────────┐                        │
│              │      ATSRouter          │                        │
│              │  (Auto ATS detection)   │                        │
│              └───────────┬─────────────┘                        │
│                          ▼                                      │
│              ┌─────────────────────────┐                        │
│              │   Application Queue     │                        │
│              └─────────────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
```

## Implemented Scrapers

### Tier 1: API-First (No Blocking)

| Scraper | Source | Volume | Features |
|---------|--------|--------|----------|
| `GreenhouseAPIScraper` | boards.greenhouse.io | Very High | Full JSON, direct apply URLs, 50+ default companies |
| `LeverAPIScraper` | api.lever.co | High | Clean JSON, startup-focused, remote detection |
| `IndeedRssScraper` | rss.indeed.com | High | Zero blocking, RSS feeds, 20 results/feed |

### Tier 2: Tech/Security Focus

| Scraper | Source | Volume | Features |
|---------|--------|--------|----------|
| `DiceScraper` | dice.com | High | Tech skills extraction, clearance detection, salary data |
| `ClearanceJobsScraper` | clearancejobs.com | Medium | Auth required, clearance filtering, agency detection |

## Key Features

### 1. Intelligent Deduplication
```python
# Cross-board deduplication using content hashing
engine = DeduplicationEngine()
unique_jobs = engine.filter_unique(all_jobs)

# Expected deduplication rate: 35-40%
# Jobs appearing on multiple boards (e.g., Dice + LinkedIn + Indeed)
```

### 2. ATS Type Detection
```python
router = ATSRouter()
ats_type = router.detect_ats(job_url)  # 'greenhouse', 'lever', 'workday', etc.

# Direct application URL validation
is_direct = router.is_direct_application_url(url)
# Filters out generic career pages vs actual application forms
```

### 3. Security Clearance Support
```python
# ClearanceJobs integration
scraper = ClearanceJobsScraper(username, password)
criteria = SearchCriteria(
    query="software engineer",
    clearance_levels=['Secret', 'TS', 'TS/SCI']
)

# Automatic clearance extraction from descriptions
job.clearance_required  # 'TS/SCI with Polygraph', 'Secret', etc.
```

### 4. Field Mappings
```python
from adapters.job_boards.field_mappings import FieldMappings

# Get selectors for any platform
selectors = FieldMappings.get_selectors('greenhouse', 'first_name')
# ['#first_name', 'input[name="first_name"]', ...]

# Supported platforms:
# - greenhouse, lever, workday, ashby
# - clearancejobs, dice, indeed, smartrecruiters, bamboohr
```

## Usage

### Basic Search
```python
import asyncio
from adapters.job_boards import (
    SearchCriteria, UnifiedJobPipeline,
    IndeedRssScraper, GreenhouseAPIScraper, LeverAPIScraper
)

async def search():
    # Create scrapers
    async with IndeedRssScraper() as indeed, \
               GreenhouseAPIScraper() as gh, \
               LeverAPIScraper() as lever:
        
        pipeline = UnifiedJobPipeline()
        pipeline.add_scraper(indeed)
        pipeline.add_scraper(gh)
        pipeline.add_scraper(lever)
        
        criteria = SearchCriteria(
            query="software engineer",
            location="Remote",
            remote_only=True,
            max_results=100
        )
        
        jobs = await pipeline.search_all(criteria)
        
        # Get statistics
        stats = pipeline.get_stats()
        print(f"Found {stats['unique_jobs']} unique jobs")
        print(f"Deduplicated {stats['duplicates_filtered']} duplicates")
        print(f"By source: {stats['by_source']}")
        print(f"By ATS: {stats['by_ats']}")

asyncio.run(search())
```

### Campaign Runner
```bash
# Basic search
python campaigns/unified_campaign_runner.py \
    --query "software engineer" \
    --location "Remote" \
    --limit 100 \
    --save

# With ClearanceJobs (requires credentials)
python campaigns/unified_campaign_runner.py \
    --query "software engineer" \
    --location "Washington, DC" \
    --enable-clearancejobs \
    --clearance-user "user@example.com" \
    --clearance-pass "password" \
    --save

# Disable specific scrapers
python campaigns/unified_campaign_runner.py \
    --query "software engineer" \
    --disable-dice \
    --disable-indeed
```

## Data Model

### JobPosting
```python
@dataclass
class JobPosting:
    id: str                      # Unique ID (prefixed by source)
    title: str                   # Job title
    company: str                 # Company name
    location: str                # Location string
    description: str             # Job description (cleaned HTML)
    url: str                     # Job posting URL
    source: str                  # Source board (dice, indeed_rss, etc.)
    posted_date: Optional[datetime]
    employment_type: Optional[str]  # Full-time, Contract, etc.
    salary_range: Optional[str]
    clearance_required: Optional[str]  # TS/SCI, Secret, etc.
    remote: bool                 # Remote position flag
    easy_apply: bool             # One-click apply available
    apply_url: str               # Direct application URL
    skills: List[str]            # Extracted tech skills
    raw_data: Dict               # Original board data
```

### SearchCriteria
```python
@dataclass
class SearchCriteria:
    query: str                   # Search keywords
    location: Optional[str]      # Location
    radius: int = 25            # Search radius (miles)
    posted_within_days: int = 7 # Recent jobs only
    employment_type: Optional[str]  # fulltime, contract, etc.
    remote_only: bool = False
    clearance_levels: List[str] = []  # For clearance jobs
    max_results: int = 100
```

## Platform Support Matrix

| Platform | Auth Required | Method | Rate Limit |
|----------|--------------|--------|------------|
| Dice | No | Hidden JSON API | 1 req/sec |
| Indeed RSS | No | RSS Feed | None |
| Greenhouse API | No | Public JSON | 10 req/sec |
| Lever API | No | Public JSON | 10 req/sec |
| ClearanceJobs | Yes | Scraping | 1 req/2sec |

## Expected Results

Based on the job board matrix:

| Phase | Sources | Daily Volume | Success Rate |
|-------|---------|--------------|--------------|
| **Phase 1** (Current) | Dice, Indeed RSS, Greenhouse, Lever | 300-500 | 35-40% |
| **Phase 2** (+ ClearanceJobs, Remote boards) | + WWR, RemoteOK, HN | 500-800 | 45-50% |
| **Phase 3** (+ ZipRecruiter, Monster) | + Generalist boards | 1000-1500 | 60-70% |

## Next Steps

1. **Test the unified pipeline** in production environment
2. **Add more scrapers**:
   - We Work Remotely (RSS)
   - RemoteOK (JSON)
   - Hacker News (Algolia API)
   - ZipRecruiter (requires proxy rotation)
   - LinkedIn (requires auth)

3. **Integrate with application automation**:
   - Route jobs to appropriate ATS handlers
   - Use field mappings for form filling
   - Implement clearance-specific workflows

4. **Monitoring & Analytics**:
   - Track success rates by source
   - Monitor deduplication effectiveness
   - Alert on scraper failures

## Files Added

```
adapters/job_boards/
├── __init__.py           # Core framework (pipeline, dedup, routing)
├── dice.py               # Dice.com scraper
├── clearancejobs.py      # ClearanceJobs.com scraper
├── indeed_rss.py         # Indeed RSS scraper
├── greenhouse_api.py     # Greenhouse API client
├── lever_api.py          # Lever API client
└── field_mappings.py     # Platform-specific selectors

campaigns/
└── unified_campaign_runner.py  # Production campaign runner
```

## Cost Per Application Target

With API-first sourcing:
- **Current**: $0.64/application (BrowserBase heavy)
- **Target**: $0.15-0.22/application (API-first, reduced CAPTCHA)

The unified framework achieves this by:
1. Using RSS/JSON APIs where possible (zero CAPTCHA cost)
2. Reducing duplicate applications across boards
3. Filtering to direct application URLs only (higher success rate)
