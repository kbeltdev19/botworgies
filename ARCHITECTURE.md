# Job Applier - Unified Architecture

## Overview

The codebase has been consolidated into a unified, modular architecture centered around:

1. **Core Module** (`core/`) - Foundation layer with models, browser, AI, and config
2. **Adapters** (`adapters/`) - Platform integrations (legacy + new unified adapter)
3. **API** (`api/`) - FastAPI endpoints
4. **Browser** (`browser/`) - Thin wrapper around core.browser

## Directory Structure

```
botworgies/
├── core/                      # Foundation layer
│   ├── __init__.py           # Exports all core components
│   ├── models.py             # Unified data models (JobPosting, UserProfile, etc.)
│   ├── browser.py            # UnifiedBrowserManager (Stagehand)
│   ├── ai.py                 # UnifiedAIService (Moonshot)
│   └── ...                   # Other core utilities
│
├── adapters/                  # Platform integrations
│   ├── __init__.py           # Adapter factory and exports
│   ├── unified.py            # UnifiedPlatformAdapter (recommended)
│   ├── base.py               # Legacy base adapter
│   └── [platform].py         # Legacy platform-specific adapters
│
├── api/                       # FastAPI application
│   ├── main.py               # API entry point
│   ├── config.py             # Unified configuration
│   └── ...                   # Other API modules
│
├── browser/                   # Browser automation (wrapper)
│   └── __init__.py           # Re-exports from core.browser
│
├── ai/                        # AI services (legacy)
│   └── job_agent_cua.py      # CUA agent using Stagehand
│
├── campaigns/                 # Campaign management
├── workers/                   # Cloudflare workers
├── tests/                     # Test suite
├── archive/                   # Archived old code
│   ├── old/                  # Old documentation
│   └── old_code/             # Old code files
│
├── main.py                    # CLI entry point
├── README.md                  # User documentation
└── ARCHITECTURE.md           # This file
```

## Quick Start

### 1. Import from Core (Recommended)

```python
from core import (
    UnifiedBrowserManager,
    UnifiedAIService,
    UserProfile,
    JobPosting,
    config
)
```

### 2. Use the Unified Adapter

```python
from adapters import UnifiedPlatformAdapter

adapter = UnifiedPlatformAdapter(user_profile=profile)
job = await adapter.get_job_details(job_url)
result = await adapter.apply(job, resume)
```

### 3. Browser Automation

```python
from core import UnifiedBrowserManager

async with UnifiedBrowserManager() as browser:
    session = await browser.create_session()
    page = session.page
    
    await page.goto("https://example.com")
    await page.act("click the apply button")
    data = await page.extract('{"title": "string"}')
```

## Key Components

### Core Module

| Component | Purpose | Replaces |
|-----------|---------|----------|
| `core.models` | Data models | `adapters/base.py`, `ats_automation/models.py` |
| `core.browser` | Browser automation | `browser/stealth_manager.py`, `core/browserbase_pool.py` |
| `core.ai` | AI service | `ai/kimi_service.py` |
| `api.config` | Configuration | Multiple scattered config files |

### Adapters

| Adapter | Use Case |
|---------|----------|
| `UnifiedPlatformAdapter` | **Recommended** - handles all platforms via AI |
| `LinkedInAdapter` | Legacy LinkedIn-specific adapter |
| `GreenhouseAdapter` | Legacy Greenhouse-specific adapter |
| ... | Other legacy adapters |

## Environment Variables

Required:
- `MOONSHOT_API_KEY` - Moonshot AI API key
- `BROWSERBASE_API_KEY` - BrowserBase API key
- `BROWSERBASE_PROJECT_ID` - BrowserBase project ID

Optional:
- `MODEL_NAME` - Model to use (default: moonshot-v1-8k-vision-preview)
- `BROWSER_ENV` - BROWSERBASE or LOCAL (default: BROWSERBASE)

## Migration Guide

### From Old Code

**Before:**
```python
from browser.stealth_manager import StealthBrowserManager
from ai.kimi_service import KimiResumeOptimizer
```

**After:**
```python
from core import UnifiedBrowserManager, UnifiedAIService
```

**Before:**
```python
from adapters import get_adapter
adapter = get_adapter("linkedin", browser_manager)
```

**After:**
```python
from adapters import UnifiedPlatformAdapter
adapter = UnifiedPlatformAdapter(user_profile=profile, browser_manager=browser)
```

## Architecture Principles

1. **Single Source of Truth**: Core module is the foundation
2. **Backward Compatibility**: Legacy adapters still work
3. **AI-First**: Unified adapter uses AI for flexibility
4. **Explicit Imports**: Clear import paths, no circular dependencies
5. **Type Safety**: All models are properly typed dataclasses

## Archived Files

Old documentation and code have been moved to `archive/`:
- `archive/old/` - Old documentation
- `archive/old_code/` - Old code modules

These are kept for reference but are no longer maintained.
