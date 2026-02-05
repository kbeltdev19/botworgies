#!/usr/bin/env python3
"""
Campaign Monitor - Real-time dashboard for tracking job application progress.

Usage:
    python campaigns/monitor.py --log campaigns/output/kevin_live.log
    python campaigns/monitor.py --watch  # Auto-find latest log
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


class CampaignMonitor:
    """Monitor campaign progress in real-time."""
    
    def __init__(self, log_file: str):
        self.log_file = Path(log_file)
        self.stats = {
            'jobs_scraped': 0,
            'jobs_processed': 0,
            'jobs_succeeded': 0,
            'jobs_failed': 0,
            'jobs_skipped': 0,
            'easy_apply': 0,
            'external_redirect': 0,
            'captcha_hits': 0,
            'rate_limited': 0,
            'by_platform': {},
        }
        self.errors = []
        self.last_position = 0
        
    def parse_log_line(self, line: str):
        """Parse a log line and update stats."""
        # Jobs scraped
        if 'Scraped' in line and 'jobs' in line:
            match = re.search(r'Scraped (\d+) jobs', line)
            if match:
                self.stats['jobs_scraped'] = int(match.group(1))
        
        # Jobs processed
        if 'Completed batch' in line:
            match = re.search(r'Completed batch (\d+)/(\d+)', line)
            if match:
                current, total = int(match.group(1)), int(match.group(2))
                # Estimate jobs processed based on batch size
                self.stats['jobs_processed'] = min(current * 25, self.stats['jobs_scraped'])
        
        # Success/failure
        if 'status' in line.lower():
            if 'submitted' in line.lower() or 'succeeded' in line.lower():
                self.stats['jobs_succeeded'] += 1
            elif 'failed' in line.lower():
                self.stats['jobs_failed'] += 1
                self.errors.append(line.strip()[-100:])
            elif 'skipped' in line.lower():
                self.stats['jobs_skipped'] += 1
        
        # Easy Apply / External
        if '[LinkedIn] Detected Easy Apply' in line:
            self.stats['easy_apply'] += 1
        if '[LinkedIn] Detected External Apply' in line:
            self.stats['external_redirect'] += 1
        
        # CAPTCHA / Rate limit
        if 'CAPTCHA' in line or 'captcha' in line:
            self.stats['captcha_hits'] += 1
        if 'rate limit' in line.lower():
            self.stats['rate_limited'] += 1
        
        # Platform breakdown
        platform_match = re.search(r'platform[=\':\s]+(\w+)', line.lower())
        if platform_match:
            platform = platform_match.group(1)
            if platform not in self.stats['by_platform']:
                self.stats['by_platform'][platform] = {'success': 0, 'failed': 0}
    
    def update(self):
        """Read new log lines and update stats."""
        if not self.log_file.exists():
            return False
        
        with open(self.log_file, 'r') as f:
            f.seek(self.last_position)
            new_lines = f.readlines()
            self.last_position = f.tell()
        
        for line in new_lines:
            self.parse_log_line(line)
        
        return len(new_lines) > 0
    
    def display(self):
        """Display current stats."""
        # Clear screen
        print('\033[2J\033[H', end='')
        
        print("╔" + "═" * 68 + "╗")
        print("║" + " CAMPAIGN MONITOR ".center(68) + "║")
        print("╠" + "═" * 68 + "╣")
        
        # File info
        print(f"║ Log File: {str(self.log_file)[-50:]:>50} ║")
        print(f"║ Last Updated: {datetime.now().strftime('%H:%M:%S'):>50} ║")
        print("╠" + "═" * 68 + "╣")
        
        # Main stats
        print("║ 📊 OVERALL PROGRESS".ljust(69) + "║")
        print(f"║   Jobs Scraped:    {self.stats['jobs_scraped']:>6}                                 ║")
        print(f"║   Jobs Processed:  {self.stats['jobs_processed']:>6}                                 ║")
        print(f"║   ✓ Succeeded:     {self.stats['jobs_succeeded']:>6}                                 ║")
        print(f"║   ✗ Failed:        {self.stats['jobs_failed']:>6}                                 ║")
        print(f"║   ⊘ Skipped:       {self.stats['jobs_skipped']:>6}                                 ║")
        
        # Calculate success rate
        total = self.stats['jobs_succeeded'] + self.stats['jobs_failed']
        if total > 0:
            rate = (self.stats['jobs_succeeded'] / total) * 100
            print(f"║   Success Rate:    {rate:>5.1f}%                                ║")
        
        print("╠" + "═" * 68 + "╣")
        
        # LinkedIn stats
        print("║ 🔗 LINKEDIN BREAKDOWN".ljust(69) + "║")
        print(f"║   Easy Apply:      {self.stats['easy_apply']:>6}                                 ║")
        print(f"║   External Apply:  {self.stats['external_redirect']:>6}                                 ║")
        print(f"║   CAPTCHA Hits:    {self.stats['captcha_hits']:>6}                                 ║")
        print(f"║   Rate Limited:    {self.stats['rate_limited']:>6}                                 ║")
        
        print("╠" + "═" * 68 + "╣")
        
        # Platform breakdown
        if self.stats['by_platform']:
            print("║ 📱 BY PLATFORM".ljust(69) + "║")
            for platform, counts in self.stats['by_platform'].items():
                print(f"║   {platform[:15]:15s}:  ✓{counts['success']:>3}  ✗{counts['failed']:>3}                     ║")
        
        print("╠" + "═" * 68 + "╣")
        
        # Recent errors
        if self.errors:
            print("║ ⚠️  RECENT ERRORS".ljust(69) + "║")
            for error in self.errors[-3:]:
                print(f"║   {error[:60]:60s}   ║")
        
        print("╚" + "═" * 68 + "╝")
        print("\nPress Ctrl+C to exit. Refreshing every 5 seconds...")
    
    def run(self, watch_mode: bool = True):
        """Run the monitor."""
        try:
            while True:
                updated = self.update()
                self.display()
                
                if watch_mode:
                    time.sleep(5)
                else:
                    break
        except KeyboardInterrupt:
            print("\n\nMonitor stopped.")


def find_latest_log() -> Optional[Path]:
    """Find the most recent campaign log file."""
    log_dirs = [
        Path('campaigns/output'),
        Path('output'),
    ]
    
    latest = None
    latest_time = 0
    
    for log_dir in log_dirs:
        if not log_dir.exists():
            continue
        for log_file in log_dir.glob('*.log'):
            mtime = log_file.stat().st_mtime
            if mtime > latest_time:
                latest_time = mtime
                latest = log_file
    
    return latest


def main():
    parser = argparse.ArgumentParser(description='Monitor campaign progress')
    parser.add_argument('--log', type=str, help='Path to log file')
    parser.add_argument('--watch', action='store_true', help='Watch mode (auto-refresh)')
    parser.add_argument('--once', action='store_true', help='Print once and exit')
    
    args = parser.parse_args()
    
    # Find log file
    if args.log:
        log_file = args.log
    else:
        latest = find_latest_log()
        if latest:
            log_file = str(latest)
            print(f"Auto-detected log: {log_file}")
        else:
            print("No log file found. Use --log to specify.")
            sys.exit(1)
    
    # Run monitor
    monitor = CampaignMonitor(log_file)
    monitor.run(watch_mode=args.watch and not args.once)


if __name__ == '__main__':
    main()
