# Job Applier - AI-Powered Job Application Automation Platform

> This file contains essential information for AI coding agents working on this project.

## Project Overview

Job Applier is an AI-powered job application automation platform that helps users:
- Parse and optimize resumes using Kimi AI (Moonshot)
- Search for jobs on LinkedIn and Indeed
- Automate Easy Apply applications with human-like behavior
- Generate personalized cover letters
- Track application history

The platform emphasizes **safety and ethics**: AI only rephrases existing experience (never invents), with rate limiting, human review options, and audit trails.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│           Frontend (Cloudflare Pages / Static)          │
│              Single HTML file with Tailwind CSS         │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│         Cloudflare Workers (API Proxy - Optional)       │
│              workers/index.js                           │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│              FastAPI Backend (Python 3.11+)             │
│  ┌─────────────┐ ┌──────────────┐ ┌─────────────────┐  │
│  │   Kimi AI   │ │   Browser    │ │  Platform       │  │
│  │   Service   │ │   Manager    │ │  Adapters       │  │
│  │  (Moonshot) │ │(BrowserBase) │ │(LinkedIn, etc.)│  │
│  └─────────────┘ └──────────────┘ └─────────────────┘  │
└─────────────────────────┬───────────────────────────────┘
                          │
         ┌────────────────┴────────────────┐
         │                                 │
┌────────▼────────┐            ┌──────────▼──────────┐
│  Moonshot AI    │            │    BrowserBase      │
│  (Kimi API)     │            │ (Stealth Browsers)  │
└─────────────────┘            └─────────────────────┘
```

## Technology Stack

### Backend (Primary)
- **Framework**: FastAPI 0.109.0 with Python 3.11+
- **Server**: Uvicorn (ASGI)
- **Database**: SQLite with aiosqlite (async)
- **Authentication**: JWT tokens (PyJWT)
- **AI Service**: Moonshot AI (Kimi) via OpenAI-compatible API
- **Browser Automation**: Playwright + BrowserBase (stealth browsing)
- **File Parsing**: PyPDF2, python-docx

### Frontend
- **Type**: Static HTML (single file)
- **Styling**: Tailwind CSS via CDN
- **Hosting**: Cloudflare Pages (or local Python server for dev)
- **State**: localStorage for profile/search preferences

### Infrastructure
- **Primary Hosting**: Fly.io (Docker container)
- **Edge Proxy**: Cloudflare Workers (optional)
- **CI/CD**: GitHub Actions
- **Monitoring**: Custom metrics module

## Project Structure

```
job-applier/
├── api/                    # FastAPI backend
│   ├── main.py            # Main application with all endpoints
│   ├── config.py          # Configuration (AppConfig dataclass)
│   ├── auth.py            # JWT authentication & encryption
│   ├── database.py        # SQLite async operations
│   └── logging_config.py  # Structured logging
│
├── ai/                    # AI service integrations
│   ├── kimi_service.py    # Moonshot/Kimi API wrapper
│   └── brave_research.py  # Company research (optional)
│
├── browser/               # Browser automation
│   └── stealth_manager.py # BrowserBase + Playwright stealth
│
├── adapters/              # Job platform adapters
│   ├── __init__.py        # Factory functions & platform detection
│   ├── base.py            # Abstract base class & data models
│   ├── linkedin.py        # LinkedIn adapter (search + Easy Apply)
│   ├── indeed.py          # Indeed adapter
│   ├── greenhouse.py      # Greenhouse ATS adapter
│   ├── workday.py         # Workday ATS adapter
│   ├── lever.py           # Lever ATS adapter
│   ├── clearancejobs.py   # ClearanceJobs adapter
│   └── company.py         # Generic company website adapter
│
├── frontend/              # Static frontend
│   └── index.html         # Single-file UI (900+ lines)
│
├── workers/               # Cloudflare Workers
│   └── index.js           # API proxy edge worker
│
├── tests/                 # Test suite
│   ├── conftest.py        # Pytest fixtures
│   ├── safety/            # Hallucination & safety tests
│   ├── e2e/               # End-to-end workflow tests
│   ├── stealth/           # Anti-detection tests
│   ├── performance/       # Benchmark tests
│   └── resilience/        # Failure mode tests
│
├── monitoring/            # Observability
│   └── metrics.py         # Custom metrics (Counter, Gauge, Histogram)
│
├── requirements.txt       # Python dependencies
├── fly.toml              # Fly.io deployment config
├── wrangler.toml         # Cloudflare Workers config
├── Dockerfile            # Container build
├── pytest.ini            # Test configuration
└── .github/workflows/     # CI/CD pipeline
    └── ci.yml
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MOONSHOT_API_KEY` | - | **Required** for AI features |
| `BROWSERBASE_API_KEY` | - | For stealth browsers |
| `BROWSERBASE_PROJECT_ID` | - | BrowserBase project |
| `JWT_SECRET_KEY` | random | JWT signing key |
| `PASSWORD_SALT` | job-applier-salt | Password hashing salt |
| `DATABASE_PATH` | ./data/job_applier.db | SQLite location |
| `DATA_DIR` | ./data | File uploads directory |
| `LOG_DIR` | ./logs | Log files directory |
| `HOST` | 0.0.0.0 | API bind address |
| `PORT` | 8080 | API port |
| `DEBUG` | false | Enable docs/debug endpoints |
| `CORS_ORIGINS` | localhost, pages.dev | Allowed CORS origins |
| `DEFAULT_DAILY_LIMIT` | 10 | Max applications per 24h |

### Local Development Secrets

Create `~/.clawdbot/secrets/tokens.env`:
```
MOONSHOT_API_KEY=your_key_here
BROWSERBASE_API_KEY=bb_live_xxx
BROWSERBASE_PROJECT_ID=xxx-xxx-xxx
```

## Build and Run Commands

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Run backend
cd api
uvicorn main:app --reload --port 8000

# Run frontend (separate terminal)
cd frontend
python -m http.server 3000

# Open http://localhost:3000
```

### Testing

```bash
# Run all tests
pytest

# Run specific test categories
pytest -m "not e2e and not stealth"  # Skip slow tests
pytest -m safety                      # Safety/hallucination tests
pytest -m e2e                         # End-to-end tests
pytest -m performance                 # Benchmark tests

# With coverage
pytest --cov=api --cov=adapters --cov=ai --cov-report=term-missing
```

### Docker

```bash
# Build image
docker build -t job-applier .

# Run container
docker run -p 8080:8080 \
  -e MOONSHOT_API_KEY=xxx \
  -e BROWSERBASE_API_KEY=xxx \
  job-applier
```

### Deployment

```bash
# Deploy backend to Fly.io
fly deploy

# Deploy frontend to Cloudflare Pages
npx wrangler pages deploy frontend --project-name=job-applier-ui

# Deploy Workers proxy
npx wrangler deploy
```

## Code Style Guidelines

### Python
- **Formatter**: Black
- **Import Sorter**: isort
- **Linter**: ruff
- **Type Hints**: Use typing for public APIs
- **Docstrings**: Google style docstrings for modules and classes

### JavaScript (Workers)
- ES6 modules
- JSDoc comments for functions

### Key Patterns

1. **Async/Await**: All I/O operations are async (database, HTTP, browser)
2. **Dataclasses**: Use `@dataclass` for configuration and models
3. **Abstract Base Classes**: Platform adapters inherit from `JobPlatformAdapter`
4. **Context Managers**: Use `asynccontextmanager` for resources (database connections)
5. **Error Handling**: Graceful degradation with logging; HTTP exceptions for API errors

## Testing Strategy

### Test Categories

| Marker | Description | When to Run |
|--------|-------------|-------------|
| (default) | Unit tests | Every commit |
| `e2e` | Full workflows | PRs, before release |
| `safety` | Hallucination guards | PRs affecting AI prompts |
| `stealth` | Anti-detection | Manual, browser-dependent |
| `performance` | Benchmarks | Release candidates |
| `resilience` | Failure modes | Infrastructure changes |

### Test Fixtures (conftest.py)
- `sample_resume_text` - Parsed resume content
- `sample_job_description` - JD for tailoring tests
- `sample_user_profile` - UserProfile dataclass instance
- `sample_resume` - Resume dataclass instance
- `mock_kimi_service` - AsyncMock for AI service
- `mock_browser_manager` - Mock for browser operations

### Safety Tests (Critical)
- `test_resume_tailoring_no_new_companies` - No company hallucination
- `test_no_skill_fabrication` - No skill claims not in resume
- `test_cover_letter_no_experience_inflation` - Accurate experience years
- `test_daily_rate_limit_enforcement` - Rate limit compliance

## Security Considerations

### Authentication
- JWT tokens with 24h access / 30d refresh expiry
- Password hashing with SHA-256 + salt
- Bearer token in Authorization header

### Data Protection
- LinkedIn cookies encrypted at rest (XOR with key-derived hash)
- Sensitive data not logged
- File upload validation (extensions, size limits)

### API Security
- CORS restricted to configured origins
- Rate limiting per user (configurable daily limit)
- Input validation via Pydantic models
- File path sanitization to prevent traversal

### Operational Security
- Health check endpoint for monitoring
- Metrics tracking for anomaly detection (IP blocks, account warnings)
- Automated dependency vulnerability scanning (safety, bandit)

## Key Modules Reference

### Adapters (`adapters/`)
All job platform adapters must implement:
- `search_jobs(criteria: SearchConfig) -> List[JobPosting]`
- `get_job_details(job_url: str) -> JobPosting`
- `apply_to_job(job, resume, profile, cover_letter, auto_submit) -> ApplicationResult`

Factory: `get_adapter(platform, browser_manager, session_cookie)`
Detection: `detect_platform_from_url(url) -> platform_id`

### AI Service (`ai/kimi_service.py`)
`KimiResumeOptimizer` methods:
- `parse_resume(text) -> dict` - Extract structured data
- `tailor_resume(resume, job_description, style) -> dict` - Optimize bullets
- `generate_cover_letter(summary, job_title, company, requirements, tone) -> str`
- `answer_application_question(question, context, existing_answers) -> str`

Safety: Prompts include "DO NOT invent new experience" constraints.

### Browser Manager (`browser/stealth_manager.py`)
`StealthBrowserManager` features:
- BrowserBase cloud sessions with residential proxies
- Stealth patches (webdriver hiding, WebGL spoofing, plugins mock)
- Human-like interactions (random delays, realistic typing, mouse movement)
- CAPTCHA detection and handling

### Database (`api/database.py`)
Tables:
- `users` - Authentication
- `profiles` - User information for applications
- `resumes` - Uploaded resumes with parsed data
- `applications` - Application history
- `user_settings` - Rate limits, encrypted cookies
- `jobs_cache` - Temporary job search results

## Common Development Tasks

### Adding a New Platform Adapter
1. Create `adapters/newplatform.py`
2. Inherit from `JobPlatformAdapter`
3. Implement required abstract methods
4. Add to `ADAPTERS` dict in `adapters/__init__.py`
5. Add URL patterns to `PLATFORM_PATTERNS`
6. Add tests in `tests/e2e/`

### Modifying AI Prompts
1. Edit prompts in `ai/kimi_service.py`
2. Ensure safety constraints remain in place
3. Run `pytest -m safety` to verify
4. Document any new output formats

### Adding API Endpoints
1. Add Pydantic model for request validation
2. Implement endpoint in `api/main.py`
3. Use `get_current_user` dependency for auth
4. Add appropriate HTTP status codes
5. Log important actions via `logger` or `log_application()`

### Database Schema Changes
1. Modify `init_database()` in `api/database.py`
2. Add migration logic if needed (SQLite ALTER TABLE limitations)
3. Update related CRUD functions
4. Test with fresh and existing databases

## External Dependencies

### Required Services
- **Moonshot AI** (Kimi): Resume parsing, tailoring, cover letters
- **BrowserBase**: Cloud browser sessions for automation

### Optional Services
- **Cloudflare**: Workers proxy, Pages hosting
- **Fly.io**: Primary backend hosting

## Notes for AI Agents

1. **Never modify test logic** - Tests verify safety constraints (hallucination prevention, rate limits). Fix code to pass tests, not vice versa.

2. **Preserve safety prompts** - AI service prompts contain critical constraints preventing fabrication. Do not remove "DO NOT invent" language.

3. **Maintain adapter interface** - All platform adapters must conform to `JobPlatformAdapter` abstract base class.

4. **Use existing patterns** - Follow the established patterns for:
   - Configuration (AppConfig dataclass)
   - Database (async context managers)
   - Authentication (JWT dependency injection)
   - Logging (structured with context)

5. **Security first** - Any changes to auth, file handling, or user data must preserve existing security measures:
   - Input validation via Pydantic
   - File extension and size limits
   - Path traversal prevention
   - Sensitive data encryption

6. **Documentation language** - All code comments and documentation are in English. The frontend UI is also in English.
