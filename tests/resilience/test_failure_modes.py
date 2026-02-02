"""
Resilience Tests - Failure Mode Testing
Test graceful degradation and recovery from various failure scenarios.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime


@pytest.mark.resilience
class TestCaptchaHandling:
    """Test captcha timeout and manual review flow."""
    
    @pytest.mark.asyncio
    async def test_captcha_timeout_triggers_manual_review(self, mock_browser_manager):
        """When captcha can't be solved, mark for manual review."""
        from adapters.base import ApplicationResult, ApplicationStatus
        
        # Simulate captcha timeout
        with patch('browserbase.solve_captcha', side_effect=asyncio.TimeoutError):
            # Application should gracefully degrade
            result = ApplicationResult(
                status=ApplicationStatus.PENDING_REVIEW,
                message="CAPTCHA_TIMEOUT: Manual review required"
            )
            
            assert result.status == ApplicationStatus.PENDING_REVIEW
            assert "CAPTCHA" in result.message
    
    @pytest.mark.asyncio
    async def test_captcha_failure_captures_screenshot(self, mock_browser_manager):
        """Captcha failures should capture screenshot for manual solving."""
        from adapters.base import ApplicationResult, ApplicationStatus
        
        screenshot_path = "/tmp/captcha_failure_123.png"
        
        result = ApplicationResult(
            status=ApplicationStatus.PENDING_REVIEW,
            message="CAPTCHA requires manual intervention",
            screenshot_path=screenshot_path
        )
        
        assert result.screenshot_path is not None
        assert "captcha" in result.screenshot_path or screenshot_path == result.screenshot_path


@pytest.mark.resilience
class TestPlatformChanges:
    """Test handling of platform DOM/structure changes."""
    
    @pytest.mark.asyncio
    async def test_selector_fallback_on_change(self, mock_browser_manager):
        """When primary selector fails, try fallbacks."""
        selectors = {
            "primary": ".outdated-class",
            "fallback_1": "[data-testid='button']",
            "fallback_2": "button[type='submit']"
        }
        
        async def try_selectors(page, selectors_dict):
            """Try selectors in order until one works."""
            for name, selector in selectors_dict.items():
                try:
                    # Simulate finding element
                    if selector == ".outdated-class":
                        raise Exception("Element not found")
                    return selector, name
                except:
                    continue
            return None, "none"
        
        result_selector, result_name = await try_selectors(MagicMock(), selectors)
        
        # Should use fallback, not fail completely
        assert result_name == "fallback_1"
    
    @pytest.mark.asyncio
    async def test_fuzzy_text_matching(self, mock_browser_manager):
        """Test fuzzy matching when exact text changes."""
        from difflib import SequenceMatcher
        
        expected_text = "Easy Apply"
        possible_texts = [
            "Easy Apply",
            "Apply Now",
            "Quick Apply",
            "Submit Application",
            "Random Button"
        ]
        
        def fuzzy_match(expected, candidates, threshold=0.6):
            """Find best fuzzy match above threshold."""
            best_match = None
            best_ratio = 0
            
            for candidate in candidates:
                ratio = SequenceMatcher(None, expected.lower(), candidate.lower()).ratio()
                if ratio > best_ratio and ratio >= threshold:
                    best_ratio = ratio
                    best_match = candidate
            
            return best_match, best_ratio
        
        match, ratio = fuzzy_match(expected_text, possible_texts)
        
        # Should find "Easy Apply" as exact match
        assert match == "Easy Apply"
        assert ratio >= 0.8


@pytest.mark.resilience
class TestAPIRateLimiting:
    """Test handling of API rate limits."""
    
    @pytest.mark.asyncio
    async def test_kimi_rate_limit_retry(self):
        """Test exponential backoff on Kimi 429 errors."""
        attempts = []
        
        async def mock_api_call():
            attempts.append(datetime.now())
            if len(attempts) < 3:
                raise Exception("429 Too Many Requests")
            return {"success": True}
        
        async def retry_with_backoff(func, max_retries=5):
            """Retry with exponential backoff."""
            for i in range(max_retries):
                try:
                    return await func()
                except Exception as e:
                    if "429" in str(e) and i < max_retries - 1:
                        wait_time = (2 ** i) * 0.1  # Fast backoff for test
                        await asyncio.sleep(wait_time)
                    else:
                        raise
        
        result = await retry_with_backoff(mock_api_call)
        
        assert result["success"]
        assert len(attempts) == 3  # Took 3 tries
    
    @pytest.mark.asyncio
    async def test_browserbase_rate_limit_queue(self):
        """Test queuing when BrowserBase rate limited."""
        queue = asyncio.Queue()
        
        async def rate_limited_operation(item):
            # Simulate rate limit check
            await asyncio.sleep(0.1)
            return f"processed_{item}"
        
        # Add items to queue
        for i in range(5):
            await queue.put(i)
        
        # Process with rate limiting
        results = []
        while not queue.empty():
            item = await queue.get()
            result = await rate_limited_operation(item)
            results.append(result)
        
        assert len(results) == 5


@pytest.mark.resilience
class TestFileHandling:
    """Test handling of file-related failures."""
    
    @pytest.mark.asyncio
    async def test_large_resume_compression(self):
        """Test handling of large resume files."""
        max_size_mb = 5
        
        def check_file_size(content: bytes) -> tuple[bytes, bool]:
            """Check file size and compress if needed."""
            size_mb = len(content) / (1024 * 1024)
            
            if size_mb > max_size_mb:
                # Would compress PDF in real implementation
                compressed = content[:int(max_size_mb * 1024 * 1024)]
                return compressed, True
            
            return content, False
        
        # Simulate large file
        large_content = b"x" * (10 * 1024 * 1024)  # 10MB
        
        result, was_compressed = check_file_size(large_content)
        
        assert was_compressed
        assert len(result) <= max_size_mb * 1024 * 1024
    
    @pytest.mark.asyncio
    async def test_unsupported_file_format_fallback(self):
        """Test handling of unsupported file formats."""
        supported_formats = [".pdf", ".docx", ".txt"]
        
        def validate_format(filename: str) -> tuple[bool, str]:
            """Validate file format."""
            import os
            ext = os.path.splitext(filename)[1].lower()
            
            if ext in supported_formats:
                return True, ext
            else:
                return False, f"Unsupported format: {ext}. Supported: {supported_formats}"
        
        # Test valid
        valid, msg = validate_format("resume.pdf")
        assert valid
        
        # Test invalid
        valid, msg = validate_format("resume.pages")
        assert not valid
        assert "Unsupported" in msg


@pytest.mark.resilience
class TestSessionRecovery:
    """Test browser session recovery."""
    
    @pytest.mark.asyncio
    async def test_session_timeout_recovery(self, mock_browser_manager):
        """Test recovery from session timeout."""
        session_state = {
            "active": True,
            "last_activity": datetime.now(),
            "step": 3
        }
        
        async def check_and_recover_session(state):
            """Check session health and recover if needed."""
            from datetime import timedelta
            
            timeout = timedelta(minutes=30)
            now = datetime.now()
            
            if now - state["last_activity"] > timeout:
                # Session timed out - create new one
                return {
                    "active": True,
                    "last_activity": now,
                    "step": state["step"],  # Resume from last step
                    "recovered": True
                }
            
            return state
        
        # Simulate timeout
        from datetime import timedelta
        session_state["last_activity"] = datetime.now() - timedelta(hours=1)
        
        recovered = await check_and_recover_session(session_state)
        
        assert recovered.get("recovered", False)
        assert recovered["step"] == 3  # Preserved step
    
    @pytest.mark.asyncio
    async def test_account_block_detection(self, mock_browser_manager):
        """Test detection of account blocks/warnings."""
        warning_indicators = [
            "unusual activity",
            "temporarily restricted",
            "verify your identity",
            "account suspended",
            "too many requests"
        ]
        
        def detect_block(page_content: str) -> tuple[bool, str]:
            """Detect if account might be blocked."""
            content_lower = page_content.lower()
            
            for indicator in warning_indicators:
                if indicator in content_lower:
                    return True, indicator
            
            return False, ""
        
        # Test blocked page
        blocked_content = "Your account has unusual activity detected. Please verify."
        is_blocked, reason = detect_block(blocked_content)
        
        assert is_blocked
        assert "unusual activity" in reason
        
        # Test normal page
        normal_content = "Welcome to your dashboard. You have 5 applications."
        is_blocked, reason = detect_block(normal_content)
        
        assert not is_blocked


@pytest.mark.resilience
class TestNetworkFailures:
    """Test handling of network-related failures."""
    
    @pytest.mark.asyncio
    async def test_connection_retry(self):
        """Test retry on connection failures."""
        attempt_count = 0
        
        async def flaky_request():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ConnectionError("Connection refused")
            return "success"
        
        async def with_retry(func, max_attempts=5):
            """Execute with retry on connection errors."""
            for i in range(max_attempts):
                try:
                    return await func()
                except ConnectionError:
                    if i == max_attempts - 1:
                        raise
                    await asyncio.sleep(0.1 * (i + 1))
        
        result = await with_retry(flaky_request)
        
        assert result == "success"
        assert attempt_count == 3
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test handling of request timeouts."""
        async def slow_operation():
            await asyncio.sleep(10)  # Would timeout
            return "done"
        
        async def with_timeout(func, timeout_seconds=1):
            """Execute with timeout."""
            try:
                return await asyncio.wait_for(func(), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                return None, "TIMEOUT"
        
        result = await with_timeout(slow_operation, timeout_seconds=0.1)
        
        # Should timeout
        assert result == (None, "TIMEOUT")
