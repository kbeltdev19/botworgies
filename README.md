# Job Applier - AI-Powered Job Application Automation

> **Consolidated Version** - The codebase has been unified for easier development.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export MOONSHOT_API_KEY="your-key"
export BROWSERBASE_API_KEY="your-key"
export BROWSERBASE_PROJECT_ID="your-project"

# Run the server
python main.py server

# Or apply to a single job
python main.py apply \
  --job-url "https://boards.greenhouse.io/..." \
  --profile path/to/profile.yaml \
  --resume path/to/resume.pdf
```

## What's New (Consolidated)

- **Unified Core Module** (`core/`) - Single source of truth for models, browser, AI
- **BrowserBase Stagehand** - AI-powered browser automation
- **Unified Adapter** - One adapter handles all platforms via AI
- **Simplified Architecture** - Reduced from 311 Python files to ~50 core files

## Architecture

```
core/           # Foundation: models, browser, AI, config
adapters/       # Platform integrations (use UnifiedPlatformAdapter)
api/            # FastAPI endpoints
browser/        # Browser automation (Stagehand)
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed documentation.

## Usage

### Python API

```python
from core import UnifiedBrowserManager, UserProfile
from adapters import UnifiedPlatformAdapter

async with UnifiedBrowserManager() as browser:
    adapter = UnifiedPlatformAdapter(
        user_profile=profile,
        browser_manager=browser
    )
    
    job = await adapter.get_job_details(job_url)
    result = await adapter.apply(job, resume)
```

### Stagehand Direct

```python
from core import UnifiedBrowserManager

async with UnifiedBrowserManager() as browser:
    session = await browser.create_session()
    page = session.page
    
    await page.goto("https://example.com")
    await page.act("click the apply button")
    data = await page.extract('{"title": "string"}')
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key (for Stagehand AI features) |
| `BROWSERBASE_API_KEY` | Yes | BrowserBase API key |
| `BROWSERBASE_PROJECT_ID` | Yes | BrowserBase project ID |
| `MOONSHOT_API_KEY` | No | Moonshot AI API key (optional alternative) |
| `MODEL_NAME` | No | Model (default: gpt-4o) |
| `BROWSER_ENV` | No | BROWSERBASE or LOCAL |

## Project Structure

```
botworgies/
├── core/               # Unified foundation
├── adapters/           # Platform adapters
├── api/                # FastAPI app
├── browser/            # Browser automation
├── campaigns/          # Campaign management
├── tests/              # Test suite
├── main.py             # CLI entry point
└── ARCHITECTURE.md     # Detailed docs
```

## Architecture Consolidation

The codebase has been consolidated from 311+ files to ~130 files:
- **Core** (`core/`) - Foundation with models, browser, AI
- **Adapters** (`adapters/`) - Platform integrations
- **API** (`api/`) - FastAPI endpoints
- **Browser** (`browser/`) - Re-exports from core.browser

See [ARCHITECTURE.md](ARCHITECTURE.md) for migration guide.

## Development

```bash
# Run tests
pytest tests/ -v

# Run specific test
pytest tests/test_unified_system.py -v

# Check types
mypy core/ adapters/
```

## License

MIT
