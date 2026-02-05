"""
Test Job URLs Configuration

This file contains ACTUAL job board URLs for E2E testing.

⚠️  IMPORTANT SAFETY GUIDELINES:

1. ONLY use test/demo job postings
2. NEVER apply to real jobs you don't want
3. Use unique email addresses for testing
4. Check the "auto_submit" setting before running
5. Respect rate limits - don't spam applications

Where to Find Test Jobs:
- Greenhouse: Many companies have "Test" or "Demo" positions
- Lever: Some boards have "Sample" or "Example" jobs
- LinkedIn: Look for "Easy Apply" test positions
- Workday: Some companies have sandbox/test instances

How to Add Your Own Test URLs:
1. Find a test job posting (contact company if unsure)
2. Copy the full job URL
3. Add it below in the appropriate section
4. Set RUN_LIVE_SUBMISSION_TESTS=true
5. Run with auto_submit=False first to verify
"""

import os
from typing import Optional, Dict, List
from dataclasses import dataclass


@dataclass
class TestJob:
    """Represents a test job configuration."""
    name: str
    url: str
    platform: str
    expected_fields: List[str]
    notes: str
    is_active: bool = True


# ============================================================================
# GREENHOUSE TEST JOBS
# ============================================================================
#
# Greenhouse boards often have test positions. Look for:
# - URLs containing "boards.greenhouse.io"
# - Job titles like "Test Position", "Demo Role", "Sample Job"
# - Engineering demo boards
#
GREENHOUSE_TEST_JOBS = [
    TestJob(
        name="Example Greenhouse Test",
        url=os.getenv("GREENHOUSE_TEST_URL", ""),
        platform="greenhouse",
        expected_fields=["first_name", "last_name", "email", "phone", "resume"],
        notes="Set GREENHOUSE_TEST_URL env var with your test job URL"
    ),
    # Add your actual test jobs here:
    # TestJob(
    #     name="Your Company Test",
    #     url="https://boards.greenhouse.io/yourcompany/jobs/1234567",
    #     platform="greenhouse",
    #     expected_fields=["first_name", "last_name", "email", "resume"],
    #     notes="Test position for QA"
    # ),
]


# ============================================================================
# LEVER TEST JOBS
# ============================================================================
#
# Lever boards may have test positions at:
# - jobs.lever.co/{company}/{job-id}
# - Look for "Test", "Demo", or "Sample" in title
#
LEVER_TEST_JOBS = [
    TestJob(
        name="Example Lever Test",
        url=os.getenv("LEVER_TEST_URL", ""),
        platform="lever",
        expected_fields=["name", "email", "resume"],
        notes="Set LEVER_TEST_URL env var with your test job URL"
    ),
    # Add your actual test jobs here:
    # TestJob(
    #     name="Your Company Test",
    #     url="https://jobs.lever.co/yourcompany/abc-123-def",
    #     platform="lever",
    #     expected_fields=["name", "email", "resume", "phone"],
    #     notes="Test position"
    # ),
]


# ============================================================================
# LINKEDIN TEST JOBS
# ============================================================================
#
# LinkedIn Easy Apply test jobs:
# - Search "test engineer easy apply"
# - Look for "Actively recruiting" with Easy Apply button
# - URL format: linkedin.com/jobs/view/{job-id}
#
# ⚠️  LinkedIn has strict anti-bot detection. Use sparingly.
#
LINKEDIN_TEST_JOBS = [
    TestJob(
        name="Example LinkedIn Test",
        url=os.getenv("LINKEDIN_TEST_JOB_URL", ""),
        platform="linkedin",
        expected_fields=["first_name", "last_name", "email", "phone", "resume"],
        notes="Set LINKEDIN_TEST_JOB_URL env var. Requires LINKEDIN_LI_AT cookie."
    ),
    # Add your actual test jobs here:
    # TestJob(
    #     name="LinkedIn Test Job",
    #     url="https://www.linkedin.com/jobs/view/1234567890",
    #     platform="linkedin",
    #     expected_fields=["first_name", "last_name", "email", "phone", "resume"],
    #     notes="Easy Apply test position"
    # ),
]


# ============================================================================
# WORKDAY TEST JOBS
# ============================================================================
#
# Workday test positions are harder to find. Look for:
# - Company career pages with "test" or "sandbox" in URL
# - URLs like: {company}.wd5.myworkdayjobs.com
# - Some companies maintain test instances
#
WORKDAY_TEST_JOBS = [
    TestJob(
        name="Example Workday Test",
        url=os.getenv("WORKDAY_TEST_URL", ""),
        platform="workday",
        expected_fields=["firstName", "lastName", "email", "phone"],
        notes="Set WORKDAY_TEST_URL env var. Workday forms are complex."
    ),
    # Add your actual test jobs here:
    # TestJob(
    #     name="Enterprise Test",
    #     url="https://company.wd5.myworkdayjobs.com/External/job/Job-Title_12345",
    #     platform="workday",
    #     expected_fields=["firstName", "lastName", "email", "phone", "resume"],
    #     notes="Test position in Workday sandbox"
    # ),
]


# ============================================================================
# ASHBY TEST JOBS
# ============================================================================
#
# Ashby boards:
# - jobs.ashbyhq.com/{company}/{job-id}
# - Modern ATS, consistent form structure
#
ASHBY_TEST_JOBS = [
    TestJob(
        name="Example Ashby Test",
        url=os.getenv("ASHBY_TEST_URL", ""),
        platform="ashby",
        expected_fields=["firstName", "lastName", "email", "resume"],
        notes="Set ASHBY_TEST_URL env var"
    ),
]


# ============================================================================
# URL HELPER FUNCTIONS
# ============================================================================

def get_test_jobs(platform: Optional[str] = None) -> List[TestJob]:
    """
    Get all test jobs or filter by platform.
    
    Args:
        platform: Optional filter by platform name
        
    Returns:
        List of TestJob objects with URLs set
    """
    all_jobs = (
        GREENHOUSE_TEST_JOBS +
        LEVER_TEST_JOBS +
        LINKEDIN_TEST_JOBS +
        WORKDAY_TEST_JOBS +
        ASHBY_TEST_JOBS
    )
    
    # Filter to only jobs with actual URLs set
    active_jobs = [job for job in all_jobs if job.url and job.is_active]
    
    if platform:
        active_jobs = [job for job in active_jobs if job.platform == platform]
    
    return active_jobs


def get_first_available_job(platform: str) -> Optional[TestJob]:
    """Get the first available test job for a platform."""
    jobs = get_test_jobs(platform)
    return jobs[0] if jobs else None


def validate_test_jobs() -> Dict[str, List[str]]:
    """
    Validate that test jobs are configured.
    
    Returns:
        Dict with 'valid' and 'missing' lists
    """
    all_jobs = (
        GREENHOUSE_TEST_JOBS +
        LEVER_TEST_JOBS +
        LINKEDIN_TEST_JOBS +
        WORKDAY_TEST_JOBS +
        ASHBY_TEST_JOBS
    )
    
    result = {
        "valid": [],
        "missing": [],
        "by_platform": {}
    }
    
    for job in all_jobs:
        if job.url:
            result["valid"].append(f"{job.platform}: {job.name}")
            result["by_platform"][job.platform] = job.url
        else:
            result["missing"].append(f"{job.platform}: {job.name} - {job.notes}")
    
    return result


def print_test_job_status():
    """Print current status of test job configuration."""
    status = validate_test_jobs()
    
    print("\n" + "="*70)
    print("TEST JOB URL CONFIGURATION STATUS")
    print("="*70)
    
    if status["valid"]:
        print("\n✅ Configured Test Jobs:")
        for job in status["valid"]:
            print(f"   • {job}")
    
    if status["missing"]:
        print("\n⚠️  Missing Test Jobs (Set environment variables):")
        for job in status["missing"]:
            print(f"   • {job}")
    
    if not status["valid"] and not status["missing"]:
        print("\n❌ No test jobs configured.")
        print("   Set environment variables or edit tests/e2e/test_job_urls.py")
    
    print("\n" + "="*70)
    print("HOW TO CONFIGURE:")
    print("="*70)
    print("""
Option 1: Environment Variables (Recommended)
---------------------------------------------
export GREENHOUSE_TEST_URL="https://boards.greenhouse.io/..."
export LEVER_TEST_URL="https://jobs.lever.co/..."
export LINKEDIN_TEST_JOB_URL="https://www.linkedin.com/jobs/view/..."
export LINKEDIN_LI_AT="your_li_at_cookie"
export WORKDAY_TEST_URL="https://company.wd5.myworkdayjobs.com/..."

Option 2: Edit Configuration File
---------------------------------
Edit tests/e2e/test_job_urls.py and add your URLs to the lists above.

Option 3: Command Line
----------------------
GREENHOUSE_TEST_URL="..." pytest tests/e2e/test_live_submissions.py -v
""")
    print("="*70 + "\n")


# Print status when module is loaded
if __name__ == "__main__":
    print_test_job_status()
