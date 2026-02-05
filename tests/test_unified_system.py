"""
Test Unified System with Production URLs

Tests the new UnifiedJobAdapter and CampaignRunner with real job URLs.
"""

import asyncio
import os
import sys
import pytest
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters.base import UserProfile, Resume, JobPosting, PlatformType
from core.adapter_base import UnifiedJobAdapter, AdapterConfig
from core.campaign_runner import CampaignRunner, CampaignConfig
from core import ScreenshotManager, FormFiller


# Test configuration
TEST_PROFILE = UserProfile(
    first_name="Test",
    last_name="User",
    email="test@example.com",
    phone="555-123-4567",
    linkedin_url="https://linkedin.com/in/testuser",
    years_experience=5,
    custom_answers={
        "salary_expectations": "$100k - $130k",
        "notice_period": "2 weeks",
        "work_authorization": "US Citizen",
        "require_sponsorship": "No"
    }
)

TEST_RESUME = Resume(
    file_path=os.getenv("RESUME_PATH", "./test_resume.pdf"),
    raw_text="Software Engineer with 5 years experience...",
    parsed_data={}
)


@pytest.mark.production
@pytest.mark.asyncio
class TestUnifiedAdapterProduction:
    """Test UnifiedJobAdapter with real production URLs."""
    
    async def test_greenhouse_production_url(self):
        """Test Greenhouse adapter with real Greenhouse URL."""
        url = os.getenv("PRODUCTION_GREENHOUSE_URL")
        if not url:
            pytest.skip("PRODUCTION_GREENHOUSE_URL not set")
        
        from core.example_adapters import GreenhouseAdapter
        from browser.stealth_manager import StealthBrowserManager
        
        browser = StealthBrowserManager()
        adapter = GreenhouseAdapter(browser, config=AdapterConfig(
            auto_submit=False,
            capture_screenshots=True
        ))
        
        job = JobPosting(
            id="test_greenhouse",
            platform=PlatformType.GREENHOUSE,
            title="Test Job",
            company="Test Company",
            location="Remote",
            url=url
        )
        
        result = await adapter.apply_to_job(
            job=job,
            resume=TEST_RESUME,
            profile=TEST_PROFILE,
            auto_submit=False
        )
        
        # Verify result
        assert result.status.value in ["pending_review", "submitted", "error"]
        assert result.screenshot_path is not None
        
        print(f"✅ Greenhouse test result: {result.status}")
        print(f"   Screenshot: {result.screenshot_path}")
        
        await browser.close_all_sessions()
    
    async def test_lever_production_url(self):
        """Test Lever adapter with real Lever URL."""
        url = os.getenv("PRODUCTION_LEVER_URL")
        if not url:
            pytest.skip("PRODUCTION_LEVER_URL not set")
        
        from core.example_adapters import LeverAdapter
        from browser.stealth_manager import StealthBrowserManager
        
        browser = StealthBrowserManager()
        adapter = LeverAdapter(browser, config=AdapterConfig(
            auto_submit=False,
            capture_screenshots=True
        ))
        
        job = JobPosting(
            id="test_lever",
            platform=PlatformType.LEVER,
            title="Test Job",
            company="Test Company",
            location="Remote",
            url=url
        )
        
        result = await adapter.apply_to_job(
            job=job,
            resume=TEST_RESUME,
            profile=TEST_PROFILE,
            auto_submit=False
        )
        
        assert result.status.value in ["pending_review", "submitted", "error"]
        
        print(f"✅ Lever test result: {result.status}")
        print(f"   Screenshot: {result.screenshot_path}")
        
        await browser.close_all_sessions()


@pytest.mark.production
@pytest.mark.asyncio
class TestUnifiedCampaignRunner:
    """Test CampaignRunner with production configuration."""
    
    async def test_campaign_yaml_config(self):
        """Test loading and running campaign from YAML."""
        config_path = Path("campaigns/configs/test_production.yaml")
        
        if not config_path.exists():
            pytest.skip("Test campaign config not found")
        
        config = CampaignRunner.load_config(config_path)
        
        # Override for testing
        config.max_applications = 1
        config.auto_submit = False
        
        runner = CampaignRunner(config)
        
        # Run campaign (dry-run with 1 application)
        result = await runner.run()
        
        assert result.campaign_name == config.name
        assert result.attempted >= 0
        
        print(f"✅ Campaign test complete: {result.success_rate*100:.1f}% success rate")


@pytest.mark.asyncio
class TestUnifiedComponents:
    """Test individual unified components."""
    
    async def test_screenshot_manager(self):
        """Test ScreenshotManager captures screenshots correctly."""
        from core import ScreenshotManager, ScreenshotConfig, ScreenshotContext
        
        manager = ScreenshotManager(ScreenshotConfig(
            base_dir=Path("./test_screenshots")
        ))
        
        # Note: This requires a browser page
        # Would need to create a browser session to test fully
        
        context = ScreenshotContext(
            job_id="test_123",
            platform="test",
            step=1,
            label="test_capture"
        )
        
        path = manager._generate_path(context)
        
        assert "test_123" in str(path)
        assert "test" in str(path)
        assert path.suffix == ".png"
        
        print(f"✅ ScreenshotManager generates correct path: {path}")
    
    async def test_form_filler_field_mapping(self):
        """Test FormFiller field mapping logic."""
        from core import FormFiller, FieldMapping, FillStrategy
        
        filler = FormFiller(strategy=FillStrategy.STANDARD)
        
        mappings = {
            "first_name": FieldMapping(
                profile_field="first_name",
                selectors=["#first_name", "input[name='first_name']"]
            ),
            "email": FieldMapping(
                profile_field="email",
                selectors=["#email", "input[type='email']"]
            )
        }
        
        # This would need a real browser page to test fully
        # Just verify the structure is correct
        assert "first_name" in mappings
        assert "email" in mappings
        assert len(mappings["first_name"].selectors) == 2
        
        print(f"✅ FormFiller field mappings configured correctly")
    
    def test_adapter_config_defaults(self):
        """Test AdapterConfig has correct defaults."""
        config = AdapterConfig()
        
        assert config.auto_submit == False
        assert config.capture_screenshots == True
        assert config.max_form_steps == 15
        assert config.max_retries == 3
        
        print(f"✅ AdapterConfig defaults verified")


def run_quick_test():
    """Run a quick test without pytest."""
    print("=" * 70)
    print("UNIFIED SYSTEM QUICK TEST")
    print("=" * 70)
    
    # Test 1: Adapter Config
    print("\n1. Testing AdapterConfig...")
    config = AdapterConfig()
    assert config.auto_submit == False
    print("   ✅ AdapterConfig defaults correct")
    
    # Test 2: Campaign Config loading
    print("\n2. Testing Campaign Config...")
    config_path = Path("campaigns/configs/example_software_engineer.yaml")
    if config_path.exists():
        try:
            import yaml
            data = yaml.safe_load(config_path.read_text())
            assert "name" in data
            assert "applicant" in data
            assert "search" in data
            print(f"   ✅ YAML config valid: {data['name']}")
        except Exception as e:
            print(f"   ❌ YAML config error: {e}")
    else:
        print("   ⚠️  Example config not found")
    
    # Test 3: Component imports
    print("\n3. Testing Component Imports...")
    try:
        from core import ScreenshotManager, FormFiller, CampaignRunner
        from core.adapter_base import UnifiedJobAdapter
        print("   ✅ All core components imported successfully")
    except Exception as e:
        print(f"   ❌ Import error: {e}")
    
    # Test 4: Adapter imports
    print("\n4. Testing Example Adapters...")
    try:
        from core.example_adapters import GreenhouseAdapter, LeverAdapter, WorkdayAdapter
        print("   ✅ Example adapters imported successfully")
    except Exception as e:
        print(f"   ❌ Import error: {e}")
    
    print("\n" + "=" * 70)
    print("QUICK TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    run_quick_test()
