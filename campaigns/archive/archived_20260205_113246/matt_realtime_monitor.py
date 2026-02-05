#!/usr/bin/env python3
"""Real-time monitor for Matt's campaign"""

import json
import time
import os
from pathlib import Path
from datetime import datetime

def clear():
    os.system('clear' if os.name != 'nt' else 'cls')

def main():
    output_dir = Path(__file__).parent / "output" / "matt_edwards_real"
    
    while True:
        clear()
        
        # Find latest progress file
        progress_files = sorted(output_dir.glob("progress_*.json"))
        
        if not progress_files:
            print("Waiting for campaign to start...")
            time.sleep(5)
            continue
        
        # Load latest
        latest = progress_files[-1]
        try:
            with open(latest) as f:
                data = json.load(f)
            
            stats = data['stats']
            
            print("="*80)
            print("🚀 MATT EDWARDS 1000-JOB REAL CAMPAIGN - LIVE MONITOR")
            print("="*80)
            print(f"Last Update: {datetime.now().strftime('%H:%M:%S')}")
            print()
            
            # Progress
            attempted = stats['total_attempted']
            success = stats['successful']
            failed = stats['failed']
            skipped = stats['skipped']
            
            success_rate = (success / attempted * 100) if attempted > 0 else 0
            
            print(f"📊 PROGRESS: {attempted}/1000 ({attempted/10:.1f}%)")
            print(f"   ✅ Successful: {success} ({success_rate:.1f}%)")
            print(f"   ❌ Failed: {failed}")
            print(f"   ⏭️  Skipped: {skipped}")
            print()
            
            # Progress bar
            bar_width = 50
            filled = int(bar_width * attempted / 1000)
            bar = "█" * filled + "░" * (bar_width - filled)
            print(f"[{bar}] {attempted/10:.1f}%")
            print()
            
            # Platform breakdown
            print("🏢 By Platform:")
            for platform, pstats in stats.get('by_platform', {}).items():
                total = sum(pstats.values())
                s_rate = (pstats.get('success', 0) / total * 100) if total > 0 else 0
                print(f"   {platform:15} {pstats.get('success', 0):4d}/{total:4d} ({s_rate:.1f}%)")
            print()
            
            # Recent results
            print("📝 Recent Activity:")
            for r in data.get('results', [])[-5:]:
                icon = "✅" if r['status'] == 'success' else "❌" if r['status'] == 'failed' else "⏭️"
                print(f"   {icon} {r['company'][:25]:25} | {r['duration']:.1f}s")
            
            print()
            print(f"💾 Data: {latest.name}")
            print("="*80)
            print("Press Ctrl+C to exit monitor (campaign continues)")
            
        except Exception as e:
            print(f"Error reading data: {e}")
        
        time.sleep(10)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMonitor stopped. Campaign continues in background.")
