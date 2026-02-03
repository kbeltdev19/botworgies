#!/usr/bin/env python3
"""
Kent Le - Apply to 10 Jobs
Real application run with job details and application tracking
"""

import sys
import asyncio
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Kent's Profile
KENT_PROFILE = {
    "name": "Kent Le",
    "email": "kle4311@gmail.com",
    "phone": "(404) 934-0630",
    "location": "Auburn, AL",
    "linkedin": "https://linkedin.com/in/kent-le",
    "summary": "Customer Success professional with supply chain background, CRM experience, bilingual English/Vietnamese",
    "target_salary": "$75,000 - $95,000",
    "relocation": "Open to remote and hybrid positions",
    "start_date": "2 weeks notice",
}

# Top 10 Jobs for Kent (selected from our search)
# Prioritized by: salary >= $75k, remote/hybrid, location proximity
TOP_10_JOBS = [
    {
        "id": 1,
        "title": "Account Manager - Commercial Lines",
        "company": "Insurance Office of America",
        "location": "Montgomery, AL (Remote)",
        "salary": "$70,000 - $90,000",
        "url": "https://www.indeed.com/viewjob?jk=ac2d8ad926f0a2a8",
        "type": "External Application",
        "notes": "Remote position, meets salary requirement, insurance industry"
    },
    {
        "id": 2,
        "title": "Account Manager - Commercial Lines", 
        "company": "Insurance Office of America",
        "location": "Columbus, GA (Remote)",
        "salary": "$70,000 - $90,000",
        "url": "https://www.indeed.com/viewjob?jk=74a78a0fd7a3bc09",
        "type": "External Application",
        "notes": "Remote position, meets salary requirement, same company as #1"
    },
    {
        "id": 3,
        "title": "Account Executive - MR",
        "company": "Mobile Communications America Inc",
        "location": "Columbus, GA (Remote)",
        "salary": "Not listed (target: $75k+)",
        "url": "https://www.indeed.com/viewjob?jk=b716ba22b3754783",
        "type": "External Application",
        "notes": "Remote AE position, B2B sales, communications industry"
    },
    {
        "id": 4,
        "title": "Customer Success Manager I or II",
        "company": "FIS",
        "location": "Columbus, GA",
        "salary": "Not listed (target: $75k+)",
        "url": "https://www.indeed.com/viewjob?jk=b60cb586e34b5de6",
        "type": "External Application",
        "notes": "Large fintech company, CSM role matches Kent's target"
    },
    {
        "id": 5,
        "title": "Customer Relations Representative",
        "company": "State Farm",
        "location": "Columbus, GA",
        "salary": "$45,000 - $60,000",
        "url": "https://www.indeed.com/viewjob?jk=159be4d691f33e44",
        "type": "External Application",
        "notes": "Below target salary but good company, entry point to insurance industry"
    },
    {
        "id": 6,
        "title": "Team Leader",
        "company": "Keller Williams Realty",
        "location": "Columbus, GA",
        "salary": "$50,000 - $75,000",
        "url": "https://www.indeed.com/viewjob?jk=bc43f359c595404e",
        "type": "External Application",
        "notes": "Leadership role, real estate industry, commission potential"
    },
    {
        "id": 7,
        "title": "Route Sales Representative",
        "company": "Community Coffee",
        "location": "Auburn, AL",
        "salary": "Not listed",
        "url": "https://www.indeed.com/viewjob?jk=b70a63193723eb64",
        "type": "External Application",
        "notes": "Local to Auburn, sales role, established company"
    },
    {
        "id": 8,
        "title": "Account Manager [Regional Events Division]",
        "company": "Greenawalt Hospitality",
        "location": "Auburn, AL",
        "salary": "$37,500 - $40,000",
        "url": "https://www.indeed.com/viewjob?jk=31d3c10320804fe4",
        "type": "External Application",
        "notes": "Local Auburn company, hospitality industry, below target but local"
    },
    {
        "id": 9,
        "title": "Account Manager",
        "company": "RNR Tire Express",
        "location": "Opelika, AL",
        "salary": "Not listed",
        "url": "https://www.indeed.com/viewjob?jk=bb49edef3821c92a",
        "type": "External Application",
        "notes": "Nearby in Opelika, account management role"
    },
    {
        "id": 10,
        "title": "Real Estate Sales Agent Trainee",
        "company": "Auburn Area Real Estate",
        "location": "Auburn, AL",
        "salary": "$97,000 - $225,000 (commission)",
        "url": "https://www.indeed.com/viewjob?jk=67d02b59499426c4",
        "type": "External Application",
        "notes": "High earning potential, local Auburn, requires real estate license"
    },
]


def print_campaign_header():
    """Print campaign header."""
    print("\n" + "="*80)
    print("  KENT LE - 10 REAL JOB APPLICATIONS")
    print("="*80)
    print()
    print("  Profile:")
    print(f"    Name: {KENT_PROFILE['name']}")
    print(f"    Location: {KENT_PROFILE['location']}")
    print(f"    Target: Customer Success / Account Management / Sales")
    print(f"    Salary: {KENT_PROFILE['target_salary']}")
    print(f"    Email: {KENT_PROFILE['email']}")
    print(f"    Phone: {KENT_PROFILE['phone']}")
    print()
    print("  Resume: /Users/tech4/Downloads/botworkieslocsl/botworgies/Test Resumes/Kent_Le_Resume.pdf")
    print("="*80)


def print_job_list():
    """Print the 10 selected jobs."""
    print("\n📋 SELECTED JOBS (Top 10):")
    print("-"*80)
    
    for job in TOP_10_JOBS:
        print(f"\n{job['id']}. {job['title']}")
        print(f"   Company: {job['company']}")
        print(f"   Location: {job['location']}")
        print(f"   Salary: {job['salary']}")
        print(f"   Type: {job['type']}")
        print(f"   URL: {job['url']}")
        print(f"   Notes: {job['notes']}")


def generate_application_package():
    """Generate application package for Kent."""
    output_dir = Path(__file__).parent / "output" / "kent_le_10_real"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    
    # Save job list
    jobs_file = output_dir / f"application_package_{timestamp}.json"
    package = {
        "candidate": KENT_PROFILE,
        "jobs": TOP_10_JOBS,
        "generated_at": datetime.now().isoformat(),
        "instructions": [
            "1. Review each job posting carefully",
            "2. Tailor resume for each position if needed",
            "3. Write custom cover letters highlighting relevant experience",
            "4. Apply via external links provided",
            "5. Track applications in spreadsheet",
            "6. Follow up after 1 week if no response"
        ],
        "cover_letter_template": generate_cover_letter_template(),
    }
    
    with open(jobs_file, 'w') as f:
        json.dump(package, f, indent=2)
    
    # Generate application tracking spreadsheet
    csv_file = output_dir / f"application_tracker_{timestamp}.csv"
    with open(csv_file, 'w') as f:
        f.write("ID,Date Applied,Company,Title,Location,Salary,URL,Status,Follow Up Date,Notes\n")
        for job in TOP_10_JOBS:
            f.write(f"\"{job['id']}\",\"\",\"{job['company']}\",\"{job['title']}\",\"{job['location']}\",\"{job['salary']}\",\"{job['url']}\",\"Pending\",\"\",\"{job['notes']}\"\n")
    
    # Generate cover letters
    cover_letter_dir = output_dir / f"cover_letters_{timestamp}"
    cover_letter_dir.mkdir(exist_ok=True)
    
    for job in TOP_10_JOBS:
        letter = generate_cover_letter(job)
        letter_file = cover_letter_dir / f"cover_letter_{job['id']}_{job['company'].replace(' ', '_')}.txt"
        with open(letter_file, 'w') as f:
            f.write(letter)
    
    print(f"\n💾 Application Package Generated:")
    print(f"   Jobs JSON: {jobs_file}")
    print(f"   Tracker CSV: {csv_file}")
    print(f"   Cover Letters: {cover_letter_dir}")
    
    return output_dir


def generate_cover_letter_template():
    """Generate a cover letter template."""
    return f"""Dear Hiring Manager,

I am writing to express my strong interest in the [POSITION] role at [COMPANY]. With my background in customer relationship management, data analysis, and supply chain operations, I am confident I can make a significant contribution to your team.

Key qualifications I bring:
• 3+ years of customer-facing experience in fast-paced environments
• Proficiency with CRM systems and data analysis tools
• Bilingual in English and Vietnamese, enabling effective communication with diverse clients
• Strong problem-solving skills and attention to detail
• Experience managing accounts and ensuring customer satisfaction

I am particularly drawn to [COMPANY] because [SPECIFIC REASON]. The opportunity to combine my customer success expertise with my analytical skills in a remote/hybrid capacity is exactly what I am looking for in my next career move.

My salary expectation is {KENT_PROFILE['target_salary']}, and I am available to start with two weeks' notice. I am open to remote, hybrid, or in-person arrangements.

Thank you for considering my application. I would welcome the opportunity to discuss how my background and skills align with your team's needs.

Sincerely,
{KENT_PROFILE['name']}
{KENT_PROFILE['phone']}
{KENT_PROFILE['email']}
{KENT_PROFILE['linkedin']}
"""


def generate_cover_letter(job):
    """Generate a tailored cover letter for a specific job."""
    company = job['company']
    title = job['title']
    
    # Customize based on company/job type
    specific_reason = "your company's commitment to customer excellence"
    
    if "Insurance" in company:
        specific_reason = "your reputation in the insurance industry and the opportunity to help businesses protect their assets"
    elif "State Farm" in company:
        specific_reason = "State Farm's trusted brand and focus on personalized customer service"
    elif "Real Estate" in company or "Realty" in company:
        specific_reason = "the dynamic real estate market and the opportunity to help clients achieve their property goals"
    elif "Sales" in title:
        specific_reason = "the opportunity to drive revenue growth while building lasting client relationships"
    elif "Customer Success" in title:
        specific_reason = "your customer-centric approach and the opportunity to ensure client satisfaction and retention"
    
    return f"""Dear Hiring Manager,

I am writing to express my strong interest in the {title} role at {company}. With my background in customer relationship management, data analysis, and supply chain operations, I am confident I can make a significant contribution to your team.

Key qualifications I bring:
• 3+ years of customer-facing experience in fast-paced environments
• Proficiency with CRM systems and data analysis tools
• Bilingual in English and Vietnamese, enabling effective communication with diverse clients
• Strong problem-solving skills and attention to detail
• Experience managing accounts and ensuring customer satisfaction

I am particularly drawn to {company} because of {specific_reason}. The opportunity to combine my customer success expertise with my analytical skills in a remote/hybrid capacity is exactly what I am looking for in my next career move.

My salary expectation is {KENT_PROFILE['target_salary']}, and I am available to start with two weeks' notice. I am open to remote, hybrid, or in-person arrangements.

Thank you for considering my application. I would welcome the opportunity to discuss how my background and skills align with your team's needs.

Sincerely,
{KENT_PROFILE['name']}
{KENT_PROFILE['phone']}
{KENT_PROFILE['email']}
{KENT_PROFILE['linkedin']}
"""


def print_next_steps(output_dir):
    """Print next steps for Kent."""
    print("\n" + "="*80)
    print("📋 NEXT STEPS FOR KENT")
    print("="*80)
    print()
    print("1. REVIEW THE SELECTED JOBS")
    print("   - Open each job URL to verify it's still active")
    print("   - Check if requirements match your experience")
    print()
    print("2. PREPARE APPLICATION MATERIALS")
    print("   - Resume: Ensure Kent_Le_Resume.pdf is up to date")
    print("   - Cover Letters: Customize the generated cover letters")
    print("   - References: Have 2-3 professional references ready")
    print()
    print("3. APPLY TO EACH JOB")
    print("   - Use the provided URLs to access job postings")
    print("   - Complete applications on company websites")
    print("   - Save confirmation emails/numbers")
    print()
    print("4. TRACK YOUR APPLICATIONS")
    print(f"   - Use the CSV tracker: {output_dir}/application_tracker_*.csv")
    print("   - Update status after each application")
    print("   - Set follow-up dates (1 week after applying)")
    print()
    print("5. FOLLOW UP")
    print("   - Send follow-up emails if no response after 1 week")
    print("   - Connect with recruiters on LinkedIn")
    print("   - Continue networking in your target industries")
    print()
    print("="*80)
    print(f"\n📁 All files saved to: {output_dir}")
    print("="*80)


def main():
    """Run the application campaign."""
    print_campaign_header()
    print_job_list()
    
    print("\n" + "-"*80)
    print("⚠️  IMPORTANT: These are EXTERNAL APPLICATIONS")
    print("-"*80)
    print("\nAll 10 jobs require visiting company websites to apply.")
    print("This campaign generates the application package for manual submission.")
    print("\nGenerating application package...")
    
    output_dir = generate_application_package()
    print_next_steps(output_dir)
    
    print("\n✅ Campaign setup complete!")
    print(f"\nKent should apply to these 10 jobs manually using the generated")
    print(f"cover letters and tracking spreadsheet.")


if __name__ == "__main__":
    main()
