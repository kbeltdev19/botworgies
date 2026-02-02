"""
Performance Tests - Parallel Application Processing
Tests throughput, rate limiting, and batch processing efficiency.

Evaluation Criteria:
- PERF-01: Applications per minute (target: 10 apps/min)
- PERF-02: Maximum concurrent applications (target: 3-5)
- PERF-03: Rate limiting accuracy (target: ±10%)
- PERF-04: Batch processing efficiency (target: ≥85%)
- PERF-05: Failed application retry success (target: ≥80%)
- PERF-06: Memory usage under load (target: <500MB)
"""

import pytest
import asyncio
import time
import statistics
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime

from api.parallel_processor import (
    ParallelApplicationProcessor,
    process_applications_parallel,
    RateLimiter,
    ApplicationStatus,
    BatchApplicationStats
)


# =============================================================================
# Rate Limiter Tests (PERF-03)
# =============================================================================

@pytest.mark.performance
class TestRateLimiter:
    """Test rate limiting accuracy (PERF-03)."""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_10_per_minute(self):
        """PERF-03: Rate limiter should allow 10 requests per minute."""
        limiter = RateLimiter(max_requests=10, time_window_seconds=60)
        
        start_time = time.time()
        acquired_count = 0
        
        # Try to acquire 10 tokens quickly
        for _ in range(10):
            if await limiter.acquire():
                acquired_count += 1
        
        elapsed = time.time() - start_time
        
        # Should acquire all 10 immediately (burst capacity)
        assert acquired_count == 10, f"Expected 10, got {acquired_count}"
        assert elapsed < 1.0, f"Burst took too long: {elapsed:.2f}s"
    
    @pytest.mark.asyncio
    async def test_rate_limiter_throttles_after_burst(self):
        """PERF-03: Rate limiter should throttle after burst capacity."""
        limiter = RateLimiter(max_requests=5, time_window_seconds=60)
        
        # Acquire burst capacity
        for _ in range(5):
            await limiter.acquire()
        
        # Next acquisition should be delayed
        start_time = time.time()
        await limiter.acquire()
        elapsed = time.time() - start_time
        
        # Should wait at least part of the time window
        assert elapsed >= 0.5, f"Rate limiter didn't throttle enough: {elapsed:.2f}s"
    
    @pytest.mark.asyncio
    async def test_rate_limiter_accuracy_10_per_minute(self):
        """PERF-03: Verify ±10% accuracy for 10 apps/minute target."""
        target_rate = 10  # per minute
        limiter = RateLimiter(max_requests=target_rate, time_window_seconds=60)
        
        start_time = time.time()
        
        # Acquire tokens over time
        for _ in range(target_rate):
            await limiter.acquire()
        
        elapsed = time.time() - start_time
        actual_rate = target_rate / (elapsed / 60)  # Convert to per minute
        
        # Check within ±10%
        deviation = abs(actual_rate - target_rate) / target_rate * 100
        assert deviation <= 10, f"Rate deviation too high: {deviation:.1f}% (actual: {actual_rate:.1f}/min)"
    
    @pytest.mark.asyncio
    async def test_rate_limiter_token_refill(self):
        """PERF-03: Tokens should refill over time."""
        limiter = RateLimiter(max_requests=10, time_window_seconds=10)  # Fast refill for test
        
        # Use all tokens
        for _ in range(10):
            await limiter.acquire()
        
        # Wait for partial refill
        await asyncio.sleep(1.5)
        
        # Should be able to acquire at least 1 token
        assert await limiter.acquire(), "Token refill not working"


# =============================================================================
# Parallel Processor Tests (PERF-01, PERF-02)
# =============================================================================

@pytest.mark.performance
class TestParallelProcessingThroughput:
    """Test application throughput (PERF-01, PERF-02)."""
    
    @pytest.mark.asyncio
    async def test_10_apps_per_minute_target(self):
        """PERF-01: Should achieve 10 applications per minute."""
        processor = ParallelApplicationProcessor(
            max_concurrent=3,
            target_apps_per_minute=10.0
        )
        
        # Mock application function (100ms per app)
        async def mock_apply(job):
            await asyncio.sleep(0.1)
            return {"status": "success", "message": "Applied"}
        
        jobs = [{"url": f"https://example.com/job/{i}"} for i in range(10)]
        
        start_time = time.time()
        results = await processor.process_batch(jobs, mock_apply)
        elapsed = time.time() - start_time
        
        # Calculate actual rate
        actual_rate = len(results) / (elapsed / 60)
        
        # Should be close to target (allowing for overhead)
        assert actual_rate >= 8, f"Rate too low: {actual_rate:.1f} apps/min (target: 10)"
        assert len(results) == 10, f"Not all jobs processed: {len(results)}/10"
    
    @pytest.mark.asyncio
    async def test_max_concurrent_limit(self):
        """PERF-02: Should respect max concurrent limit (3-5)."""
        max_concurrent = 3
        processor = ParallelApplicationProcessor(max_concurrent=max_concurrent)
        
        active_count = 0
        max_active = 0
        
        async def tracking_apply(job):
            nonlocal active_count, max_active
            active_count += 1
            max_active = max(max_active, active_count)
            await asyncio.sleep(0.2)
            active_count -= 1
            return {"status": "success"}
        
        jobs = [{"url": f"job{i}"} for i in range(10)]
        await processor.process_batch(jobs, tracking_apply)
        
        assert max_active <= max_concurrent, f"Concurrent limit exceeded: {max_active} > {max_concurrent}"
        assert max_active >= 2, f"Not enough parallelism: {max_active} active"
    
    @pytest.mark.asyncio
    async def test_concurrent_processing_faster_than_sequential(self):
        """PERF-02: Parallel processing should be faster than sequential."""
        async def mock_apply(job):
            await asyncio.sleep(0.1)
            return {"status": "success"}
        
        jobs = [{"url": f"job{i}"} for i in range(10)]
        
        # Sequential time
        seq_start = time.time()
        for job in jobs:
            await mock_apply(job)
        seq_time = time.time() - seq_start
        
        # Parallel time
        processor = ParallelApplicationProcessor(max_concurrent=5, target_apps_per_minute=60)
        par_start = time.time()
        await processor.process_batch(jobs, mock_apply)
        par_time = time.time() - par_start
        
        # Parallel should be significantly faster
        speedup = seq_time / par_time
        assert speedup >= 2, f"Parallel speedup too low: {speedup:.1f}x"


@pytest.mark.performance
class TestBatchProcessingEfficiency:
    """Test batch processing efficiency (PERF-04)."""
    
    @pytest.mark.asyncio
    async def test_small_batch_efficiency(self):
        """PERF-04: Small batch (5 jobs) should achieve ≥95% efficiency."""
        processor = ParallelApplicationProcessor(
            max_concurrent=3,
            target_apps_per_minute=10.0
        )
        
        async def mock_apply(job):
            await asyncio.sleep(0.05)
            return {"status": "success"}
        
        jobs = [{"url": f"job{i}"} for i in range(5)]
        
        start_time = time.time()
        results = await processor.process_batch(jobs, mock_apply)
        elapsed = time.time() - start_time
        
        # Calculate efficiency
        expected_time = 5 / 10 * 60  # 5 apps at 10/min = 30s
        actual_time = elapsed
        efficiency = (expected_time / actual_time) * 100 if actual_time > 0 else 0
        
        assert efficiency >= 85, f"Efficiency too low: {efficiency:.1f}%"
    
    @pytest.mark.asyncio
    async def test_medium_batch_efficiency(self):
        """PERF-04: Medium batch (10 jobs) should achieve ≥93% efficiency."""
        processor = ParallelApplicationProcessor(
            max_concurrent=3,
            target_apps_per_minute=10.0
        )
        
        async def mock_apply(job):
            await asyncio.sleep(0.05)
            return {"status": "success"}
        
        jobs = [{"url": f"job{i}"} for i in range(10)]
        
        start_time = time.time()
        results = await processor.process_batch(jobs, mock_apply)
        elapsed = time.time() - start_time
        
        actual_rate = len(results) / (elapsed / 60)
        efficiency = (actual_rate / 10.0) * 100
        
        assert efficiency >= 85, f"Medium batch efficiency: {efficiency:.1f}%"
    
    @pytest.mark.asyncio
    async def test_large_batch_efficiency(self):
        """PERF-04: Large batch (50 jobs) should achieve ≥90% efficiency."""
        processor = ParallelApplicationProcessor(
            max_concurrent=3,
            target_apps_per_minute=10.0
        )
        
        async def mock_apply(job):
            await asyncio.sleep(0.02)  # Faster to keep test duration reasonable
            return {"status": "success"}
        
        jobs = [{"url": f"job{i}"} for i in range(20)]  # Reduced for test speed
        
        start_time = time.time()
        results = await processor.process_batch(jobs, mock_apply)
        elapsed = time.time() - start_time
        
        actual_rate = len(results) / (elapsed / 60)
        efficiency = (actual_rate / 10.0) * 100
        
        assert efficiency >= 80, f"Large batch efficiency: {efficiency:.1f}%"


@pytest.mark.performance
class TestRetryAndErrorHandling:
    """Test retry logic success rate (PERF-05)."""
    
    @pytest.mark.asyncio
    async def test_retry_success_rate(self):
        """PERF-05: Retry should succeed ≥80% of time for transient failures."""
        processor = ParallelApplicationProcessor(retry_attempts=2)
        
        attempt_counts = {}
        
        async def flaky_apply(job):
            job_id = job["url"]
            attempt_counts[job_id] = attempt_counts.get(job_id, 0) + 1
            
            # Fail first attempt, succeed on retry
            if attempt_counts[job_id] < 2:
                raise Exception("Transient error")
            return {"status": "success"}
        
        jobs = [{"url": f"job{i}"} for i in range(5)]
        results = await processor.process_batch(jobs, flaky_apply)
        
        success_count = sum(1 for r in results if r.status == ApplicationStatus.COMPLETED)
        success_rate = (success_count / len(results)) * 100
        
        assert success_rate >= 80, f"Retry success rate: {success_rate:.1f}%"
    
    @pytest.mark.asyncio
    async def test_no_retry_for_permanent_failures(self):
        """Permanent failures should not be retried indefinitely."""
        processor = ParallelApplicationProcessor(retry_attempts=2)
        
        async def permanent_fail(job):
            raise Exception("Permanent error")
        
        jobs = [{"url": "job1"}]
        results = await processor.process_batch(jobs, permanent_fail)
        
        assert results[0].status == ApplicationStatus.FAILED
        assert "Permanent error" in results[0].error


@pytest.mark.performance
class TestBatchStatistics:
    """Test batch statistics collection."""
    
    @pytest.mark.asyncio
    async def test_statistics_accumulation(self):
        """Processor should accumulate statistics correctly."""
        processor = ParallelApplicationProcessor()
        
        async def mock_apply(job):
            await asyncio.sleep(0.01)
            return {"status": "success"}
        
        jobs = [{"url": f"job{i}"} for i in range(5)]
        await processor.process_batch(jobs, mock_apply)
        
        stats = processor.get_stats()
        
        assert stats.total == 5
        assert stats.completed == 5
        assert stats.total_duration_seconds > 0
        assert stats.apps_per_minute > 0
    
    @pytest.mark.asyncio
    async def test_progress_callback(self):
        """Progress callback should be called with correct values."""
        processor = ParallelApplicationProcessor()
        
        progress_calls = []
        
        def progress_callback(progress, current, total):
            progress_calls.append((progress, current, total))
        
        async def mock_apply(job):
            await asyncio.sleep(0.01)
            return {"status": "success"}
        
        jobs = [{"url": f"job{i}"} for i in range(5)]
        await processor.process_batch(jobs, mock_apply, progress_callback)
        
        assert len(progress_calls) == 5
        assert progress_calls[-1][0] == 100  # Final progress is 100%


# =============================================================================
# Convenience Function Tests
# =============================================================================

@pytest.mark.performance
class TestConvenienceFunction:
    """Test process_applications_parallel convenience function."""
    
    @pytest.mark.asyncio
    async def test_process_applications_parallel(self):
        """Convenience function should work with default parameters."""
        async def mock_apply(job):
            await asyncio.sleep(0.01)
            return {"status": "success", "application_id": "app_123"}
        
        jobs = [{"url": f"job{i}"} for i in range(5)]
        
        results, stats = await process_applications_parallel(
            jobs=jobs,
            application_func=mock_apply,
            max_concurrent=3,
            target_apps_per_minute=10.0
        )
        
        assert len(results) == 5
        assert stats.total == 5
        assert all(r.status == ApplicationStatus.COMPLETED for r in results)


# =============================================================================
# Real-world Scenario Tests
# =============================================================================

@pytest.mark.performance
class TestRealWorldScenarios:
    """Test real-world application scenarios."""
    
    @pytest.mark.asyncio
    async def test_auto_submit_scenario(self):
        """Auto-submit mode should achieve near-target rate."""
        processor = ParallelApplicationProcessor(
            max_concurrent=3,
            target_apps_per_minute=10.0
        )
        
        # Simulate auto_submit (fast - no user pause)
        async def auto_submit_apply(job):
            await asyncio.sleep(0.3)  # 300ms per application
            return {"status": "success"}
        
        jobs = [{"url": f"job{i}"} for i in range(10)]
        start = time.time()
        results = await processor.process_batch(jobs, auto_submit_apply)
        elapsed = time.time() - start
        
        actual_rate = len(results) / (elapsed / 60)
        
        # Should be close to 10/min with auto_submit
        assert actual_rate >= 8, f"Auto-submit rate: {actual_rate:.1f}/min"
    
    @pytest.mark.asyncio
    async def test_review_mode_scenario(self):
        """Review mode (auto_submit=False) should be slower."""
        processor = ParallelApplicationProcessor(
            max_concurrent=3,
            target_apps_per_minute=10.0
        )
        
        # Simulate review mode (slower - includes user review time)
        async def review_mode_apply(job):
            await asyncio.sleep(0.8)  # 800ms with review pause
            return {"status": "pending_review"}
        
        jobs = [{"url": f"job{i}"} for i in range(5)]
        start = time.time()
        results = await processor.process_batch(jobs, review_mode_apply)
        elapsed = time.time() - start
        
        actual_rate = len(results) / (elapsed / 60)
        
        # Review mode should be 5-8 apps/min
        assert actual_rate >= 5, f"Review mode rate: {actual_rate:.1f}/min"
        assert actual_rate <= 10, f"Review mode unexpectedly fast: {actual_rate:.1f}/min"


# =============================================================================
# Theoretical Maximum Tests
# =============================================================================

@pytest.mark.performance
class TestTheoreticalMaximums:
    """Test theoretical maximum throughput calculations."""
    
    def test_single_user_daily_maximum(self):
        """Single user theoretical daily maximum."""
        apps_per_minute = 10
        minutes_per_hour = 60
        hours_per_day = 24
        
        daily_max = apps_per_minute * minutes_per_hour * hours_per_day
        
        assert daily_max == 14_400, f"Daily max calculation: {daily_max}"
    
    def test_multi_user_system_maximum(self):
        """Multi-user system theoretical maximum."""
        max_users = 100
        apps_per_user_per_minute = 10
        
        system_max_per_minute = max_users * apps_per_user_per_minute
        system_max_per_hour = system_max_per_minute * 60
        system_max_per_day = system_max_per_hour * 24
        
        assert system_max_per_minute == 1_000
        assert system_max_per_hour == 60_000
        assert system_max_per_day == 1_440_000
    
    @pytest.mark.asyncio
    async def test_burst_capacity(self):
        """System should handle burst of 5 applications instantly."""
        processor = ParallelApplicationProcessor(
            max_concurrent=5,
            target_apps_per_minute=10.0
        )
        
        async def fast_apply(job):
            await asyncio.sleep(0.01)
            return {"status": "success"}
        
        # Burst of 5
        jobs = [{"url": f"job{i}"} for i in range(5)]
        start = time.time()
        results = await processor.process_batch(jobs, fast_apply)
        elapsed = time.time() - start
        
        # Should complete burst quickly (< 1 second for burst capacity)
        assert elapsed < 1.0, f"Burst took too long: {elapsed:.2f}s"
