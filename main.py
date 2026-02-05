#!/usr/bin/env python3
"""
Job Applier - Main Entry Point

Unified entry point for the job application automation system.

Usage:
    # Run API server
    python main.py server
    
    # Run a campaign
    python main.py campaign --profile path/to/profile.yaml --config path/to/config.yaml
    
    # Apply to single job
    python main.py apply --job-url https://... --profile path/to/profile.yaml --resume path/to/resume.pdf
"""

import os
import sys
import asyncio
import argparse
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_environment():
    """Check that required environment variables are set."""
    required = ['MOONSHOT_API_KEY', 'BROWSERBASE_API_KEY', 'BROWSERBASE_PROJECT_ID']
    missing = [var for var in required if not os.getenv(var)]
    
    if missing:
        print("❌ Missing required environment variables:")
        for var in missing:
            print(f"  - {var}")
        print("\nPlease set these in your .env file or environment.")
        return False
    
    print("✅ All required environment variables set")
    return True


def run_server(host: str = "0.0.0.0", port: int = 8080, reload: bool = False):
    """Run the FastAPI server."""
    import uvicorn
    
    print(f"🚀 Starting server on {host}:{port}")
    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


async def run_campaign(profile_path: str, config_path: str = None):
    """Run a job application campaign."""
    from core import UnifiedBrowserManager, UnifiedAIService, UserProfile
    from adapters import UnifiedPlatformAdapter
    import yaml
    
    logger.info(f"Starting campaign with profile: {profile_path}")
    
    # Load profile
    with open(profile_path) as f:
        profile_data = yaml.safe_load(f)
    
    profile = UserProfile(**profile_data)
    
    # Initialize services
    browser = UnifiedBrowserManager()
    ai = UnifiedAIService()
    
    await browser.init()
    
    try:
        # Create adapter
        adapter = UnifiedPlatformAdapter(
            user_profile=profile,
            browser_manager=browser,
            ai_service=ai
        )
        
        logger.info("Campaign initialized successfully")
        logger.info(f"User: {profile.full_name}")
        logger.info(f"Email: {profile.email}")
        
        # TODO: Implement campaign logic here
        logger.info("Campaign mode not yet fully implemented")
        
    finally:
        await browser.close_all()


async def apply_single_job(job_url: str, profile_path: str, resume_path: str):
    """Apply to a single job."""
    from core import UnifiedBrowserManager, UserProfile
    from adapters import UnifiedPlatformAdapter
    import yaml
    
    logger.info(f"Applying to: {job_url}")
    
    # Load profile
    with open(profile_path) as f:
        profile_data = yaml.safe_load(f)
    
    profile = UserProfile(**profile_data)
    
    # Initialize browser
    browser = UnifiedBrowserManager()
    await browser.init()
    
    try:
        # Create adapter and apply
        adapter = UnifiedPlatformAdapter(
            user_profile=profile,
            browser_manager=browser
        )
        
        # Get job details
        job = await adapter.get_job_details(job_url)
        logger.info(f"Job: {job.title} at {job.company}")
        
        # Apply
        from core.models import Resume
        resume = Resume(
            file_path=resume_path,
            raw_text="",  # Would be parsed
            parsed_data={}
        )
        
        result = await adapter.apply(job, resume)
        
        if result.success:
            logger.info(f"✅ Application successful! Confirmation: {result.confirmation_id}")
        else:
            logger.error(f"❌ Application failed: {result.message}")
            
    finally:
        await browser.close_all()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Job Applier - AI-powered job application automation"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Server command
    server_parser = subparsers.add_parser('server', help='Run API server')
    server_parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    server_parser.add_argument('--port', type=int, default=8080, help='Port to bind to')
    server_parser.add_argument('--reload', action='store_true', help='Enable auto-reload')
    
    # Campaign command
    campaign_parser = subparsers.add_parser('campaign', help='Run a campaign')
    campaign_parser.add_argument('--profile', required=True, help='Path to profile YAML')
    campaign_parser.add_argument('--config', help='Path to campaign config YAML')
    
    # Apply command
    apply_parser = subparsers.add_parser('apply', help='Apply to single job')
    apply_parser.add_argument('--job-url', required=True, help='Job posting URL')
    apply_parser.add_argument('--profile', required=True, help='Path to profile YAML')
    apply_parser.add_argument('--resume', required=True, help='Path to resume PDF')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Run command
    if args.command == 'server':
        run_server(args.host, args.port, args.reload)
    
    elif args.command == 'campaign':
        asyncio.run(run_campaign(args.profile, args.config))
    
    elif args.command == 'apply':
        asyncio.run(apply_single_job(args.job_url, args.profile, args.resume))


if __name__ == "__main__":
    main()
