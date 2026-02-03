#!/usr/bin/env python3
"""
Real-time Monitor for Matt Edwards 1000-Job Campaign
Displays live progress, statistics, and alerts
"""

import os
import sys
import json
import time
import curses
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class CampaignMonitor:
    """Real-time terminal monitor for campaign progress."""
    
    def __init__(self):
        self.output_dir = Path(__file__).parent / "output" / "matt_edwards_production"
        self.report_file = self.output_dir / "MATT_1000_FINAL_REPORT.json"
        self.running = True
        
    def run(self, stdscr):
        """Main monitoring loop using curses."""
        # Setup curses
        curses.curs_set(0)  # Hide cursor
        stdscr.nodelay(1)   # Non-blocking input
        stdscr.timeout(1000)  # Refresh every second
        
        while self.running:
            try:
                # Clear screen
                stdscr.clear()
                
                # Get terminal size
                height, width = stdscr.getmaxyx()
                
                # Draw header
                self._draw_header(stdscr, width)
                
                # Get current stats
                stats = self._load_stats()
                
                # Draw stats
                self._draw_stats(stdscr, stats, width)
                
                # Draw progress bar
                self._draw_progress(stdscr, stats, width)
                
                # Draw recent activity
                self._draw_activity(stdscr, stats, width, height)
                
                # Draw footer
                self._draw_footer(stdscr, width, height)
                
                # Refresh
                stdscr.refresh()
                
                # Check for quit
                key = stdscr.getch()
                if key == ord('q') or key == ord('Q'):
                    self.running = False
                    
            except Exception as e:
                # Handle errors gracefully
                pass
    
    def _draw_header(self, stdscr, width):
        """Draw the header section."""
        title = "🚀 MATT EDWARDS 1000-JOB CAMPAIGN MONITOR"
        subtitle = "Real-time Production Dashboard"
        
        try:
            stdscr.addstr(0, (width - len(title)) // 2, title, curses.A_BOLD | curses.A_UNDERLINE)
            stdscr.addstr(1, (width - len(subtitle)) // 2, subtitle)
            stdscr.addstr(2, 0, "=" * width)
        except:
            pass
    
    def _load_stats(self) -> Dict:
        """Load current stats from report file."""
        default_stats = {
            "summary": {
                "total_attempted": 0,
                "successful": 0,
                "failed": 0,
                "skipped": 0,
                "success_rate": 0,
                "duration_minutes": 0,
                "apps_per_minute": 0
            },
            "by_platform": {},
            "timeline": {"start_time": None},
            "all_results": []
        }
        
        if not self.report_file.exists():
            # Try intermediate files
            intermediate_files = sorted(self.output_dir.glob("matt_edwards_intermediate_*.json"))
            if intermediate_files:
                try:
                    with open(intermediate_files[-1]) as f:
                        data = json.load(f)
                        return {
                            "summary": {
                                "total_attempted": data["stats"]["total_attempted"],
                                "successful": data["stats"]["successful"],
                                "failed": data["stats"]["failed"],
                                "skipped": data["stats"]["skipped"],
                                "success_rate": 0,
                                "duration_minutes": 0,
                                "apps_per_minute": 0
                            },
                            "by_platform": data["stats"]["by_platform"],
                            "all_results": data["results"]
                        }
                except:
                    pass
            return default_stats
        
        try:
            with open(self.report_file) as f:
                return json.load(f)
        except:
            return default_stats
    
    def _draw_stats(self, stdscr, stats: Dict, width):
        """Draw statistics section."""
        summary = stats.get("summary", {})
        
        lines = [
            "",
            f"  📊 OVERALL PROGRESS",
            f"  ├─ Attempted:    {summary.get('total_attempted', 0):4d} / 1000",
            f"  ├─ Successful:   {summary.get('successful', 0):4d} ({summary.get('success_rate', 0):.1f}%)",
            f"  ├─ Failed:       {summary.get('failed', 0):4d}",
            f"  └─ Skipped:      {summary.get('skipped', 0):4d}",
            "",
            f"  ⏱️  PERFORMANCE",
            f"  ├─ Duration:     {summary.get('duration_minutes', 0):.1f} minutes",
            f"  ├─ Rate:         {summary.get('apps_per_minute', 0):.1f} apps/min",
            f"  └─ ETA:          {self._calculate_eta(summary):}",
        ]
        
        row = 4
        for line in lines:
            try:
                stdscr.addstr(row, 0, line[:width-1])
                row += 1
            except:
                break
    
    def _calculate_eta(self, summary: Dict) -> str:
        """Calculate estimated time remaining."""
        attempted = summary.get('total_attempted', 0)
        rate = summary.get('apps_per_minute', 0)
        
        if rate <= 0 or attempted >= 1000:
            return "Calculating..."
        
        remaining = 1000 - attempted
        eta_minutes = remaining / rate
        
        if eta_minutes < 1:
            return f"{int(eta_minutes * 60)} seconds"
        elif eta_minutes < 60:
            return f"{int(eta_minutes)} minutes"
        else:
            return f"{eta_minutes/60:.1f} hours"
    
    def _draw_progress(self, stdscr, stats: Dict, width):
        """Draw progress bar."""
        summary = stats.get("summary", {})
        attempted = summary.get('total_attempted', 0)
        percent = min(100, (attempted / 1000) * 100)
        
        bar_width = min(50, width - 20)
        filled = int(bar_width * percent / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        
        try:
            row = 16
            stdscr.addstr(row, 2, f"Progress: [{bar}] {percent:.1f}%")
        except:
            pass
    
    def _draw_activity(self, stdscr, stats: Dict, width, height):
        """Draw recent activity log."""
        results = stats.get("all_results", [])[-10:]  # Last 10
        
        try:
            row = 19
            stdscr.addstr(row, 0, "  📝 RECENT ACTIVITY")
            row += 1
            stdscr.addstr(row, 0, "  " + "-" * (width - 4))
            row += 1
            
            for result in reversed(results):
                if row >= height - 3:
                    break
                
                status = result.get('status', 'unknown')
                company = result.get('company', 'Unknown')[:20]
                title = result.get('title', 'Unknown')[:30]
                duration = result.get('duration_seconds', 0)
                
                icon = "✅" if status == "success" else "❌" if status == "failed" else "⏭️"
                line = f"  {icon} {company:20} | {title:30} | {duration:5.1f}s"
                
                stdscr.addstr(row, 0, line[:width-1])
                row += 1
        except:
            pass
    
    def _draw_footer(self, stdscr, width, height):
        """Draw footer with instructions."""
        try:
            footer_text = "Press 'Q' to quit | Auto-refreshes every second"
            stdscr.addstr(height - 1, (width - len(footer_text)) // 2, footer_text)
        except:
            pass


def simple_monitor():
    """Simple text-based monitor without curses."""
    output_dir = Path(__file__).parent / "output" / "matt_edwards_production"
    report_file = output_dir / "MATT_1000_FINAL_REPORT.json"
    
    print("\n" + "="*80)
    print("🚀 MATT EDWARDS 1000-JOB CAMPAIGN MONITOR")
    print("="*80)
    print("\nMonitoring campaign progress... (Press Ctrl+C to stop)\n")
    
    try:
        while True:
            # Load stats
            stats = {}
            if report_file.exists():
                with open(report_file) as f:
                    stats = json.load(f).get("summary", {})
            else:
                # Check intermediate files
                intermediate_files = sorted(output_dir.glob("matt_edwards_intermediate_*.json"))
                if intermediate_files:
                    with open(intermediate_files[-1]) as f:
                        data = json.load(f)
                        stats = {
                            "total_attempted": data["stats"]["total_attempted"],
                            "successful": data["stats"]["successful"],
                            "failed": data["stats"]["failed"],
                            "skipped": data["stats"]["skipped"],
                            "success_rate": 0,
                            "duration_minutes": 0,
                            "apps_per_minute": 0
                        }
            
            # Clear screen (ANSI escape)
            print("\033[2J\033[H", end="")
            
            # Print header
            print("="*80)
            print("🚀 MATT EDWARDS 1000-JOB CAMPAIGN - LIVE MONITOR")
            print("="*80)
            print(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print()
            
            # Print stats
            attempted = stats.get('total_attempted', 0)
            successful = stats.get('successful', 0)
            failed = stats.get('failed', 0)
            skipped = stats.get('skipped', 0)
            success_rate = (successful / attempted * 100) if attempted > 0 else 0
            
            print(f"📊 PROGRESS: {attempted}/1000 ({attempted/10:.1f}%)")
            print(f"   ✅ Successful: {successful} ({success_rate:.1f}%)")
            print(f"   ❌ Failed: {failed}")
            print(f"   ⏭️  Skipped: {skipped}")
            print()
            
            # Progress bar
            bar_width = 50
            filled = int(bar_width * attempted / 1000)
            bar = "█" * filled + "░" * (bar_width - filled)
            print(f"[{bar}] {attempted/10:.1f}%")
            print()
            
            # Performance
            rate = stats.get('apps_per_minute', 0)
            duration = stats.get('duration_minutes', 0)
            print(f"⏱️  Performance:")
            print(f"   Duration: {duration:.1f} minutes")
            print(f"   Rate: {rate:.1f} apps/minute")
            if rate > 0 and attempted < 1000:
                remaining = 1000 - attempted
                eta = remaining / rate
                print(f"   ETA: {eta:.1f} minutes")
            print()
            
            # Recent file check
            if intermediate_files := sorted(output_dir.glob("matt_edwards_intermediate_*.json")):
                latest = intermediate_files[-1]
                print(f"💾 Latest backup: {latest.name}")
            
            print("-"*80)
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")


if __name__ == "__main__":
    # Try curses first, fall back to simple monitor
    try:
        monitor = CampaignMonitor()
        curses.wrapper(monitor.run)
    except:
        simple_monitor()
