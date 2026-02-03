# Kevin Beltran - 1000 Job Campaign

## Campaign Overview

| Attribute | Value |
|-----------|-------|
| **Campaign ID** | kevin_beltran_servicenow_1000_2026 |
| **Candidate** | Kevin Beltran |
| **Location** | Atlanta, GA |
| **Target** | 1000 job applications |
| **Session Limit** | 1000 |
| **Concurrent Browsers** | 50 |
| **Min Salary** | $85,000 |
| **Focus** | Remote contract roles |

## Contact Information

- **Email:** beltranrkevin@gmail.com
- **Phone:** 770-378-2545
- **LinkedIn:** (to be added)

## Target Roles

1. ServiceNow Business Analyst
2. ServiceNow Consultant
3. ServiceNow Administrator
4. ITSM Consultant
5. ITSM Analyst
6. ServiceNow Reporting Specialist
7. ServiceNow Analyst
8. Customer Success Manager
9. Technical Business Analyst
10. Federal ServiceNow Analyst

## Search Criteria

- **Locations:** Remote, Atlanta GA, Georgia, United States, CONUS
- **Work Types:** Remote, Hybrid
- **Platforms:** LinkedIn, Indeed, ClearanceJobs, Greenhouse, Lever, Workday
- **Keywords:** ServiceNow, ITSM, ITIL, reporting, federal, VA, customer success, CSA, business analyst, consultant

## Campaign Configuration

```json
{
  "max_applications_per_day": 1000,
  "max_total_applications": 1000,
  "concurrent_applications": 50,
  "min_delay_seconds": 30,
  "max_delay_seconds": 90,
  "auto_submit": false,
  "generate_cover_letter": true
}
```

## How to Run

### Option 1: Using Python directly
```bash
cd campaigns
python3 kevin_beltran_1000_campaign.py
```

### Option 2: Using the shell script
```bash
cd campaigns
./run_kevin_beltran_campaign.sh
```

## Expected Output Files

After running the campaign, the following files will be generated in this directory:

| File | Description |
|------|-------------|
| `kevin_beltran_scraped_jobs.json` | All scraped job listings |
| `kevin_beltran_campaign_report.json` | Final campaign report with metrics |

## Campaign Phases

1. **Phase 1 - Job Scraping:** Scrape up to 1000 relevant ServiceNow/ITSM contract jobs
2. **Phase 2 - Applications:** Apply to jobs with 50 concurrent browser sessions
3. **Phase 3 - Reporting:** Generate comprehensive campaign report

## Estimated Runtime

- Job Scraping: ~10-15 minutes
- Applications: ~40-50 minutes (at ~25 apps/min with 50 concurrent)
- Total: ~60-70 minutes

## Notes

- Campaign targets federal contractors on ClearanceJobs (Deloitte Federal, Accenture Federal, CGI Federal, etc.)
- Session cookie configured for authentication
- Salary filter set to $85k+ minimum
- Remote roles prioritized
