#!/usr/bin/env python3
"""
Test script to verify JobSpy setup and functionality.
Run this after installing Python 3.11+ to verify everything works.
"""

import sys
import asyncio


def check_python_version():
    """Check if Python version is 3.10+."""
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print("\n❌ ERROR: Python 3.10+ required for JobSpy")
        print("Current version is too old. Please upgrade:")
        print("  ./scripts/install_python311.sh")
        return False
    
    print("✅ Python version is compatible\n")
    return True


def test_jobspy_import():
    """Test if JobSpy can be imported."""
    try:
        from jobspy import scrape_jobs
        print("✅ JobSpy import successful\n")
        return True
    except ImportError as e:
        print(f"❌ JobSpy import failed: {e}")
        print("Install with: pip install python-jobspy\n")
        return False


def test_adapter_import():
    """Test if JobSpy adapter can be imported."""
    try:
        from adapters.jobspy_scraper import JobSpyScraper, JobSpyConfig
        print("✅ JobSpy adapter import successful\n")
        return True
    except ImportError as e:
        print(f"❌ JobSpy adapter import failed: {e}\n")
        return False


async def test_basic_scrape():
    """Test a basic JobSpy scrape."""
    from adapters.jobspy_scraper import JobSpyScraper, JobSpyConfig
    
    print("Testing basic JobSpy scrape...")
    print("=" * 50)
    
    scraper = JobSpyScraper()
    
    config = JobSpyConfig(
        site_name=["indeed"],  # Use Indeed for testing (most reliable)
        search_term="software engineer",
        location="Remote",
        results_wanted=5,
        hours_old=168,
        verbose=1
    )
    
    try:
        jobs = await scraper.scrape_jobs(config)
        print(f"\n✅ Scrape successful! Found {len(jobs)} jobs")
        
        if jobs:
            print("\nSample jobs:")
            for job in jobs[:3]:
                print(f"  - {job.title} @ {job.company}")
                print(f"    Location: {job.location}")
                print(f"    URL: {job.url[:60]}...")
        
        return True
    except Exception as e:
        print(f"\n❌ Scrape failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 50)
    print("JobSpy Setup Verification")
    print("=" * 50)
    print()
    
    # Check Python version
    if not check_python_version():
        return 1
    
    # Test imports
    if not test_jobspy_import():
        return 1
    
    if not test_adapter_import():
        return 1
    
    # Test basic scrape
    success = asyncio.run(test_basic_scrape())
    
    print()
    print("=" * 50)
    if success:
        print("✅ All tests passed! JobSpy is ready to use.")
        print()
        print("Next steps:")
        print("  1. Import in your code:")
        print("     from adapters import JobSpyScraper, JobSpyConfig")
        print()
        print("  2. Use for scraping:")
        print("     scraper = JobSpyScraper()")
        print("     jobs = await scraper.scrape_jobs(config)")
    else:
        print("❌ Some tests failed. Check errors above.")
        return 1
    print("=" * 50)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
