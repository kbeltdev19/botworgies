"""
Run Kent Le's 500-Job Live Test

IMPORTANT: This will actually apply to 500 jobs using BrowserBase sessions.
Estimated time: 2-3 hours
Estimated cost: ~$10-20 in BrowserBase credits
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ats_automation.testing.live_test_runner import LiveTestRunner, KENT_LE_PROFILE, TestMetrics
from ats_automation import ATSRouter, ApplicationResult, ATSPlatform


async def run_500_job_test():
    """Run the full 500-job test for Kent Le"""
    
    print("\n" + "="*70)
    print("🚀 KENT LE 500-JOB LIVE TEST")
    print("="*70)
    print(f"\nCandidate: Kent Le")
    print(f"Location: Auburn, AL / Remote")
    print(f"Target: 500 job applications")
    print(f"Concurrent: 5 sessions")
    print(f"Resume: Test Resumes/Kent_Le_Resume.pdf")
    print(f"\n⚠️  WARNING: This will create actual BrowserBase sessions")
    print(f"   and attempt to apply to 500 real jobs.")
    print(f"   Estimated time: 2-3 hours")
    print(f"   Estimated cost: $10-20 in BrowserBase credits")
    print(f"\n{'='*70}\n")
    
    # Load job URLs
    job_urls_file = Path("job_urls_500.txt")
    if not job_urls_file.exists():
        print(f"❌ Job URLs file not found: {job_urls_file}")
        print("   Run: python3 collect_500_fast.py")
        return
    
    with open(job_urls_file, 'r') as f:
        job_urls = [line.strip() for line in f if line.strip()]
    
    print(f"✅ Loaded {len(job_urls)} job URLs")
    
    # Confirm
    response = input("\n⚠️  Do you want to proceed with the 500-job test? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("\n❌ Test cancelled by user")
        return
    
    # Initialize tester
    print("\n🧪 Initializing test runner...")
    tester = LiveTestRunner(KENT_LE_PROFILE)
    
    # Run test
    print(f"\n🚀 Starting 500-job test batch...")
    print(f"   Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   This will take approximately 2-3 hours...")
    print(f"\n{'='*70}\n")
    
    try:
        report = await tester.run_test_batch(
            job_urls=job_urls,
            target_location="Auburn, AL / Remote / United States",
            concurrent=5,
            test_id="kent_le_500_full_test"
        )
        
        # Print report
        tester.print_report()
        
        # Save report
        output_dir = Path("test_results")
        output_dir.mkdir(exist_ok=True)
        report_file = output_dir / f"{report.test_id}_report.json"
        report.save(report_file)
        
        print(f"\n✅ Full report saved to: {report_file}")
        
        # Evaluate
        from test_criteria import evaluate_test_results
        evaluation = evaluate_test_results(report.to_dict())
        
        print(f"\n{'='*70}")
        print("📊 FINAL EVALUATION")
        print(f"{'='*70}")
        print(f"Grade: {evaluation['grade']}")
        print(f"Score: {evaluation['overall_score']}/100")
        
        if evaluation['passed']:
            print(f"\n✅ PASSED:")
            for p in evaluation['passed']:
                print(f"  • {p}")
        
        if evaluation['failed']:
            print(f"\n❌ FAILED:")
            for f in evaluation['failed']:
                print(f"  • {f}")
        
        if evaluation['recommendations']:
            print(f"\n💡 RECOMMENDATIONS:")
            for r in evaluation['recommendations']:
                print(f"  • {r}")
        
        print(f"\n{'='*70}")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        print("   Partial results may be available in test_results/")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


async def run_demo_test(count: int = 10):
    """Run a small demo test (default 10 jobs)"""
    
    print("\n" + "="*70)
    print("🧪 DEMO TEST (Small Batch)")
    print("="*70)
    print(f"\nRunning test with {count} jobs to validate system...")
    
    # Load job URLs
    job_urls_file = Path("job_urls_500.txt")
    if not job_urls_file.exists():
        print(f"❌ Job URLs file not found")
        return
    
    with open(job_urls_file, 'r') as f:
        job_urls = [line.strip() for line in f if line.strip()][:count]
    
    print(f"✅ Loaded {len(job_urls)} job URLs")
    
    # Initialize tester
    tester = LiveTestRunner(KENT_LE_PROFILE)
    
    # Run test
    report = await tester.run_test_batch(
        job_urls=job_urls,
        target_location="Auburn, AL / Remote",
        concurrent=3,
        test_id=f"kent_le_demo_{count}"
    )
    
    # Print report
    tester.print_report()
    
    # Save
    output_dir = Path("test_results")
    output_dir.mkdir(exist_ok=True)
    report.save(output_dir / f"{report.test_id}_report.json")
    
    print(f"\n✅ Demo test complete!")
    print(f"   To run full 500-job test: python3 run_kent_le_500_test.py --full")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Kent Le 500-job test")
    parser.add_argument('--full', action='store_true', help='Run full 500-job test')
    parser.add_argument('--demo', type=int, default=10, help='Run demo with N jobs (default: 10)')
    args = parser.parse_args()
    
    if args.full:
        asyncio.run(run_500_job_test())
    else:
        asyncio.run(run_demo_test(args.demo))
