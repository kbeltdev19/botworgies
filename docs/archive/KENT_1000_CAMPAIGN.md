# Kent Le - 1000 Applications Campaign

## 🎯 Campaign Overview

**Candidate:** Kent Le  
**Location:** Auburn, AL (Open to Remote/Hybrid/In-person)  
**Target Salary:** $75,000+  
**Target Roles:** Customer Success, Account Management, Sales, Business Development  
**Campaign Goal:** 1,000 successful job applications

---

## 🚀 Quick Start

### Option 1: Unified Campaign Runner (Recommended - Fastest)

Uses 3-phase hybrid scraping (JobSpy → BrowserBase → Direct APIs) for maximum speed:

```bash
# Run complete campaign with BrowserBase integration
python3 -m campaigns run --profile campaigns/profiles/kent_le.yaml --limit 1000
```

**Performance:** ~100 jobs/minute with BrowserBase, ~1.1 jobs/second sustained

### Option 2: Legacy Full Automated Campaign

```bash
# Run complete campaign: collect jobs + apply
python campaigns/kent_1000_run.py 1000
```

### Option 3: Step-by-Step

```bash
# Step 1: Collect 1000 jobs
python campaigns/kent_batch_apply.py 1000

# Step 2: Apply to collected jobs
python campaigns/kent_apply_to_jobs.py output/kent_batch_1000_TIMESTAMP/jobs_to_apply.json
```

### Option 4: Dry Run (Test First)

```bash
# Collect jobs but don't apply
python3 -m campaigns run --profile campaigns/profiles/kent_le.yaml --limit 100 --dry-run
```

---

## 📁 Campaign Files

| File | Purpose |
|------|---------|
| `campaigns/kent_1000_run.py` | Main orchestrator - runs full campaign |
| `campaigns/kent_batch_apply.py` | Job collection and prioritization |
| `campaigns/kent_apply_to_jobs.py` | Automated application runner |
| `campaigns/kent_1000_auto_campaign.py` | Advanced campaign with full features |

---

## 📊 Expected Results

| Metric | Target | Notes |
|--------|--------|-------|
| Jobs Discovered | 2,000+ | From Indeed, LinkedIn, ZipRecruiter |
| Applications Sent | 1,000 | Automated submissions |
| Success Rate | 60-75% | Based on platform and job type |
| Time Required | 2-4 hours | With BrowserBase optimization |
| Easy Apply Jobs | ~30% | Higher success rate |

### BrowserBase Integration (New!)

The unified campaign runner now includes **BrowserBase** for reliable job scraping:

| Phase | Method | Speed | Reliability |
|-------|--------|-------|-------------|
| Phase 1 | JobSpy (HTTP) | Fast | Limited by network |
| Phase 2 | BrowserBase | Medium | High (stealth browsing) |
| Phase 3 | Direct APIs | Fast | Limited (rate limits) |

**Tested Performance:**
- 100 jobs: ~90 seconds (BrowserBase primary)
- 1000 jobs: ~15-20 minutes estimated
- Handles anti-bot protection automatically

---

## 🎯 Job Search Strategy

### Primary Targets (High Priority)
1. **Customer Success Manager** - Remote, Atlanta
2. **Account Manager** - Remote, Atlanta, Columbus
3. **Client Success Manager** - Remote

### Secondary Targets
4. **Account Executive** - Remote, Atlanta
5. **Sales Representative** - Remote, Auburn
6. **Business Development Rep** - Remote

### Local/Regional
7. Account Manager - Columbus, GA
8. Sales Rep - Auburn, AL
9. Customer Success - Birmingham, AL

---

## 💰 Salary Targets

Jobs are prioritized by salary:
- **Tier 1:** $90k+ (Highest priority)
- **Tier 2:** $75k-$90k (Target range)
- **Tier 3:** $60k-$75k (Acceptable for growth)
- **Tier 4:** Commission-based (High potential)

---

## ⚡ Rate Limiting & Safety

The campaign includes:
- 3-8 second delays between applications
- Random delays to appear human
- Automatic retry on failures
- Browser session rotation
- Progress saving every 50 jobs

---

## 📈 Progress Tracking

During the campaign, you'll see:
```
📊 PROGRESS: 150/1000 | Success: 89 (59.3%)
```

Results are saved to:
- `application_results.json` - Detailed results
- `jobs_to_apply.csv` - Job list with status
- `campaign_progress.json` - Real-time stats

---

## 🔄 Resuming a Campaign

If interrupted, resume with:
```bash
# Use existing jobs file
python campaigns/kent_1000_run.py 1000 --skip-collect --jobs-file output/PREVIOUS/jobs_to_apply.json
```

---

## 📋 Post-Campaign Actions

After 1000 applications:

1. **Review Results**
   ```bash
   cat output/kent_1000_*/application_results.json
   ```

2. **Manual Follow-up**
   - Apply to "external" jobs manually
   - Send LinkedIn connection requests
   - Follow up after 1 week

3. **Track Responses**
   - Update spreadsheet with responses
   - Schedule interviews
   - Negotiate offers

---

## 🛠️ Troubleshooting

### Campaign Stops Unexpectedly
```bash
# Resume from last save
python campaigns/kent_apply_to_jobs.py output/LATEST/jobs_to_apply.json
```

### Rate Limited
- Increase delays in `kent_apply_to_jobs.py`
- Use residential proxies
- Reduce concurrent sessions

### Browser Issues
```bash
# Reinstall playwright
playwright install chromium
```

---

## 📞 Kent's Profile

```yaml
Name: Kent Le
Email: kle4311@gmail.com
Phone: (404) 934-0630
Location: Auburn, AL
LinkedIn: https://linkedin.com/in/kent-le

Experience: 3+ years customer-facing
Skills: CRM, Salesforce, Data Analysis, Bilingual (Vietnamese/English)
Target: $75,000 - $95,000
Start: 2 weeks notice
```

---

## 🎉 Expected Outcome

With 1000 applications:
- **20-40 callbacks** (2-4% response rate)
- **10-20 phone screens**
- **5-10 interviews**
- **2-5 offers**

**Good luck, Kent! 🚀**
