# Kent Campaign - Fix Required

## Problem Summary
Kent's campaign hit BrowserBase rate limits and is now stalled with zombie processes.

## Immediate Actions Needed

### 1. Clear Zombie Processes (Requires system restart or force kill)
```bash
# Try force kill with SIGKILL
sudo kill -9 95920 96123 96316

# Or restart the computer if processes won't die
```

### 2. Wait for BrowserBase Rate Limit Reset
- Rate limits reset after 1 minute
- Concurrent session limit may take longer
- Check BrowserBase dashboard for current usage

### 3. Reduce Concurrency for Restart
**Current (BROKEN):** 35-50 concurrent  
**Recommended:** 10-15 concurrent max

## Revised Kent Campaign Config

```python
# campaigns/kent_fixed.py
CONCURRENT_BROWSERS = 10  # Reduced from 35-50
RATE_LIMIT_DELAY = 2.0    # Seconds between session creation
MAX_SESSIONS = 50         # BrowserBase account limit
```

## Before Restarting

### Check BrowserBase Dashboard
1. Log into https://browserbase.com
2. Check current session count
3. Verify rate limit status
4. Ensure sessions are under limit

### Clear Database Stuck Jobs
```bash
sqlite3 data/job_applier.db "DELETE FROM applications WHERE status = 'pending' AND created_at < datetime('now', '-1 hour');"
```

## Restart Command

```bash
cd campaigns
python3 kent_beltran_production.py \
  --concurrent=10 \
  --delay=2.0 \
  --max-sessions=50
```

## Prevention

1. **Always start with low concurrency (5-10)**
2. **Monitor BrowserBase dashboard during run**
3. **Implement exponential backoff on 429 errors**
4. **Use session pooling with proper cleanup**
5. **Add circuit breaker for rate limits**

## Current Status
- ❌ 0 successful applications
- ❌ 68+ BrowserBase errors
- ❌ 3 zombie processes
- ⚠️ Rate limits may still be active

**Estimated time to fix:** 5-10 minutes (after processes cleared)
