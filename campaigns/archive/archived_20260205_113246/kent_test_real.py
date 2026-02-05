#!/usr/bin/env python3
"""
Kent Le - Test 5 REAL Applications
Quick test with actual browser automation
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from kent_1000_real_production import RealApplicationRunner


async def main():
    print("\n" + "="*80)
    print("🧪 TEST MODE: 5 REAL APPLICATIONS")
    print("="*80)
    print("\nThis will:")
    print("  1. Find 5 real job listings")
    print("  2. Open actual browser sessions")
    print("  3. Fill real application forms")
    print("  4. Submit applications (or stop at review step)")
    print("\nEstimated time: 10-20 minutes")
    print("Estimated cost: $0.50 in BrowserBase sessions\n")
    
    runner = RealApplicationRunner(target=5)
    await runner.run()


if __name__ == "__main__":
    asyncio.run(main())
