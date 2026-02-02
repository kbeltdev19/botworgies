# 🚀 Job Applier

AI-powered job application automation platform with resume optimization, cover letter generation, and browser automation.

## Features

- **📄 Resume Parsing & Optimization**: Upload your resume, get it parsed and tailored for specific job descriptions
- **✨ AI Cover Letters**: Generate personalized cover letters using Kimi AI
- **🔍 Job Search**: Search LinkedIn and Indeed with advanced filters
- **⚡ Easy Apply Automation**: Automated LinkedIn Easy Apply with human-like behavior
- **🛡️ Anti-Detection**: BrowserBase stealth browsers with residential proxies
- **📊 Application Tracking**: Track all your applications in one place

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Frontend (Cloudflare Pages)         │
│                    React/HTML                    │
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────┐
│            Cloudflare Workers (API Proxy)        │
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────┐
│              FastAPI Backend                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Kimi AI  │  │ Browser  │  │  Platform    │  │
│  │ Service  │  │ Manager  │  │  Adapters    │  │
│  └──────────┘  └──────────┘  └──────────────┘  │
└─────────────────────┬───────────────────────────┘
                      │
         ┌────────────┴────────────┐
         │                         │
┌────────▼────────┐    ┌──────────▼──────────┐
│  Moonshot AI    │    │    BrowserBase      │
│  (Kimi API)     │    │ (Stealth Browsers)  │
└─────────────────┘    └─────────────────────┘
```

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Node.js 18+ (for Cloudflare deployment)
- API Keys:
  - Moonshot/Kimi API key
  - BrowserBase API key & project ID

### 2. Install Dependencies

```bash
cd projects/job-applier
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure Environment

Add to `~/.clawdbot/secrets/tokens.env`:
```
MOONSHOT_API_KEY=your_key_here
BROWSERBASE_API_KEY=bb_live_xxx
BROWSERBASE_PROJECT_ID=xxx-xxx-xxx
```

### 4. Run Backend

```bash
cd api
uvicorn main:app --reload --port 8000
```

### 5. Open Frontend

Open `frontend/index.html` in your browser, or serve it:
```bash
cd frontend
python -m http.server 3000
```

## Deployment

### Cloudflare Pages (Frontend)

```bash
npx wrangler pages deploy frontend --project-name=job-applier
```

### Cloudflare Workers (API Proxy)

```bash
npx wrangler deploy
```

### Backend Server

Deploy the Python backend to any server that can run:
- The FastAPI application
- Connect to BrowserBase (cloud browsers)
- Access Moonshot AI API

Options: Railway, Fly.io, Render, or your own VPS.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/resume/upload` | POST | Upload and parse resume |
| `/resume/tailor` | POST | Tailor resume to job description |
| `/profile` | POST | Save user profile |
| `/jobs/search` | POST | Search for jobs |
| `/apply` | POST | Apply to a job |
| `/applications` | GET | Get application history |
| `/ai/generate-cover-letter` | POST | Generate cover letter |
| `/ai/answer-question` | POST | Answer application question |

## Platform Support

| Platform | Search | Easy Apply | Status |
|----------|--------|------------|--------|
| LinkedIn | ✅ | ✅ | Supported |
| Indeed | ✅ | ✅ | Supported |
| Greenhouse | 🔜 | 🔜 | Planned |
| Workday | 🔜 | 🔜 | Planned |
| Lever | 🔜 | 🔜 | Planned |

## Safety & Ethics

- **Rate Limiting**: Configurable max applications per day
- **Human Review**: Optional approval before final submit
- **No Hallucination**: AI only rephrases existing experience, never invents
- **Audit Trail**: All applications logged with screenshots
- **Terms of Service**: Users are responsible for compliance with job platform ToS

## Project Structure

```
job-applier/
├── api/
│   └── main.py          # FastAPI backend
├── ai/
│   └── kimi_service.py  # Kimi/Moonshot integration
├── browser/
│   └── stealth_manager.py  # BrowserBase automation
├── adapters/
│   ├── base.py          # Platform adapter interface
│   └── linkedin.py      # LinkedIn adapter
├── frontend/
│   └── index.html       # Web UI
├── workers/
│   └── index.js         # Cloudflare Worker
├── wrangler.toml        # Cloudflare config
└── requirements.txt     # Python dependencies
```

## Contributing

1. Fork the repo
2. Create a feature branch
3. Make your changes
4. Submit a PR

## License

MIT
