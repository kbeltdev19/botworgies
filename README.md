# Job Applier Bot 🚀

Automated job application system with multi-platform scraping and intelligent form filling.

## Features

- **Multi-Platform Job Scraping**
  - LinkedIn (public listings)
  - Greenhouse API (100+ companies)
  - HN Jobs (Who is Hiring threads)
  - Lever, Ashby (coming soon)

- **Automated Applications**
  - Form auto-fill for Greenhouse jobs
  - LinkedIn Easy Apply (requires `li_at` cookie)
  - Resume upload and profile mapping

- **Campaign Management**
  - Create candidate profiles
  - Track application status
  - Batch processing with rate limiting

## Quick Start

### 1. Deploy to Fly.io

```bash
# Install Fly CLI
curl -L https://fly.io/install.sh | sh

# Login and deploy
fly auth login
fly deploy
```

### 2. Set Environment Variables

```bash
fly secrets set MOONSHOT_API_KEY=your_key
fly secrets set JWT_SECRET=your_secret
```

### 3. Create a Campaign

```bash
# POST /auth/register - Create account
curl -X POST https://job-applier-api.fly.dev/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@email.com","password":"pass123"}'

# POST /auth/login - Get token
curl -X POST https://job-applier-api.fly.dev/auth/login \
  -d "username=you@email.com&password=pass123"

# POST /jobs/search - Find jobs
curl -X POST https://job-applier-api.fly.dev/jobs/search \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"software engineer","location":"remote","limit":50}'
```

## Local Development

```bash
# Clone and setup
git clone https://github.com/kbeltdev19/botworgies.git
cd botworgies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Run API
uvicorn api.main:app --reload --port 8000

# Run batch applications
python -c "from campaigns.runner import run_campaign; run_campaign('matt_edwards.json')"
```

## Campaign Configuration

Create a JSON file in `campaigns/`:

```json
{
  "campaign_id": "your_campaign",
  "candidate": {
    "name": "John Doe",
    "email": "john@email.com",
    "linkedin": "https://linkedin.com/in/johndoe"
  },
  "resume_path": "data/resume.pdf",
  "search_criteria": {
    "roles": ["software engineer", "backend developer"],
    "locations": ["Remote", "San Francisco"],
    "salary_min": 100000,
    "easy_apply_only": true
  },
  "application_settings": {
    "max_applications_per_day": 50,
    "max_total_applications": 200
  }
}
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/auth/register` | POST | Create account |
| `/auth/login` | POST | Get JWT token |
| `/jobs/search` | POST | Search jobs |
| `/apply` | POST | Apply to single job |
| `/apply/batch` | POST | Batch applications |
| `/resume/upload` | POST | Upload resume |
| `/applications` | GET | List applications |

## Platforms Supported

| Platform | Search | Apply | Notes |
|----------|--------|-------|-------|
| LinkedIn | ✅ Public | ⚠️ Needs cookie | `li_at` required for Easy Apply |
| Greenhouse | ✅ API | ✅ Auto-fill | 100+ companies |
| HN Jobs | ✅ Algolia | ❌ External | Links to company sites |
| Lever | 🔄 WIP | 🔄 WIP | API format changed |

## Architecture

```
┌─────────────────┐     ┌──────────────────┐
│   Campaign      │────▶│  Job Scraper     │
│   Config        │     │  (Multi-source)  │
└─────────────────┘     └────────┬─────────┘
                                 │
                                 ▼
┌─────────────────┐     ┌──────────────────┐
│   Application   │◀────│  Job Queue       │
│   Pipeline      │     │  (Deduplicated)  │
└────────┬────────┘     └──────────────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│   Browser       │────▶│  Form Filler     │
│   (Playwright)  │     │  (Auto-detect)   │
└─────────────────┘     └──────────────────┘
```

## Rate Limits

To avoid bans, the bot enforces:

- 30-90 second delay between applications
- Max 50 applications per day per platform
- Human-like mouse movements and typing
- Session rotation for high-volume

## License

MIT
