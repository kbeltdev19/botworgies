#!/usr/bin/env python3
"""
Campaign Runner CLI

Run job application campaigns from YAML configuration files.
Replaces individual campaign scripts with a single configurable tool.

Usage:
    # Run a campaign
    python campaigns/run_campaign.py --config campaigns/configs/my_campaign.yaml
    
    # Run in auto-submit mode (production)
    python campaigns/run_campaign.py --config campaigns/configs/my_campaign.yaml --auto-submit
    
    # Dry run - search only, no applications
    python campaigns/run_campaign.py --config campaigns/configs/my_campaign.yaml --dry-run
    
    # Resume a failed campaign
    python campaigns/run_campaign.py --config campaigns/configs/my_campaign.yaml --resume
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.campaign_runner import CampaignRunner, CampaignConfig


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                Path("./campaign_output") / f"campaign_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            )
        ]
    )


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run job application campaigns",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic usage - review mode
    python campaigns/run_campaign.py --config my_campaign.yaml
    
    # Production - auto-submit
    python campaigns/run_campaign.py --config my_campaign.yaml --auto-submit
    
    # Dry run - search only
    python campaigns/run_campaign.py --config my_campaign.yaml --dry-run
    
    # Resume from checkpoint
    python campaigns/run_campaign.py --config my_campaign.yaml --resume
    
    # Override limits
    python campaigns/run_campaign.py --config my_campaign.yaml --max-applications 50
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        required=True,
        help='Path to campaign YAML configuration file'
    )
    
    parser.add_argument(
        '--auto-submit', '-a',
        action='store_true',
        help='Enable auto-submit mode (production)'
    )
    
    parser.add_argument(
        '--dry-run', '-d',
        action='store_true',
        help='Dry run - search only, no applications'
    )
    
    parser.add_argument(
        '--resume', '-r',
        action='store_true',
        help='Resume from previous checkpoint'
    )
    
    parser.add_argument(
        '--max-applications', '-m',
        type=int,
        help='Override max applications limit'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    return parser.parse_args()


async def main():
    """Main entry point."""
    args = parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 70)
    logger.info("CAMPAIGN RUNNER")
    logger.info("=" * 70)
    
    # Load configuration
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)
    
    logger.info(f"Loading configuration from: {config_path}")
    
    try:
        config = CampaignRunner.load_config(config_path)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    # Apply command line overrides
    if args.auto_submit:
        logger.warning("⚠️  AUTO-SUBMIT MODE ENABLED - Applications will be automatically submitted!")
        config.auto_submit = True
    
    if args.max_applications:
        logger.info(f"Overriding max applications: {args.max_applications}")
        config.max_applications = args.max_applications
    
    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - Searching only, no applications")
        config.max_applications = 0
    
    # Print campaign summary
    logger.info("\n" + "=" * 70)
    logger.info("CAMPAIGN SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Name: {config.name}")
    logger.info(f"Applicant: {config.applicant_profile.first_name} {config.applicant_profile.last_name}")
    logger.info(f"Platforms: {', '.join(config.platforms)}")
    logger.info(f"Max Applications: {config.max_applications}")
    logger.info(f"Auto-Submit: {config.auto_submit}")
    logger.info(f"Search Roles: {', '.join(config.search_criteria.roles)}")
    logger.info(f"Search Locations: {', '.join(config.search_criteria.locations)}")
    logger.info("=" * 70 + "\n")
    
    # Confirm if auto-submit
    if config.auto_submit and not args.dry_run:
        response = input("⚠️  Auto-submit is enabled. Type 'CONFIRM' to proceed: ")
        if response.strip() != "CONFIRM":
            logger.info("Aborted by user")
            sys.exit(0)
    
    # Run campaign
    runner = CampaignRunner(config)
    
    try:
        result = await runner.run()
        
        # Exit with appropriate code
        if result.success_rate < 0.3:
            logger.warning("Low success rate detected")
            sys.exit(1)
        
        sys.exit(0)
        
    except KeyboardInterrupt:
        logger.info("\nCampaign interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Campaign failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
