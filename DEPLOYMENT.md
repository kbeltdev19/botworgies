# Deployment Guide - Job Applier Bot v2.0.0

**Release Date:** 2026-02-02  
**Version:** v2.0.0  
**Git Tag:** `v2.0.0`  
**Status:** Ready for Production Deployment

---

## 🚀 Quick Deploy

### Option 1: Fly.io (Recommended)

```bash
# 1. Install Fly CLI
curl -L https://fly.io/install.sh | sh
export FLYCTL_INSTALL="$HOME/.fly"
export PATH="$FLYCTL_INSTALL/bin:$PATH"

# 2. Login
fly auth login

# 3. Deploy
fly deploy

# 4. Check status
fly status
fly open
```

### Option 2: Docker

```bash
# Build
docker build -t job-applier .

# Run locally
docker run -p 8080:8080 \
  -e BROWSERBASE_API_KEY=bb_live_xxx \
  -e BROWSERBASE_PROJECT_ID=c47b2ef9-00fa-4b16-9cc6-e74e5288e03c \
  -e MOONSHOT_API_KEY=your_key_here \
  job-applier

# Or use docker-compose
docker-compose up -d
```

### Option 3: Manual (Development)

```bash
# Setup Python 3.11
pyenv install 3.11.9
pyenv global 3.11.9

# Install dependencies
pip3 install -r requirements.txt
pip3 install jobspy pandas aiohttp browserbase playwright
python3 -m playwright install chromium

# Start API
cd api && uvicorn main:app --host 0.0.0.0 --port 8080
```

---

## 📦 Release Assets

### What's Included

| Component | Location | Status |
|-----------|----------|--------|
| **Backend API** | `api/` | ✅ Production Ready |
| **Frontend** | `frontend/index.html` | ✅ Static site |
| **Browser Automation** | `browser/` | ✅ BrowserBase integrated |
| **Job Scraping** | `adapters/jobspy_scraper.py` | ✅ JobSpy integrated |
| **CAPTCHA Solving** | `api/captcha_solver.py` | ⚠️ Needs API key |
| **Retry Logic** | `api/form_retry_handler.py` | ✅ Active |
| **A/B Testing** | `api/ab_testing.py` | ✅ Active |
| **Proxy Manager** | `api/proxy_manager.py` | ✅ Active |
| **Campaign Runner** | `campaigns/` | ✅ Ready |

---

## 🔧 Environment Variables

### Required
```bash
# BrowserBase (Already configured)
BROWSERBASE_API_KEY=bb_live_xxx
BROWSERBASE_PROJECT_ID=c47b2ef9-00fa-4b16-9cc6-e74e5288e03c

# Moonshot AI (Required for resume parsing)
MOONSHOT_API_KEY=your_key_here

# Database
DATABASE_PATH=./data/job_applier.db
DATA_DIR=./data
```

### Optional (For Full Features)
```bash
# CAPTCHA Solving (Recommended for production)
CAPSOLVER_API_KEY=your_key_here
# OR
TWOCAPTCHA_API_KEY=your_key_here

# Residential Proxies (Recommended for scale)
BRIGHTDATA_USERNAME=your_username
BRIGHTDATA_PASSWORD=your_password
# OR
OXYLABS_USERNAME=your_username
OXYLABS_PASSWORD=your_password

# Security
JWT_SECRET_KEY=your_secret_key
ADMIN_KEY=your_admin_key
```

---

## 🌐 Deployment Endpoints

### After Deployment

| Service | URL | Purpose |
|---------|-----|---------|
| **API** | `https://your-app.fly.dev` | Main API |
| **Health** | `/health` | Status check |
| **Docs** | `/docs` | API documentation (if DEBUG=true) |
| **Frontend** | `https://your-frontend.pages.dev` | User interface |

---

## 📊 Scaling Configuration

### Current Limits (Fly.io)
```toml
# fly.toml
[vm]
memory = '1024mb'
cpu_kind = 'shared'
cpus = 1

# Scale up for production
fly scale vm dedicated-cpu-1x --memory 2048
fly scale count 2  # Run 2 instances
```

### BrowserBase Limits
- **Free Tier:** 100 concurrent sessions
- **Pro Tier:** 500+ concurrent sessions
- **Current:** Using 100 sessions (configured)

### Rate Limits
- Default: 60 applications/minute
- Max: 1000 applications/day per user
- Can be configured per campaign

---

## 🧪 Pre-Flight Checklist

Before going live:

- [ ] `fly deploy` succeeds without errors
- [ ] Health check returns `{"status": "healthy"}`
- [ ] Can upload resume via frontend
- [ ] Can search jobs (JobSpy working)
- [ ] Browser sessions create successfully
- [ ] Database migrations run (auto)
- [ ] API key secrets set in Fly
- [ ] Frontend deployed to CDN
- [ ] SSL certificates active

---

## 🔐 Security Checklist

- [ ] JWT_SECRET_KEY is random and secure
- [ ] API keys not in code (use `fly secrets`)
- [ ] Database encrypted at rest
- [ ] CORS configured for production domain
- [ ] Rate limiting enabled
- [ ] No debug mode in production
- [ ] Access logs enabled

---

## 📈 Monitoring

### Logs
```bash
# View live logs
fly logs

# View specific app
fly logs --app job-applier-api
```

### Metrics
- Check `/health` endpoint
- Monitor BrowserBase dashboard
- Track success rates in campaign reports

### Alerts (Set up in Fly.io)
- High error rate (>10%)
- Low success rate (<70%)
- BrowserBase session failures
- API downtime

---

## 🔄 Database Migrations

SQLite migrations are automatic on startup. To reset:

```bash
# Backup first
fly ssh console -C "cp /app/data/job_applier.db /app/data/backup.db"

# Reset (DANGER - deletes all data)
fly ssh console -C "rm /app/data/job_applier.db"
```

---

## 🚀 Production Deployment Steps

### Step 1: Set Secrets
```bash
fly secrets set MOONSHOT_API_KEY=your_key
fly secrets set CAPSOLVER_API_KEY=your_key  # Optional
fly secrets set JWT_SECRET_KEY=$(openssl rand -hex 32)
```

### Step 2: Deploy
```bash
fly deploy --strategy rolling
```

### Step 3: Verify
```bash
fly status
curl https://your-app.fly.dev/health
```

### Step 4: Deploy Frontend
```bash
cd frontend
# Using Cloudflare Pages
npx wrangler pages deploy . --project-name=job-applier-ui

# Or using surge.sh
npx surge . job-applier-ui.surge.sh
```

---

## 🐛 Troubleshooting

### "No access token available"
```bash
fly auth login
```

### "Memory quota exceeded"
```bash
fly scale memory 2048
```

### "Database locked"
SQLite doesn't support concurrent writes well. Use WAL mode (already configured).

### "Browser sessions failing"
Check BrowserBase dashboard:
- Session limits reached?
- API key valid?
- Project ID correct?

---

## 📞 Support

### Resources
- **Fly Docs:** https://fly.io/docs
- **BrowserBase:** https://docs.browserbase.com
- **JobSpy:** https://github.com/speedyapply/JobSpy
- **GitHub Issues:** https://github.com/kbeltdev19/botworgies/issues

### Current Configuration
- **App Name:** `job-applier-api`
- **Region:** `ord` (Chicago)
- **Database:** SQLite (persistent volume)
- **Sessions:** 100 concurrent BrowserBase

---

## ✅ Release Verification

After deployment, verify:

```bash
# 1. API is up
curl https://your-app.fly.dev/health

# 2. Can upload resume
curl -X POST https://your-app.fly.dev/resume/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.pdf"

# 3. Can search jobs
curl -X POST https://your-app.fly.dev/jobs/search \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"roles": ["Customer Success Manager"], "locations": ["Remote"]}'

# 4. Browser works
python3 -c "
import requests
resp = requests.get('https://your-app.fly.dev/health')
print(f'Browser available: {resp.json()[\"browser_available\"]}')
"
```

---

## 🎉 You're Live!

Once deployed:
1. Share the frontend URL with users
2. Monitor logs for issues
3. Run first test campaign (10 jobs)
4. Scale up based on success

**Version 2.0.0 is ready for production! 🚀**
