#!/bin/bash
#
# Quick 50-job test to validate error rate test before full 1000 run
#

echo "🧪 Running 50-job error rate test validation..."
echo ""

cd "$(dirname "$0")"

# Run a quick 50-job test using Python
python3 -c "
import sys
import asyncio
import os
sys.path.insert(0, '..')

# Set test mode
os.chdir('.')

from KEVIN_1000_ERROR_RATE_TEST import ProductionErrorRateTest

class QuickTest(ProductionErrorRateTest):
    def __init__(self):
        self.target = 50
        from KEVIN_1000_ERROR_RATE_TEST import ErrorRateMonitor, KEVIN_PROFILE
        self.monitor = ErrorRateMonitor(
            campaign_id='kevin_50_test',
            candidate_name='Kevin Beltran',
            target=50
        )
        from pathlib import Path
        self.output_dir = Path('output/kevin_error_rate_test')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.production_mode = False
        
        print('=' * 60)
        print('🧪 50-JOB VALIDATION TEST')
        print('=' * 60)

async def main():
    test = QuickTest()
    jobs = test.load_or_generate_jobs()[:50]
    await test.run_production_test(jobs)
    report = test.generate_error_report()
    
    print()
    print('=' * 60)
    print('✅ 50-JOB TEST COMPLETE')
    print(f'Success Rate: {report.overall_success_rate:.1f}%')
    print(f'Error Rate: {report.overall_error_rate:.1f}%')
    print('=' * 60)

asyncio.run(main())
" 2>&1

echo ""
echo "✅ Validation complete!"
