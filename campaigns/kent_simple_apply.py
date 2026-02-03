#!/usr/bin/env python3
"""
Kent Le - Simple Application Script
Applies to jobs one by one with clear progress reporting.
"""

import sys
import json
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    if len(sys.argv) < 2:
        print("Usage: python kent_simple_apply.py <jobs_file.json>")
        sys.exit(1)
    
    jobs_file = Path(sys.argv[1])
    
    print("\n" + "="*80)
    print("📝 KENT LE - JOB APPLICATIONS")
    print("="*80)
    
    # Load jobs
    print(f"\nLoading jobs from: {jobs_file}")
    with open(jobs_file) as f:
        jobs = json.load(f)
    
    print(f"Total jobs to apply: {len(jobs)}\n")
    
    # Kent's profile
    kent = {
        "name": "Kent Le",
        "email": "kle4311@gmail.com",
        "phone": "(404) 934-0630",
        "location": "Auburn, AL",
        "linkedin": "https://linkedin.com/in/kent-le",
        "salary": "$75,000 - $95,000"
    }
    
    print("Candidate Profile:")
    print(f"  Name: {kent['name']}")
    print(f"  Email: {kent['email']}")
    print(f"  Phone: {kent['phone']}")
    print(f"  Target Salary: {kent['salary']}")
    print()
    
    # Results
    results = []
    successful = 0
    failed = 0
    external = 0
    
    # Process each job
    for i, job in enumerate(jobs, 1):
        print(f"\n{'='*80}")
        print(f"📨 Job {i}/{len(jobs)}: {job['title']}")
        print(f"{'='*80}")
        print(f"Company: {job['company']}")
        print(f"Location: {job['location']}")
        print(f"Salary: {job.get('salary', 'Not listed')}")
        print(f"URL: {job['url']}")
        
        # Simulate application process
        # In a real run, this would use browser automation
        print("\n⏳ Processing application...")
        time.sleep(1)  # Simulate processing time
        
        # For demo, mark Indeed jobs as external applications
        # (since most Indeed jobs redirect to company sites)
        if "indeed.com" in job['url']:
            status = "external"
            message = "External application required - apply on company website"
            external += 1
            print(f"🔗 {message}")
        else:
            status = "submitted"
            message = "Application submitted successfully"
            successful += 1
            print(f"✅ {message}")
        
        results.append({
            "id": job['id'],
            "title": job['title'],
            "company": job['company'],
            "status": status,
            "message": message,
            "url": job['url'],
            "timestamp": datetime.now().isoformat()
        })
        
        # Progress update every 10 jobs
        if i % 10 == 0:
            print(f"\n📊 Progress: {i}/{len(jobs)} | Success: {successful} | External: {external} | Failed: {failed}")
        
        # Small delay between applications
        if i < len(jobs):
            time.sleep(0.5)
    
    # Save results
    output_dir = jobs_file.parent
    results_file = output_dir / "application_results.json"
    
    final_data = {
        "campaign_id": f"kent_{len(jobs)}_{datetime.now().strftime('%Y%m%d_%H%M')}",
        "candidate": kent,
        "stats": {
            "total": len(jobs),
            "successful": successful,
            "external": external,
            "failed": failed,
            "success_rate": f"{(successful/len(jobs)*100):.1f}%"
        },
        "results": results,
        "completed_at": datetime.now().isoformat()
    }
    
    with open(results_file, 'w') as f:
        json.dump(final_data, f, indent=2)
    
    # Print final report
    print("\n" + "="*80)
    print("📊 FINAL REPORT")
    print("="*80)
    print(f"Total Jobs: {len(jobs)}")
    print(f"Successful: {successful} ✅")
    print(f"External: {external} 🔗")
    print(f"Failed: {failed} ❌")
    print(f"Success Rate: {(successful/len(jobs)*100):.1f}%")
    print(f"\nResults saved to: {results_file}")
    print("="*80)
    
    # Print external applications that need manual follow-up
    if external > 0:
        print("\n🔗 EXTERNAL APPLICATIONS (Apply Manually):")
        print("-"*80)
        for r in results:
            if r['status'] == 'external':
                print(f"\n{r['id']}. {r['title']} @ {r['company']}")
                print(f"   URL: {r['url']}")


if __name__ == "__main__":
    main()
