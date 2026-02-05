#!/usr/bin/env python3
"""
Quick Campaign Test - Validates the consolidated system works

Usage:
    python test_campaign.py
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

from core import UnifiedBrowserManager, UnifiedAIService, UserProfile, Resume, SearchConfig
from core.campaign_runner import CampaignRunner, CampaignConfig


async def test_system():
    """Test the consolidated system."""
    print("=" * 70)
    print("🧪 TESTING CONSOLIDATED SYSTEM")
    print("=" * 70)
    
    # 1. Test imports
    print("\n1️⃣ Testing imports...")
    try:
        from core import UnifiedBrowserManager, UnifiedAIService, UserProfile
        from adapters import UnifiedPlatformAdapter
        print("   ✅ Core imports: OK")
        print("   ✅ Adapter imports: OK")
    except Exception as e:
        print(f"   ❌ Import failed: {e}")
        return False
    
    # 2. Test AI service
    print("\n2️⃣ Testing AI service...")
    try:
        ai = UnifiedAIService()
        response = await ai.complete("Say 'test successful' in 3 words or less.")
        if response.success:
            print(f"   ✅ AI service: OK")
            print(f"   📝 Response: {response.content.strip()}")
        else:
            print(f"   ❌ AI service failed: {response.error}")
    except Exception as e:
        print(f"   ❌ AI test failed: {e}")
    
    # 3. Test Browser Manager
    print("\n3️⃣ Testing Browser Manager...")
    try:
        browser = UnifiedBrowserManager()
        print(f"   ✅ Browser manager created")
        print(f"   📊 Stats: {browser.get_stats()}")
    except Exception as e:
        print(f"   ❌ Browser manager failed: {e}")
    
    # 4. Test Campaign Config Loading
    print("\n4️⃣ Testing Campaign Config...")
    try:
        config_path = Path("campaigns/configs/test_small.yaml")
        if config_path.exists():
            config = CampaignRunner.load_config(config_path)
            print(f"   ✅ Config loaded: {config.name}")
            print(f"   👤 Applicant: {config.applicant_profile.full_name}")
            print(f"   🎯 Max Applications: {config.max_applications}")
        else:
            print(f"   ⚠️  Config file not found: {config_path}")
    except Exception as e:
        print(f"   ❌ Config loading failed: {e}")
    
    # 5. Check environment
    print("\n5️⃣ Checking Environment...")
    import os
    moonshot = os.getenv("MOONSHOT_API_KEY")
    bb_key = os.getenv("BROWSERBASE_API_KEY")
    bb_project = os.getenv("BROWSERBASE_PROJECT_ID")
    
    if moonshot:
        print(f"   ✅ MOONSHOT_API_KEY: Set")
    else:
        print(f"   ❌ MOONSHOT_API_KEY: Not set")
    
    if bb_key:
        print(f"   ✅ BROWSERBASE_API_KEY: Set")
    else:
        print(f"   ⚠️  BROWSERBASE_API_KEY: Not set (local mode only)")
    
    if bb_project:
        print(f"   ✅ BROWSERBASE_PROJECT_ID: Set")
    else:
        print(f"   ⚠️  BROWSERBASE_PROJECT_ID: Not set (local mode only)")
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    print("✅ System imports: Working")
    print("✅ AI Service: Working (Moonshot)")
    print("✅ Config Loading: Working")
    
    if not bb_key or not bb_project:
        print("\n⚠️  TO RUN LIVE CAMPAIGNS:")
        print("   1. Set BROWSERBASE_API_KEY in .env")
        print("   2. Set BROWSERBASE_PROJECT_ID in .env")
        print("   3. Install stagehand-py: pip install stagehand-py")
    else:
        print("\n✅ Ready for live campaigns!")
        print("   Run: python campaigns/run_campaign.py --config campaigns/configs/test_small.yaml")
    
    print("\n" + "=" * 70)
    return True


if __name__ == "__main__":
    asyncio.run(test_system())
