#!/usr/bin/env python3
"""
Application Monitoring CLI Tool

Check status of job applications, view reports, and analyze failures.

Usage:
    python scripts/check_applications.py status
    python scripts/check_applications.py report
    python scripts/check_applications.py failures --hours 24
    python scripts/check_applications.py analyze <application_id>
    python scripts/check_applications.py iteration
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from monitoring.application_monitor import get_monitor
from monitoring.iteration_engine import get_iteration_engine


def print_status():
    """Print current application status."""
    monitor = get_monitor()
    
    print("\n" + "="*70)
    print("APPLICATION MONITORING STATUS")
    print("="*70)
    
    # Platform success rates
    stats = monitor.get_platform_success_rates()
    
    if not stats:
        print("\nNo applications recorded yet.")
        return
    
    print("\nPlatform Success Rates:")
    print("-" * 70)
    print(f"{'Platform':<15} {'Attempts':<10} {'Success':<10} {'Failed':<10} {'Rate':<10}")
    print("-" * 70)
    
    for platform, data in sorted(stats.items()):
        success_rate = data['success_rate'] * 100
        print(f"{platform:<15} {data['total_attempts']:<10} "
              f"{data['successful']:<10} {data['failed']:<10} "
              f"{success_rate:>6.1f}%")
    
    print("-" * 70)
    
    # Recent failures
    failures = monitor.get_recent_failures(hours=24)
    if failures:
        print(f"\n⚠️  Recent Failures (24h): {len(failures)}")
        for f in failures[:5]:
            print(f"   • {f['platform']}: {f['error_message'][:50]}...")
    else:
        print("\n✅ No failures in the last 24 hours")
    
    print("="*70 + "\n")


def print_report():
    """Print daily report."""
    monitor = get_monitor()
    report = monitor.generate_daily_report()
    print(report)


def print_failures(hours: int = 24, detailed: bool = False):
    """Print recent failures."""
    monitor = get_monitor()
    failures = monitor.get_recent_failures(hours=hours)
    
    print(f"\n{'='*70}")
    print(f"FAILURES IN LAST {hours} HOURS")
    print(f"{'='*70}\n")
    
    if not failures:
        print("✅ No failures recorded!")
        return
    
    print(f"Total failures: {len(failures)}\n")
    
    for i, failure in enumerate(failures, 1):
        print(f"{i}. Application: {failure['application_id']}")
        print(f"   Platform: {failure['platform']}")
        print(f"   Time: {failure['timestamp']}")
        print(f"   URL: {failure['job_url'][:70]}...")
        print(f"   Error: {failure['error_message']}")
        print()
        
        if detailed:
            # Get full report
            report = monitor.get_application_report(failure['application_id'])
            if 'events' in report:
                print("   Event Log:")
                for event in report['events'][-5:]:  # Last 5 events
                    print(f"     [{event['timestamp']}] {event['type']}: {event['message'][:60]}")
                print()
    
    print("="*70 + "\n")


def analyze_application(application_id: str):
    """Analyze a specific application."""
    monitor = get_monitor()
    engine = get_iteration_engine()
    
    print(f"\n{'='*70}")
    print(f"APPLICATION ANALYSIS: {application_id}")
    print(f"{'='*70}\n")
    
    # Get report
    report = monitor.get_application_report(application_id)
    
    if "error" in report:
        print(f"❌ {report['error']}")
        return
    
    metrics = report['metrics']
    events = report['events']
    
    print("Metrics:")
    print(f"  Platform: {metrics['platform']}")
    print(f"  Job URL: {metrics['job_url']}")
    print(f"  Status: {metrics['final_status']}")
    print(f"  Success: {'✅ Yes' if metrics['success'] else '❌ No'}")
    print(f"  Duration: {metrics['duration_seconds']:.1f}s")
    print(f"  Steps: {metrics['steps_completed']}")
    print(f"  Fields Filled: {metrics['fields_filled']}")
    print(f"  Confirmation: {metrics['confirmation_id'] or 'N/A'}")
    print()
    
    # Event timeline
    print("Event Timeline:")
    print("-" * 70)
    for event in events:
        status = "✅" if event.get('success') else "❌" if event.get('success') == False else "•"
        print(f"{status} [{event['timestamp']}] {event['type']}")
        print(f"    {event['message']}")
        if event.get('screenshot'):
            print(f"    Screenshot: {event['screenshot']}")
        print()
    
    # Failure analysis if failed
    if not metrics['success']:
        print("-" * 70)
        print("Failure Analysis:")
        analysis = engine.analyze_failure(application_id)
        if analysis:
            print(f"  Pattern: {analysis.failure_pattern.value}")
            print(f"  Confidence: {analysis.confidence*100:.0f}%")
            print(f"  Root Cause: {analysis.root_cause}")
            print(f"  Suggested Fix: {analysis.suggested_fix}")
            
            # Get adjustments
            adjustments = engine.generate_adjustments(analysis)
            if adjustments:
                print("\n  Strategy Adjustments:")
                for adj in adjustments:
                    print(f"    • {adj.parameter}: {adj.new_value} ({adj.reason})")
        else:
            print("  Could not determine failure pattern")
    
    print("="*70 + "\n")


def print_iteration_report():
    """Print iteration engine report."""
    engine = get_iteration_engine()
    report = engine.get_iteration_report(hours=24)
    print(report)


def main():
    parser = argparse.ArgumentParser(
        description="Monitor job application submissions"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Status command
    subparsers.add_parser('status', help='Show current status')
    
    # Report command
    subparsers.add_parser('report', help='Show daily report')
    
    # Failures command
    failures_parser = subparsers.add_parser('failures', help='Show recent failures')
    failures_parser.add_argument('--hours', type=int, default=24, help='Hours to look back')
    failures_parser.add_argument('--detailed', action='store_true', help='Show detailed logs')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze specific application')
    analyze_parser.add_argument('application_id', help='Application ID to analyze')
    
    # Iteration command
    subparsers.add_parser('iteration', help='Show iteration report')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == 'status':
        print_status()
    elif args.command == 'report':
        print_report()
    elif args.command == 'failures':
        print_failures(args.hours, args.detailed)
    elif args.command == 'analyze':
        analyze_application(args.application_id)
    elif args.command == 'iteration':
        print_iteration_report()


if __name__ == "__main__":
    main()
