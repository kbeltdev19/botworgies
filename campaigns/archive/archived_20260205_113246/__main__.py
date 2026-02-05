#!/usr/bin/env python3
"""
Campaign CLI - Main entry point for job application campaigns.

Usage:
    python -m campaigns run --profile campaigns/profiles/kevin_beltran.yaml --limit 1000
    python -m campaigns test --profile campaigns/profiles/kevin_beltran.yaml
    python -m campaigns validate  # Test all components
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    # Load environment variables from .env file
    from dotenv import load_dotenv
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description='Job Application Campaign Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full 1000-job campaign
  python -m campaigns run --profile campaigns/profiles/kevin_beltran.yaml --limit 1000
  
  # Test mode (5 jobs, no actual applications)
  python -m campaigns test --profile campaigns/profiles/kevin_beltran.yaml
  
  # Validate all components
  python -m campaigns validate
  
  # Run with specific options
  python -m campaigns run --profile kevin_beltran.yaml --limit 100 --daily-limit 10 --no-pipeline
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run a campaign')
    run_parser.add_argument('--profile', required=True, help='Path to profile YAML file')
    run_parser.add_argument('--resume', help='Path to resume PDF (auto-detected from profile if not specified)')
    run_parser.add_argument('--limit', type=int, default=100, help='Target number of jobs (default: 100)')
    run_parser.add_argument('--daily-limit', type=int, default=25, help='Max applications per day (default: 25)')
    run_parser.add_argument('--no-pipeline', action='store_true', help='Disable pipeline mode')
    run_parser.add_argument('--no-visual', action='store_true', help='Disable Visual Form Agent')
    run_parser.add_argument('--strategy', choices=['direct', 'linkedin', 'balanced'], default='balanced',
                           help='Application strategy (default: balanced)')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Test mode (dry run)')
    test_parser.add_argument('--profile', required=True, help='Path to profile YAML file')
    test_parser.add_argument('--jobs', type=int, default=5, help='Number of test jobs (default: 5)')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate all components')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show campaign statistics')
    stats_parser.add_argument('--campaign-id', help='Specific campaign ID (default: latest)')
    
    args = parser.parse_args()
    
    if args.command == 'run':
        asyncio.run(cmd_run(args))
    elif args.command == 'test':
        asyncio.run(cmd_test(args))
    elif args.command == 'validate':
        asyncio.run(cmd_validate())
    elif args.command == 'stats':
        cmd_stats(args)
    else:
        parser.print_help()
        sys.exit(1)


async def cmd_run(args):
    """Run a full campaign."""
    import logging
    from campaigns.campaign_runner_v2 import CampaignRunnerV2, CampaignConfig, PipelineConfig
    
    # Setup logging
    Path('campaigns/output').mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('campaigns/output/campaign.log')
        ]
    )
    
    # Determine strategy weights
    if args.strategy == 'direct':
        direct_weight, linkedin_weight = 0.90, 0.10
    elif args.strategy == 'linkedin':
        direct_weight, linkedin_weight = 0.30, 0.70
    else:  # balanced
        direct_weight, linkedin_weight = 0.70, 0.30
    
    # Create config
    profile_path = Path(args.profile)
    if not profile_path.exists() and not profile_path.is_absolute():
        profile_path = Path('campaigns/profiles') / profile_path
    
    # Auto-detect resume path if not specified
    resume_path = args.resume
    if not resume_path:
        # Try to find resume based on profile name
        profile_name = profile_path.stem
        possible_resumes = [
            Path(f'Test Resumes/{profile_name.replace("_", " ").title()}_Resume.pdf'),
            Path(f'Test Resumes/{profile_name}_Resume.pdf'),
            Path('Test Resumes/Kevin_Beltran_Resume.pdf'),  # Default
        ]
        for path in possible_resumes:
            if path.exists():
                resume_path = str(path)
                break
        if not resume_path:
            resume_path = 'Test Resumes/Kevin_Beltran_Resume.pdf'
    
    config = CampaignConfig(
        profile_path=profile_path,
        resume_path=Path(resume_path),
        target_jobs=args.limit,
        daily_limit=args.daily_limit,
        direct_ats_weight=direct_weight,
        linkedin_weight=linkedin_weight,
        use_pipeline=not args.no_pipeline,
        use_visual_agent=not args.no_visual,
        pipeline_config=PipelineConfig(
            scrape_batch_size=50,
            apply_batch_size=5,
            max_queue_size=200,
            apply_delay_seconds=10.0,
        )
    )
    
    # Run campaign
    runner = CampaignRunnerV2(config)
    await runner.initialize()
    stats = await runner.run()
    
    # Exit with appropriate code
    success_rate = stats.success_rate
    if success_rate >= 85:
        logging.info(f"\n🎉 EXCELLENT! Success rate: {success_rate:.1f}%")
        sys.exit(0)
    elif success_rate >= 70:
        logging.info(f"\n✅ GOOD! Success rate: {success_rate:.1f}%")
        sys.exit(0)
    else:
        logging.warning(f"\n⚠️ NEEDS IMPROVEMENT. Success rate: {success_rate:.1f}%")
        sys.exit(1)


async def cmd_test(args):
    """Run test mode (dry run with limited jobs)."""
    import logging
    from campaigns.campaign_runner_v2 import CampaignRunnerV2, CampaignConfig
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    
    logging.info("=" * 60)
    logging.info("TEST MODE - Dry Run (No actual applications)")
    logging.info("=" * 60)
    
    # This is a dry run - we just test the components
    profile_path = Path(args.profile)
    if not profile_path.exists() and not profile_path.is_absolute():
        profile_path = Path('campaigns/profiles') / profile_path
    
    # Run with limited settings
    config = CampaignConfig(
        profile_path=profile_path,
        resume_path=Path('Test Resumes/Kevin_Beltran_Resume.pdf'),
        target_jobs=args.jobs,
        daily_limit=args.jobs,
        use_pipeline=False,
        use_visual_agent=True,
    )
    
    # Just initialize to test components
    runner = CampaignRunnerV2(config)
    await runner.initialize()
    
    logging.info("\n✅ All components initialized successfully!")
    logging.info("Ready for full campaign run.")


async def cmd_validate():
    """Validate all campaign components."""
    import logging
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("VALIDATING CAMPAIGN COMPONENTS")
    logger.info("=" * 60)
    
    errors = []
    warnings = []
    
    # 1. Check Python version
    import sys
    logger.info(f"\n[1/10] Python Version: {sys.version.split()[0]}")
    if sys.version_info < (3, 10):
        errors.append("Python 3.10+ required")
    else:
        logger.info("  ✅ OK")
    
    # 2. Check environment variables
    logger.info("\n[2/10] Environment Variables:")
    import os
    required_vars = ['MOONSHOT_API_KEY', 'BROWSERBASE_API_KEY']
    optional_vars = ['TWOCAPTCHA_API_KEY', 'CAPSOLVER_API_KEY']
    
    for var in required_vars:
        if os.getenv(var):
            logger.info(f"  ✅ {var}: Set")
        else:
            errors.append(f"Missing required: {var}")
    
    for var in optional_vars:
        if os.getenv(var):
            logger.info(f"  ✅ {var}: Set (optional)")
        else:
            logger.info(f"  ⚠️  {var}: Not set (optional)")
    
    # 3. Check required files
    logger.info("\n[3/10] Required Files:")
    required_files = [
        'campaigns/profiles/kevin_beltran.yaml',
        'Test Resumes/Kevin_Beltran_Resume.pdf',
    ]
    for path in required_files:
        if Path(path).exists():
            logger.info(f"  ✅ {path}")
        else:
            errors.append(f"Missing file: {path}")
    
    # 4. Check cookie file
    logger.info("\n[4/10] LinkedIn Cookies:")
    cookie_file = Path('campaigns/cookies/linkedin_cookies.json')
    if cookie_file.exists():
        import json
        try:
            with open(cookie_file) as f:
                cookies = json.load(f)
            logger.info(f"  ✅ Found {len(cookies)} cookies")
            # Check for li_at
            li_at = [c for c in cookies if c.get('name') == 'li_at']
            if li_at:
                logger.info(f"  ✅ li_at cookie present")
            else:
                warnings.append("li_at cookie not found - authentication may fail")
        except Exception as e:
            errors.append(f"Invalid cookie file: {e}")
    else:
        errors.append("LinkedIn cookie file not found")
    
    # 5. Check imports
    logger.info("\n[5/10] Python Dependencies:")
    modules = [
        ('playwright', 'Playwright'),
        ('yaml', 'PyYAML'),
        ('PIL', 'Pillow'),
        ('openai', 'OpenAI'),
    ]
    for module, name in modules:
        try:
            __import__(module)
            logger.info(f"  ✅ {name}")
        except ImportError:
            errors.append(f"Missing module: {name} ({module})")
    
    # 6. Check Direct ATS scrapers
    logger.info("\n[6/10] Direct ATS Scrapers:")
    try:
        from adapters.job_boards.direct_scrapers import (
            GreenhouseDirectScraper,
            LeverDirectScraper,
            WorkdayDirectScraper
        )
        logger.info(f"  ✅ Greenhouse: {len(GreenhouseDirectScraper.COMPANIES)} companies")
        logger.info(f"  ✅ Lever: {len(LeverDirectScraper.COMPANIES)} companies")
        logger.info(f"  ✅ Workday: {len(WorkdayDirectScraper.COMPANIES)} companies")
        total = len(GreenhouseDirectScraper.COMPANIES) + len(LeverDirectScraper.COMPANIES) + len(WorkdayDirectScraper.COMPANIES)
        logger.info(f"  ✅ Total: {total} companies")
    except Exception as e:
        errors.append(f"Direct ATS scrapers error: {e}")
    
    # 7. Check Visual Form Agent
    logger.info("\n[7/10] Visual Form Agent:")
    try:
        from ai.visual_form_agent import VisualFormAgent
        logger.info("  ✅ VisualFormAgent importable")
    except Exception as e:
        warnings.append(f"Visual Form Agent: {e}")
    
    # 8. Check LinkedIn handler
    logger.info("\n[8/10] LinkedIn Handler:")
    try:
        from adapters.handlers.linkedin_easy_apply import LinkedInEasyApplyHandler
        handler = LinkedInEasyApplyHandler()
        logger.info("  ✅ LinkedInEasyApplyHandler initialized")
        logger.info(f"  ✅ {len(handler.APPLY_BUTTON_SELECTORS)} button selectors")
    except Exception as e:
        errors.append(f"LinkedIn handler error: {e}")
    
    # 9. Check CAPTCHA solver
    logger.info("\n[9/10] CAPTCHA Solver:")
    try:
        from adapters.handlers.captcha_solver import CaptchaSolver
        solver = CaptchaSolver()
        if solver.twocaptcha_key:
            logger.info("  ✅ 2captcha configured")
        elif solver.capsolver_key:
            logger.info("  ✅ Capsolver configured")
        else:
            warnings.append("No CAPTCHA service configured (optional)")
    except Exception as e:
        warnings.append(f"CAPTCHA solver: {e}")
    
    # 10. Check output directory
    logger.info("\n[10/10] Output Directory:")
    output_dir = Path('campaigns/output')
    if output_dir.exists():
        logger.info(f"  ✅ {output_dir} exists")
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"  ✅ Created {output_dir}")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("VALIDATION SUMMARY")
    logger.info("=" * 60)
    
    if errors:
        logger.error(f"\n❌ ERRORS ({len(errors)}):")
        for err in errors:
            logger.error(f"  - {err}")
    
    if warnings:
        logger.warning(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for warn in warnings:
            logger.warning(f"  - {warn}")
    
    if not errors and not warnings:
        logger.info("\n🎉 ALL CHECKS PASSED!")
        sys.exit(0)
    elif not errors:
        logger.info("\n✅ READY (with warnings)")
        sys.exit(0)
    else:
        logger.error("\n❌ VALIDATION FAILED")
        sys.exit(1)


def cmd_stats(args):
    """Show campaign statistics."""
    import json
    from pathlib import Path
    
    output_dir = Path('campaigns/output')
    if not output_dir.exists():
        print("No campaign output found")
        return
    
    # Find latest campaign file
    campaign_files = sorted(output_dir.glob('campaign_*.json'), reverse=True)
    
    if not campaign_files:
        print("No campaign results found")
        return
    
    if args.campaign_id:
        target_file = output_dir / f"campaign_{args.campaign_id}.json"
    else:
        target_file = campaign_files[0]
    
    if not target_file.exists():
        print(f"Campaign not found: {target_file}")
        return
    
    with open(target_file) as f:
        data = json.load(f)
    
    stats = data['stats']
    
    print("\n" + "=" * 60)
    print(f"CAMPAIGN STATISTICS: {target_file.stem}")
    print("=" * 60)
    print(f"Duration: {stats['elapsed_minutes']:.1f} minutes")
    print(f"\nJobs Discovered: {stats['jobs_discovered']}")
    print(f"  Direct ATS: {stats['jobs_from_direct_ats']}")
    print(f"  LinkedIn: {stats['jobs_from_linkedin']}")
    print(f"\nApplications:")
    print(f"  Attempted: {stats['applications_attempted']}")
    print(f"  Successful: {stats['applications_successful']}")
    print(f"  Failed: {stats['applications_failed']}")
    print(f"\n🎯 SUCCESS RATE: {stats['success_rate']:.1f}%")
    
    if stats['success_rate'] >= 85:
        print("\n🎉 EXCELLENT performance!")
    elif stats['success_rate'] >= 70:
        print("\n✅ GOOD performance")
    else:
        print("\n⚠️  Needs improvement")
    
    print("\nBy Platform:")
    for platform, pstats in stats.get('platform_stats', {}).items():
        rate = (pstats['successful'] / pstats['attempted'] * 100) if pstats['attempted'] > 0 else 0
        print(f"  {platform}: {pstats['successful']}/{pstats['attempted']} ({rate:.1f}%)")
    
    print("=" * 60)


if __name__ == '__main__':
    main()
