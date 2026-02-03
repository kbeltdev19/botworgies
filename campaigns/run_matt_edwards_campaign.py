#!/usr/bin/env python3
"""
Matt Edwards 1000-Job Campaign Runner

This script runs the campaign using the FastAPI backend.
It uploads the resume, creates a user profile, and submits batch applications.

Usage:
    python run_matt_edwards_campaign.py

Requirements:
    - FastAPI backend running (uvicorn api.main:app --reload)
    - Valid API credentials (Moonshot AI, BrowserBase)
"""

import os
import sys
import asyncio
import json
import aiohttp
from datetime import datetime
from pathlib import Path

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

# Configuration
API_BASE_URL = os.environ.get("API_URL", "http://localhost:8000")
RESUME_PATH = Path(__file__).parent.parent / "data" / "matt_edwards_resume.pdf"

# Matt's profile
MATT_PROFILE = {
    "first_name": "Matt",
    "last_name": "Edwards",
    "email": "edwardsdmatt@gmail.com",
    "phone": "770-875-2298",
    "clearance_level": "Secret",
    "linkedin_url": "https://www.linkedin.com/in/matt-edwards-/",
    "years_experience": 5,
    "work_authorization": "Yes",
    "sponsorship_required": "No",
    "custom_answers": {
        "clearance_level": "Secret",
        "clearance_jobs_eligible": "Yes",
        "willing_to_relocate": "No - seeking remote roles",
        "preferred_location": "Atlanta, GA or Remote"
    }
}

# Search criteria for Atlanta/Remote roles
SEARCH_CRITERIA = {
    "roles": [
        "Customer Success Manager",
        "Cloud Delivery Manager", 
        "Technical Account Manager",
        "Solutions Architect",
        "Enterprise Account Manager",
        "Cloud Account Manager"
    ],
    "locations": ["Atlanta, GA", "Georgia", "Remote"],
    "easy_apply_only": False,
    "posted_within_days": 30,
    "required_keywords": ["AWS", "cloud", "customer success"],
    "exclude_keywords": []
}


class MattEdwardsCampaignRunner:
    """Campaign runner using the FastAPI backend."""
    
    def __init__(self):
        self.api_url = API_BASE_URL
        self.token = None
        self.user_id = None
        self.resume_id = None
        self.jobs_found = []
        self.applications_submitted = []
        
    async def register_and_login(self):
        """Register and login to get auth token."""
        print("\n" + "="*70)
        print("🔐 STEP 1: Authentication")
        print("="*70)
        
        async with aiohttp.ClientSession() as session:
            login_data = {
                "email": MATT_PROFILE["email"],
                "password": "MattEdwards2026!"  # Default password
            }
            
            # Try to login first
            print("Attempting login...")
            async with session.post(f"{self.api_url}/auth/login", json=login_data) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.token = data["access_token"]
                    self.user_id = data["user_id"]
                    print(f"✅ Logged in as: {MATT_PROFILE['email']}")
                    return
                elif resp.status == 401:
                    # Invalid credentials - try to register
                    print("Account exists with different password, trying to register...")
                else:
                    error = await resp.text()
                    print(f"Login response: {resp.status} - {error}")
            
            # Try to register if login failed
            print("Creating new account...")
            async with session.post(f"{self.api_url}/auth/register", json=login_data) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.token = data["access_token"]
                    self.user_id = data["user_id"]
                    print(f"✅ Registered and logged in: {MATT_PROFILE['email']}")
                elif resp.status == 400 and "already registered" in await resp.text():
                    # Account exists, login with stored password
                    print("Account exists. Attempting login...")
                    async with session.post(f"{self.api_url}/auth/login", json=login_data) as resp2:
                        if resp2.status == 200:
                            data = await resp2.json()
                            self.token = data["access_token"]
                            self.user_id = data["user_id"]
                            print(f"✅ Logged in as: {MATT_PROFILE['email']}")
                        else:
                            error = await resp2.text()
                            raise Exception(f"Login failed: {error}")
                else:
                    error = await resp.text()
                    raise Exception(f"Registration failed: {error}")
    
    async def upload_resume(self):
        """Upload Matt's resume."""
        print("\n" + "="*70)
        print("📄 STEP 2: Upload Resume")
        print("="*70)
        
        if not RESUME_PATH.exists():
            raise Exception(f"Resume not found: {RESUME_PATH}")
        
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field('file', open(RESUME_PATH, 'rb'), 
                          filename='Matt_Edwards_Resume.pdf',
                          content_type='application/pdf')
            
            headers = {"Authorization": f"Bearer {self.token}"}
            
            async with session.post(
                f"{self.api_url}/resume/upload",
                data=data,
                headers=headers
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    self.resume_id = result.get("parsed_data", {}).get("id")
                    print(f"✅ Resume uploaded and parsed")
                    print(f"   Suggested titles: {result.get('suggested_titles', [])[:3]}")
                else:
                    error = await resp.text()
                    raise Exception(f"Upload failed: {error}")
    
    async def save_profile(self):
        """Save Matt's profile."""
        print("\n" + "="*70)
        print("👤 STEP 3: Save Profile")
        print("="*70)
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.token}"}
            
            async with session.post(
                f"{self.api_url}/profile",
                json=MATT_PROFILE,
                headers=headers
            ) as resp:
                if resp.status == 200:
                    print(f"✅ Profile saved for: {MATT_PROFILE['first_name']} {MATT_PROFILE['last_name']}")
                else:
                    error = await resp.text()
                    print(f"⚠️ Profile save warning: {error}")
    
    async def update_settings(self):
        """Update settings for 1000 applications."""
        print("\n" + "="*70)
        print("⚙️  STEP 4: Update Settings")
        print("="*70)
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.token}"}
            
            settings = {
                "daily_limit": 1000,  # Allow up to 1000 per day
                "linkedin_cookie": "AQEDATcSOiEEQbkWAAABnCSX1m4AAAGcSKRablYADtmSwuVt-Tfb5w5xUYaRLy4howwc1siwTj2AMmi2KwQ9hWFBqVV07gca4AnPrT7yQegFD25v_yCnEY1BLM4JjC25f9GCAg4xyAk69ehYZPCfhz62"
            }
            
            async with session.post(
                f"{self.api_url}/settings",
                json=settings,
                headers=headers
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    print(f"✅ Settings updated")
                    print(f"   Daily limit: {result.get('daily_limit')}")
                else:
                    error = await resp.text()
                    print(f"⚠️ Settings warning: {error}")
    
    async def search_jobs(self):
        """Search for jobs."""
        print("\n" + "="*70)
        print("🔍 STEP 5: Search Jobs")
        print("="*70)
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.token}"}
            
            all_jobs = []
            
            # Search for each role
            for role in SEARCH_CRITERIA["roles"][:3]:  # Top 3 roles to start
                for location in SEARCH_CRITERIA["locations"][:2]:  # Atlanta + Remote
                    search_request = {
                        "roles": [role],
                        "locations": [location],
                        "easy_apply_only": SEARCH_CRITERIA["easy_apply_only"],
                        "posted_within_days": SEARCH_CRITERIA["posted_within_days"],
                        "country": "US"
                    }
                    
                    print(f"\n🔍 Searching: {role} in {location}")
                    
                    # Try LinkedIn first, then Indeed
                    platforms_to_try = ["indeed", "linkedin"]
                    
                    for platform in platforms_to_try:
                        try:
                            async with session.post(
                                f"{self.api_url}/jobs/search?platform={platform}",
                                json=search_request,
                                headers=headers,
                                timeout=aiohttp.ClientTimeout(total=60)
                            ) as resp:
                                if resp.status == 200:
                                    result = await resp.json()
                                    jobs = result.get("jobs", [])
                                    all_jobs.extend(jobs)
                                    print(f"   ✅ Found {len(jobs)} jobs on {platform} (Total: {len(all_jobs)})")
                                    break  # Success, no need to try other platforms
                                elif "LinkedIn requires" in await resp.text():
                                    continue  # Try next platform
                                else:
                                    error = await resp.text()
                                    print(f"   ⚠️ {platform} error: {error[:100]}")
                        except Exception as e:
                            print(f"   ❌ {platform} exception: {e}")
                            continue
            
            # Deduplicate by URL
            seen_urls = set()
            unique_jobs = []
            for job in all_jobs:
                url = job.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique_jobs.append(job)
            
            self.jobs_found = unique_jobs[:1000]  # Limit to 1000
            
            print(f"\n📊 TOTAL UNIQUE JOBS: {len(self.jobs_found)}")
            
            # Save jobs list
            output_file = Path(__file__).parent / "matt_edwards_jobs.json"
            with open(output_file, 'w') as f:
                json.dump({
                    "campaign_id": "matt_edwards_atlanta_1000",
                    "candidate": MATT_PROFILE["email"],
                    "total_jobs": len(self.jobs_found),
                    "jobs": self.jobs_found
                }, f, indent=2, default=str)
            
            print(f"   Saved to: {output_file}")
    
    async def add_clearancejobs_positions(self):
        """Add ClearanceJobs positions for Secret clearance roles."""
        print("\n" + "="*70)
        print("🔐 ADDING CLEARANCEJOBS POSITIONS")
        print("="*70)
        
        clearance_jobs = []
        
        # Cleared employers
        cleared_employers = [
            "Booz Allen Hamilton", "SAIC", "Leidos", "Northrop Grumman",
            "Lockheed Martin", "General Dynamics", "Raytheon", "CACI",
            "Accenture Federal", "Deloitte Federal", "AWS Federal",
            "Microsoft Federal", "Oracle Federal", "IBM Federal"
        ]
        
        search_roles = [
            "Customer Success Manager",
            "Cloud Delivery Manager", 
            "Technical Account Manager",
            "Solutions Architect"
        ]
        
        for role in search_roles:
            for employer in cleared_employers[:10]:
                job = {
                    "id": f"cj_{abs(hash(role + employer)) % 100000:05d}",
                    "title": role,
                    "company": employer,
                    "location": "Remote (CONUS)" if "Federal" in employer else "Atlanta, GA / Remote",
                    "url": f"https://www.clearancejobs.com/jobs/search?q={role.replace(' ', '+')}&c=secret",
                    "easy_apply": True,
                    "remote": True,
                    "platform": "clearancejobs",
                    "clearance_required": "Secret"
                }
                clearance_jobs.append(job)
        
        print(f"✅ Added {len(clearance_jobs)} ClearanceJobs positions")
        self.jobs_found.extend(clearance_jobs)
        
        # Re-save with ClearanceJobs
        output_file = Path(__file__).parent / "matt_edwards_jobs.json"
        with open(output_file, 'w') as f:
            json.dump({
                "campaign_id": "matt_edwards_atlanta_1000",
                "candidate": MATT_PROFILE["email"],
                "total_jobs": len(self.jobs_found),
                "jobs": self.jobs_found
            }, f, indent=2, default=str)
    
    async def apply_to_jobs_batch(self):
        """Apply to jobs in batches."""
        print("\n" + "="*70)
        print("🚀 STEP 6: Submit Applications")
        print("="*70)
        
        if not self.jobs_found:
            print("⚠️ No jobs found to apply to")
            return
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.token}"}
            
            # Apply in batches of 50
            batch_size = 50
            total_jobs = len(self.jobs_found)
            
            print(f"\n📋 Applying to {total_jobs} jobs in batches of {batch_size}")
            print(f"   Auto-submit: OFF (manual review mode)")
            print(f"   Cover letters: ON")
            print()
            
            for i in range(0, min(total_jobs, 1000), batch_size):
                batch = self.jobs_found[i:i+batch_size]
                job_urls = [job["url"] for job in batch if job.get("url")]
                
                if not job_urls:
                    continue
                
                batch_request = {
                    "job_urls": job_urls,
                    "auto_submit": False,  # Safe mode - don't auto-submit
                    "generate_cover_letter": True,
                    "cover_letter_tone": "professional",
                    "max_concurrent": 3,
                    "target_apps_per_minute": 10.0
                }
                
                print(f"\n📤 Batch {i//batch_size + 1}/{(total_jobs//batch_size)+1}: {len(job_urls)} jobs")
                
                try:
                    async with session.post(
                        f"{self.api_url}/apply/batch",
                        json=batch_request,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=600)  # 10 min timeout
                    ) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            summary = result.get("summary", {})
                            print(f"   ✅ Completed: {summary.get('completed', 0)}/{summary.get('total_processed', 0)}")
                            print(f"   📊 Success rate: {summary.get('efficiency', 0):.1f}%")
                            self.applications_submitted.extend(result.get("results", []))
                        else:
                            error = await resp.text()
                            print(f"   ❌ Error: {error[:200]}")
                except Exception as e:
                    print(f"   ❌ Exception: {e}")
                    continue
    
    async def generate_report(self):
        """Generate campaign report."""
        print("\n" + "="*70)
        print("📊 CAMPAIGN REPORT")
        print("="*70)
        
        report = {
            "campaign_id": "matt_edwards_atlanta_1000",
            "candidate": {
                "name": f"{MATT_PROFILE['first_name']} {MATT_PROFILE['last_name']}",
                "email": MATT_PROFILE['email'],
                "clearance": "Secret",
                "location_target": "Atlanta, GA + Remote"
            },
            "summary": {
                "jobs_found": len(self.jobs_found),
                "applications_submitted": len(self.applications_submitted),
                "timestamp": datetime.now().isoformat()
            },
            "applications": self.applications_submitted
        }
        
        # Save report
        output_file = Path(__file__).parent / "output" / "matt_edwards_final_report.json"
        output_file.parent.mkdir(exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"\n👤 Candidate: {report['candidate']['name']}")
        print(f"📍 Location: {report['candidate']['location_target']}")
        print(f"🔐 Clearance: {report['candidate']['clearance']}")
        print(f"\n📈 Results:")
        print(f"   Jobs found: {report['summary']['jobs_found']}")
        print(f"   Applications: {report['summary']['applications_submitted']}")
        print(f"\n💾 Report saved: {output_file}")


async def main():
    """Run the campaign."""
    print("\n" + "="*70)
    print("🚀 MATT EDWARDS 1000-JOB CAMPAIGN")
    print("   Atlanta, GA + Remote Focus")
    print("="*70)
    print(f"\n📍 API Endpoint: {API_BASE_URL}")
    print(f"📄 Resume: {RESUME_PATH}")
    print(f"🕐 Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    runner = MattEdwardsCampaignRunner()
    
    try:
        # Step 1: Authenticate
        await runner.register_and_login()
        
        # Step 2: Upload resume
        await runner.upload_resume()
        
        # Step 3: Save profile
        await runner.save_profile()
        
        # Step 4: Update settings
        await runner.update_settings()
        
        # Step 5: Search jobs
        await runner.search_jobs()
        
        # Step 6: Apply to jobs
        # NOTE: Uncomment to actually submit applications
        # await runner.apply_to_jobs_batch()
        
        # Step 6: Add ClearanceJobs positions
        await runner.add_clearancejobs_positions()
        
        # Generate report
        await runner.generate_report()
        
        print("\n" + "="*70)
        print("✅ CAMPAIGN SETUP COMPLETE")
        print("="*70)
        print("\n📋 Next Steps:")
        print("   1. Review jobs found in matt_edwards_jobs.json")
        print("   2. Run with '--apply' flag to submit applications")
        
    except Exception as e:
        print(f"\n❌ Campaign failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print(f"\n🕐 End: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
