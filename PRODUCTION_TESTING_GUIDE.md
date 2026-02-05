# Production Testing Guide - Real Applications with Monitoring

> Submit REAL job applications with comprehensive monitoring and iteration.

---

## 🚀 Quick Start

### 1. Set Up Environment

```bash
# Create necessary directories
mkdir -p logs/evidence data

# Set your information
export APPLICANT_FIRST_NAME="Your"
export APPLICANT_LAST_NAME="Name"
export APPLICANT_EMAIL="your.email@example.com"
export APPLICANT_PHONE="555-123-4567"
export APPLICANT_LINKEDIN="https://linkedin.com/in/yourprofile"
export APPLICANT_YEARS_EXP="5"
export APPLICANT_SALARY="$100,000 - $130,000"

# Set your resume path
export RESUME_PATH="/path/to/your/resume.pdf"

# Set real job URLs (find actual job postings)
export PRODUCTION_GREENHOUSE_URL="https://boards.greenhouse.io/company/jobs/1234567"
export PRODUCTION_LEVER_URL="https://jobs.lever.co/company/abc-def-123"
export PRODUCTION_LINKEDIN_URL="https://www.linkedin.com/jobs/view/1234567890"
export LINKEDIN_LI_AT="your_li_at_cookie"
```

### 2. Run Single Application

```bash
# Test one application
pytest tests/e2e/test_production_applications.py::TestProductionGreenhouse::test_greenhouse_production_application -v
```

### 3. Check Results

```bash
# View status
python scripts/check_applications.py status

# View daily report
python scripts/check_applications.py report

# View failures
python scripts/check_applications.py failures --hours 24

# Analyze specific application
python scripts/check_applications.py analyze gh_prod_20240205_120000
```

---

## 📊 Monitoring System

### What's Tracked

Every application submission is monitored:

```python
{
    "application_id": "gh_prod_20240205_120000",
    "platform": "greenhouse",
    "job_url": "https://boards.greenhouse.io/...",
    "start_time": "2024-02-05T12:00:00",
    "end_time": "2024-02-05T12:00:45",
    "duration_seconds": 45.2,
    "steps_completed": 3,
    "fields_filled": 8,
    "questions_answered": 2,
    "screenshots_count": 5,
    "success": True,
    "confirmation_id": "ABC-123-456",
    "final_status": "submitted"
}
```

### Event Log

Every action is logged:

```
[2024-02-05 12:00:00] STARTED: Starting application to greenhouse
[2024-02-05 12:00:02] NAVIGATING: Loading job page
[2024-02-05 12:00:05] FIELD_FILLED: first_name = "Your"
[2024-02-05 12:00:06] FIELD_FILLED: last_name = "Name"
[2024-02-05 12:00:10] FILE_UPLOADED: resume.pdf (150KB)
[2024-02-05 12:00:15] QUESTION_ANSWERED: "How many years experience?" = "5"
[2024-02-05 12:00:20] SCREENSHOT: review_step.png
[2024-02-05 12:00:25] SUBMIT_ATTEMPTED: Submit button clicked
[2024-02-05 12:00:30] SUBMIT_SUCCESS: Application submitted
[2024-02-05 12:00:30] CONFIRMATION_FOUND: ABC-123-456
```

### Evidence Collection

Screenshots saved to `logs/evidence/`:
- `initial.png` - Page load
- `form_filled.png` - After filling
- `review.png` - Before submit
- `success.png` - Confirmation page
- `error.png` - If failure occurs

---

## 🔁 Iteration System

When applications fail, the system analyzes and suggests improvements:

### Failure Analysis

```python
# Example: Selector not found
{
    "pattern": "selector_not_found",
    "confidence": 0.85,
    "root_cause": "Submit button selector outdated",
    "suggested_fix": "Add alternative selectors and increase wait time",
    "adjustments": [
        {
            "parameter": "pre_selector_wait",
            "new_value": 3.0,
            "reason": "Element may need more time to appear"
        },
        {
            "parameter": "fallback_count",
            "new_value": 5,
            "reason": "Primary selector may have changed"
        }
    ]
}
```

### Learned Strategies

Platform-specific strategies are learned over time:

```python
# Greenhouse strategy after 10 attempts
greenhouse_strategy = {
    "wait_times": {
        "pre_selector": 2.5,      # Increased from 2.0
        "post_action": 1.0,
        "post_submit": 7.0,       # Increased from 5.0
    },
    "selector_strategy": {
        "fallback_count": 4,       # Increased from 3
        "retry_attempts": 3,
    },
    "interaction": {
        "scroll_before_click": True,  # Learned from failures
    }
}
```

---

## 📈 Success Metrics

### View Platform Performance

```bash
python scripts/check_applications.py status
```

Output:
```
Platform Success Rates:
----------------------------------------------------------------------
Platform        Attempts   Success    Failed     Rate
----------------------------------------------------------------------
greenhouse      15         13         2          86.7%
lever           10         8          2          80.0%
linkedin        5          2          3          40.0%
workday         3          0          3           0.0%
----------------------------------------------------------------------

⚠️  Recent Failures (24h): 2
   • linkedin: CAPTCHA detected
   • workday: Form timeout
```

### Daily Report

```bash
python scripts/check_applications.py report
```

Shows:
- Total applications today
- Success/failure counts
- Platform breakdown
- Recent errors
- Suggested improvements

---

## 🛠️ Troubleshooting

### Application Failed

1. **Check logs**
   ```bash
   tail -f logs/applications.log
   ```

2. **View evidence**
   ```bash
   ls logs/evidence/*failed_application_id*
   ```

3. **Analyze failure**
   ```bash
   python scripts/check_applications.py analyze <application_id>
   ```

4. **Get iteration suggestions**
   ```bash
   python scripts/check_applications.py iteration
   ```

### Common Issues

| Issue | Solution |
|-------|----------|
| Selector not found | Wait longer, add fallbacks |
| CAPTCHA detected | Manual review mode, use CapSolver |
| Timeout | Increase timeout, check network |
| Upload failed | Verify file exists, check size |
| Confirmation not found | Wait longer after submit |

---

## 🔄 Batch Processing

### Run Multiple Applications

```bash
# Set multiple URLs (comma-separated)
export PRODUCTION_GREENHOUSE_URL="url1,url2,url3"
export BATCH_SIZE=5
export RUN_BATCH_PRODUCTION=true

# Run batch
pytest tests/e2e/test_production_applications.py::test_batch_production_applications -v
```

### Batch Results

```
======================================================================
BATCH COMPLETE
======================================================================
Total: 10
Successful: 8
Failed: 2
Success Rate: 80.0%
======================================================================
```

---

## 📝 Best Practices

### 1. Start Small
- Test 1-2 applications first
- Verify screenshots look correct
- Check confirmation emails
- Scale up gradually

### 2. Monitor Closely
```bash
# Watch logs in real-time
tail -f logs/applications.log | grep ERROR

# Check status every hour
watch -n 3600 'python scripts/check_applications.py status'
```

### 3. Iterate on Failures
- Analyze every failure
- Apply suggested fixes
- Test fixed version
- Document what works

### 4. Rate Limiting
- Don't submit too fast
- Respect platform limits
- Use delays between apps
- Monitor for warnings

---

## 🎯 Expected Success Rates

After iteration and tuning:

| Platform | Target Success Rate |
|----------|-------------------|
| Greenhouse | 85-90% |
| Lever | 80-85% |
| Ashby | 75-80% |
| LinkedIn | 50-60% |
| Workday | 40-50% |

---

## 📁 File Structure

```
logs/
├── applications.log          # Detailed event log
├── evidence/                 # Screenshots
│   ├── gh_prod_*.png
│   ├── lv_prod_*.png
│   └── ...
├── daily_report.txt         # Generated reports
└── *.har                    # Network logs

data/
├── application_monitor.db   # SQLite database
└── ...

monitoring/
├── application_monitor.py   # Monitoring system
└── iteration_engine.py      # Failure analysis

scripts/
└── check_applications.py    # CLI tool

tests/e2e/
└── test_production_applications.py  # Production tests
```

---

## 🔐 Safety

### Information Protection
- Resume path is logged but content isn't
- Personal info redacted in logs
- Screenshots saved locally only
- Database is local SQLite

### Platform Safety
- Respects rate limits
- Uses human-like delays
- Realistic user agents
- Proxy rotation available

---

## 🚀 Next Steps

1. **Set up your environment variables**
2. **Find 2-3 real job postings** to test
3. **Run single application test**
4. **Check screenshots** in logs/evidence/
5. **Verify application** in company portal
6. **Scale up** to more jobs
7. **Monitor and iterate**

---

**Ready to submit real applications? Set your environment variables and run:**

```bash
pytest tests/e2e/test_production_applications.py -v
```
