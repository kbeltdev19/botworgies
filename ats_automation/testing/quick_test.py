"""
Quick Test Script - Run a small batch to verify ATS automation works
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ats_automation.testing.live_test_runner import LiveTestRunner, KENT_LE_PROFILE


# Sample test URLs (mix of different platforms for validation)
SAMPLE_TEST_URLS = [
    # Dice jobs (Easy Apply) - Most likely to work
    "https://www.dice.com/job-detail/Customer-Success-Manager",
    
    # Note: Real URLs would be collected from job search
    # These are placeholder examples
]


async def run_quick_test():
    """Run a quick 10-job test to verify system works"""
    
    print("\n" + "="*70)
    print("🚀 QUICK ATS AUTOMATION TEST")
    print("="*70)
    print("\nThis will test the ATS automation system with a small batch")
    print("of jobs to verify all components are working.\n")
    
    # Initialize tester with Kent's profile
    tester = LiveTestRunner(KENT_LE_PROFILE)
    
    # For demonstration, we'll use placeholder URLs
    # In real usage, these would come from job search
    print("⚠️  NOTE: Using placeholder URLs for demonstration")
    print("   To run real test, provide actual job URLs from Dice/Workday/etc.\n")
    
    # Since we don't have real URLs, let's at least verify the system initializes
    print("✓ Profile loaded:", tester.profile.first_name, tester.profile.last_name)
    print("✓ BrowserBase manager initialized")
    print("✓ Test runner ready\n")
    
    print("To run actual test with real job URLs:")
    print("  1. Search for jobs on Dice.com")
    print("  2. Collect 10-50 job URLs")
    print("  3. Run: python quick_test.py --urls <file>")
    
    # If user has URLs, they can pass them
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--urls', help='File containing job URLs (one per line)')
    parser.add_argument('--count', type=int, default=10, help='Number of jobs to test')
    args = parser.parse_args()
    
    if args.urls:
        # Read URLs from file
        with open(args.urls, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        
        urls = urls[:args.count]
        
        print(f"\n🧪 Running test with {len(urls)} jobs...\n")
        
        report = await tester.run_test_batch(
            job_urls=urls,
            target_location="Auburn, AL",
            concurrent=3,
            test_id="quick_test"
        )
        
        tester.print_report()
        
        # Save report
        output_dir = Path("test_results")
        output_dir.mkdir(exist_ok=True)
        report.save(output_dir / "quick_test_report.json")
        
        print(f"\n✅ Report saved to: test_results/quick_test_report.json")
        
        # Evaluate against criteria
        from test_criteria import evaluate_test_results
        evaluation = evaluate_test_results(report.to_dict())
        
        print(f"\n📊 EVALUATION:")
        print(f"  Grade: {evaluation['grade']}")
        print(f"  Score: {evaluation['overall_score']}/100")
        print(f"\n  Passed: {len(evaluation['passed'])}")
        for p in evaluation['passed']:
            print(f"    ✓ {p}")
        print(f"\n  Failed: {len(evaluation['failed'])}")
        for f in evaluation['failed']:
            print(f"    ✗ {f}")
        
        if evaluation['recommendations']:
            print(f"\n  Recommendations:")
            for r in evaluation['recommendations']:
                print(f"    • {r}")
    else:
        print("\n💡 To run actual test:")
        print("   python quick_test.py --urls job_urls.txt --count 10")
        print("\n   Create job_urls.txt with one URL per line:")
        print("   https://www.dice.com/job-detail/...")
        print("   https://company.workday.com/...")
        print("   https://company.taleo.net/...")


if __name__ == "__main__":
    asyncio.run(run_quick_test())
