#!/usr/bin/env python3
"""Collect fresh ServiceNow jobs for Kevin Beltran using JobSpy - Parallelized"""

import json
import sys
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent.parent))

from jobspy import scrape_jobs

ROLES = [
    "ServiceNow Business Analyst",
    "ServiceNow Consultant",
    "ServiceNow Administrator",
    "ITSM Analyst",
    "ServiceNow Developer",
    "ServiceNow Engineer",
    "ServiceNow Architect",
    "IT Service Management",
]

LOCATIONS = [
    "Remote",
    "Atlanta, GA",
    "Georgia",
]

OUTPUT_DIR = Path("campaigns/output/kevin_fresh")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def search_one(role, location):
    """Search a single role+location combo."""
    is_remote = location == "Remote"
    try:
        jobs_df = scrape_jobs(
            site_name=["indeed", "linkedin", "zip_recruiter"],
            search_term=role,
            location="" if is_remote else location,
            is_remote=is_remote,
            results_wanted=100,
            hours_old=336,
            job_type="fulltime",
        )
        results = []
        for _, job in jobs_df.iterrows():
            url = job.get("job_url", "")
            if not url:
                continue
            results.append({
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "location": job.get("location", ""),
                "url": url,
                "is_remote": bool(job.get("is_remote", False)),
                "site": job.get("site", "unknown"),
                "date_posted": str(job.get("date_posted", "")),
            })
        return role, location, results
    except Exception as e:
        return role, location, []


def main():
    # Build all search combos
    combos = [(role, loc) for role in ROLES for loc in LOCATIONS]
    print(f"Running {len(combos)} searches in parallel (8 workers)...\n")

    all_jobs = []
    seen_urls = set()

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(search_one, role, loc): (role, loc)
            for role, loc in combos
        }

        for future in as_completed(futures):
            role, location, results = future.result()
            new = 0
            for job in results:
                if job["url"] not in seen_urls:
                    seen_urls.add(job["url"])
                    all_jobs.append(job)
                    new += 1
            print(f"  {role} | {location} -> +{new} (total: {len(all_jobs)})")

    # Save
    output_file = OUTPUT_DIR / "jobs.json"
    with open(output_file, "w") as f:
        json.dump(all_jobs, f, indent=2, default=str)

    print(f"\n{'='*60}")
    print(f"Collected {len(all_jobs)} unique jobs")
    print(f"Saved to: {output_file}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
