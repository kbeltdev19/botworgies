# Universal ATS Automation System

Multi-ATS job application automation supporting Workday, Taleo, iCIMS, SuccessFactors, ADP, AngelList, and Dice.

## Supported Platforms

| Platform | Priority | Market Share | Handler |
|----------|----------|--------------|---------|
| **Workday** | 1 | 30% | ✅ Full Support |
| **Taleo** | 2 | 20% | ✅ Full Support |
| **iCIMS** | 3 | 15% | ✅ Full Support |
| **SuccessFactors** | 4 | 10% | ✅ Full Support |
| **ADP** | 5 | 5% | ✅ Full Support |
| **Greenhouse** | - | 10% | ✅ Full Support |
| **AngelList/Wellfound** | - | 5% | ✅ Full Support |
| **Dice.com** | - | Tech-focused | ✅ Full Support |

## Architecture

```
ATSController
├── BrowserBaseManager (stealth, proxies, captcha)
├── GenericFieldMapper (universal field detection)
├── Specific Handlers:
│   ├── WorkdayHandler
│   ├── TaleoHandler
│   ├── iCIMSHandler
│   ├── SuccessFactorsHandler
│   ├── ADPHandler
│   ├── AngelListHandler
│   ├── GreenhouseHandler
│   └── DiceHandler
└── ATSRouter (detection & routing)
```

## Installation

```bash
pip install browserbase playwright aiohttp beautifulsoup4
playwright install chromium
```

## Usage

### Apply to Single Job

```python
from ats_automation import ATSRouter, UserProfile

profile = UserProfile(
    first_name="Kent",
    last_name="Le",
    email="kle4311@gmail.com",
    phone="404-934-0630",
    resume_path="/path/to/resume.pdf",
    years_experience=3,
    skills=["CRM", "Salesforce", "Customer Success"]
)

router = ATSRouter(profile)
result = await router.apply("https://company.wd101.myworkdayjobs.com/job/123")

print(f"Success: {result.success}")
print(f"Platform: {result.platform.value}")
print(f"Confirmation: {result.confirmation_number}")
```

### Apply to Multiple Jobs

```python
job_urls = [
    "https://company1.wd101.myworkdayjobs.com/job/1",
    "https://company2.taleo.net/job/2",
    "https://company3.icims.com/job/3"
]

results = await router.apply_batch(job_urls, concurrent=3)

for result in results:
    print(f"{result.job_url}: {'✅' if result.success else '❌'}")
```

### Search & Apply on Dice.com

```python
# Search for jobs
results = await router.search_and_apply_dice(
    query="Customer Success Manager",
    location="Atlanta, GA",
    remote=True,
    max_jobs=10
)

print(f"Applied to {len(results)} Easy Apply jobs")
```

## API Endpoints

### Detect Platform
```bash
POST /ats/detect?url=https://company.workday.com/job/123
```

### Apply to Job
```bash
POST /ats/apply
{
  "job_url": "https://...",
  "profile": { ... },
  "ai_api_key": "optional"
}
```

### Batch Apply
```bash
POST /ats/apply/batch
{
  "job_urls": ["https://...", "https://..."],
  "profile": { ... },
  "concurrent": 3
}
```

### Dice Search & Apply
```bash
POST /ats/dice/apply
{
  "query": "Software Engineer",
  "location": "San Francisco",
  "remote": true,
  "max_jobs": 10,
  "profile": { ... }
}
```

## Features

### Universal Field Detection
The `GenericFieldMapper` automatically detects form fields across all ATS platforms:
- First/Last Name
- Email, Phone
- Resume Upload
- Cover Letter
- LinkedIn/Portfolio URLs
- Salary Expectations
- Custom Questions (with AI-generated answers)
- EEO fields (auto "Prefer not to answer")

### Anti-Detection
- BrowserBase stealth sessions
- Residential proxy rotation
- CAPTCHA solving (BrowserBase built-in)
- Human-like delays
- Randomized typing speeds

### Smart Routing
- URL pattern matching (fast)
- Content-based detection (fallback)
- Generic handler for unknown platforms

## Dice.com Integration

Special features for Dice:
- Search jobs by query/location
- Filter for Easy Apply only
- Batch apply to multiple Easy Apply jobs
- External redirect detection

```python
from ats_automation.handlers.dice import DiceHandler

# Search jobs
jobs = await dice.search_jobs(
    query="Python Developer",
    location="Remote",
    max_results=50
)

# Filter Easy Apply
easy_apply_jobs = [j for j in jobs if j.easy_apply]

# Quick batch apply
results = await dice.quick_apply_batch(easy_apply_jobs, max_applications=10)
```

## Error Handling

All handlers return `ApplicationResult` with:
- `success`: Boolean
- `platform`: ATSPlatform enum
- `status`: 'submitted', 'incomplete', 'error', 'captcha_blocked', 'external_redirect'
- `error_message`: Details on failure
- `confirmation_number`: If available

## Environment Variables

```bash
BROWSERBASE_API_KEY=bb_live_xxx
BROWSERBASE_PROJECT_ID=xxx-xxx-xxx
```

## Testing

```bash
# Test specific handler
python -c "
from ats_automation.handlers.workday import WorkdayHandler
handler = WorkdayHandler(...)
result = await handler.apply('https://...')
print(result)
"

# Run full test
pytest tests/ats_automation/
```
