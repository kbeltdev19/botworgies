# System Review Checklist

End-to-end review of the botworgies codebase. Goal: simplify, consolidate, archive what's unnecessary.

---

## Phase 1: Delete Dead Code

### 1.1 Dead modules in core/
- [ ] **Delete `core/captcha_solver.py`** — 82 lines, 0 active imports. Superseded by `adapters/handlers/captcha_solver.py`
- [ ] **Delete `core/proxy_manager.py`** — 79 lines, 0 active imports. Superseded by `api/proxy_manager.py`
- [ ] **Delete `core/browser_pool.py`** — 0 active imports. Superseded by `core/browser.py` (UnifiedBrowserManager)

### 1.2 Dead handler variants in adapters/handlers/
- [ ] **Delete `adapters/handlers/greenhouse_full.py`** — 19K, never imported in active code
- [ ] **Delete `adapters/handlers/greenhouse_optimized.py`** — 11K, never imported
- [ ] **Delete `adapters/handlers/lever_full.py`** — 8.8K, never imported
- [ ] **Delete `adapters/handlers/lever_optimized.py`** — 6.4K, never imported
- [ ] **Delete `adapters/handlers/workday_full.py`** — 31K, never imported
- [ ] **Delete `adapters/handlers/workday_optimized.py`** — 6.7K, never imported

### 1.3 Dead directories
- [ ] **Delete `workers/`** — empty, no Python files, Cloudflare Workers stub never deployed
- [ ] **Delete `frontend/`** — single index.html, not a deployed app
- [ ] **Delete `evaluation/`** — `evaluation_criteria.py` has 0 active imports

### 1.4 Broken code
- [ ] **Delete or fix `ats_automation/testing/live_test_runner.py`** — imports from `ats_automation.handlers.dice` which doesn't exist

---

## Phase 2: Consolidate Duplicates

### 2.1 Captcha solver (3 implementations → 1)
- [ ] Keep `adapters/handlers/captcha_solver.py` (most complete, BrowserBase Stealth support)
- [ ] Delete `core/captcha_solver.py` (Phase 1)
- [ ] Evaluate if `api/captcha_solver.py` can be replaced by `adapters/handlers/` version
- [ ] Update any imports that reference `core.captcha_solver` or `api.captcha_solver`

### 2.2 Proxy manager (2 implementations → 1)
- [ ] Keep `api/proxy_manager.py` (async, full-featured)
- [ ] Delete `core/proxy_manager.py` (Phase 1)
- [ ] Decide: move `api/proxy_manager.py` → `core/proxy_manager.py` so it lives in the foundation layer?

### 2.3 Browser module wrapper
- [ ] Evaluate if `browser/__init__.py` (re-exports from `core.browser`) is still needed
- [ ] If nothing active imports from `browser.`, delete the `browser/` directory entirely
- [ ] Update any remaining `from browser import ...` → `from core import ...`

### 2.4 ats_automation/ vs adapters/
- [ ] `ats_automation/` largely duplicates `adapters/` — decide: archive or delete?
- [ ] `ats_automation/ats_router.py` is legacy routing superseded by `adapters/unified.py`
- [ ] `ats_automation/production_*.py` scripts use old ATSRouter pattern — migrate or archive
- [ ] `ats_automation/utils/session_pool.py` — superseded by `core/browser.py`
- [ ] `ats_automation/utils/retry.py` — check if `core/error_handler.py` covers this

---

## Phase 3: Prune Archives

### 3.1 campaigns/archive/ (~2.5M)
- [ ] `campaigns/archive/archived_20260205_113246/` — 125+ old campaign scripts
- [ ] `campaigns/archive/misc/` — old shell scripts
- [ ] Decision: delete entirely or keep one representative example?

### 3.2 archive/old_code/ (~450K)
- [ ] Old adapters, browser managers, ATS handlers, AI services
- [ ] All replaced by current unified architecture
- [ ] Decision: delete entirely? Already served its purpose as migration reference

### 3.3 docs/archive/ (~301K)
- [ ] 19 archived documentation files
- [ ] Not referenced in active code
- [ ] Decision: delete or keep for historical context?

### 3.4 campaign_output/ at root
- [ ] Check if `campaign_output/` at project root has useful data or just test artifacts
- [ ] Clean or .gitignore

---

## Phase 4: Clean Up Adapters

### 4.1 Dead platform adapters in adapters/ root
- [ ] Audit each file in `adapters/` root — which ones are actually imported by active code?
- [ ] Known active: `unified.py`, `__init__.py`
- [ ] Likely dead: individual platform adapters (`linkedin.py`, `indeed.py`, `greenhouse.py`, etc.) if UnifiedPlatformAdapter handles everything
- [ ] Decision: archive legacy adapters or keep as fallbacks?

### 4.2 adapters/job_boards/
- [ ] Audit which job board scrapers are actually used in campaign configs
- [ ] Multiple scraper implementations for same platform (e.g., `greenhouse_api.py` + `greenhouse_scraper.py`)
- [ ] Consolidate overlapping scrapers

### 4.3 adapters/handlers/
- [ ] After deleting _full/_optimized variants (Phase 1), audit what remains
- [ ] `generic_ats.py` — is this used alongside `unified.py` or superseded?
- [ ] `linkedin_easy_apply.py`, `indeed_handler.py`, `other_ats.py` — still active?
- [ ] `form_field_cache.py` — used or dead?

---

## Phase 5: Scripts & Root-Level Cleanup

### 5.1 scripts/ directory
- [ ] `kent_batch_1000.py` — user-specific, uses old patterns. Archive?
- [ ] `kimi_swarm.py` — still relevant or experimental artifact?
- [ ] `patch_jobspy_python39.py` — still needed? Project targets Python 3.11
- [ ] `install_python311.sh` / `install_python311_pyenv.sh` — useful utilities, keep
- [ ] `set_fly_secrets.sh` — deployment utility, keep
- [ ] `archive_campaigns.py` — utility, keep
- [ ] `check_applications.py` — utility, keep

### 5.2 Root-level files
- [ ] `test_campaign.py` — functional, uses current imports. Keep or move to tests/?
- [ ] `test_jobspy_setup.py` — setup verification. Keep or move to tests/?
- [ ] `run_live_campaign.sh` — campaign launcher. Still accurate?
- [ ] `CONSOLIDATION_SUMMARY.md` — historical, can archive to docs/archive/ or delete
- [ ] `AGENTS.md` — review if still accurate post-cleanup
- [ ] `src/` directory — empty submodule (python-jobspy). Remove if not used
- [ ] `Test Resumes/` — sample data. Keep or move into tests/fixtures/?

---

## Phase 6: Module Exports & Imports

### 6.1 core/__init__.py
- [ ] Verify all exports match surviving modules (after deleting dead code)
- [ ] Remove exports for deleted modules (captcha_solver, proxy_manager, browser_pool)
- [ ] Ensure no `ImportError` on `from core import ...`

### 6.2 adapters/__init__.py
- [ ] Verify factory function `get_adapter()` doesn't reference deleted handlers
- [ ] Clean up any dead imports

### 6.3 Circular import check
- [ ] Run a quick `python -c "from core import *"` to verify no circular imports
- [ ] Run `python -c "from adapters import *"`
- [ ] Run `python -c "from api.main import app"`

---

## Phase 7: Configuration & Infrastructure

### 7.1 wrangler.toml
- [ ] References `workers/index.js` which doesn't exist in active code
- [ ] Decision: delete wrangler.toml if Cloudflare Workers isn't being used

### 7.2 Dockerfile
- [ ] Verify it doesn't COPY deleted directories
- [ ] Verify it still builds after cleanup

### 7.3 .github/workflows/ci.yml
- [ ] Verify test paths still valid after moving/deleting files
- [ ] Verify lint/security stages cover correct directories

### 7.4 .gitignore / .dockerignore
- [ ] Add `campaign_output/` if not already ignored
- [ ] Remove entries for deleted directories

### 7.5 fly.toml
- [ ] Verify deployment config still accurate

---

## Phase 8: Documentation Update

### 8.1 ARCHITECTURE.md
- [ ] Remove references to deleted directories (workers/, frontend/, browser/)
- [ ] Update directory structure diagram
- [ ] Update component table
- [ ] Remove migration guide if old code no longer exists

### 8.2 README.md
- [ ] Verify quick start still works
- [ ] Update directory structure if shown
- [ ] Remove references to archived components

### 8.3 FEATURES.md
- [ ] Audit feature claims — are all listed features still implemented?
- [ ] Remove features tied to deleted code

### 8.4 DEPLOYMENT.md
- [ ] Remove Cloudflare Workers deployment if workers/ is deleted
- [ ] Verify Docker/Fly.io instructions still accurate

---

## Phase 9: Testing & Verification

### 9.1 Run tests
- [ ] `python -m pytest tests/ -x --ignore=tests/e2e --ignore=tests/stealth -k "not integration"`
- [ ] Fix any import errors from deleted modules
- [ ] Verify test fixtures don't reference dead code

### 9.2 Import smoke test
- [ ] `python -c "from core import UnifiedBrowserManager, UnifiedAIService"`
- [ ] `python -c "from adapters import UnifiedPlatformAdapter"`
- [ ] `python -c "from api.main import app"`
- [ ] `python main.py --help`

### 9.3 Lint
- [ ] Run `ruff check .` — no errors
- [ ] Run `black --check .` — formatting ok

---

## Summary: Impact Estimates

| Action | Files Removed | Size Freed |
|--------|--------------|------------|
| Dead core modules | 3 | ~10K |
| Dead handler variants | 6 | ~84K |
| Dead directories (workers, frontend, evaluation) | ~5 | ~95K |
| campaigns/archive/ | 125+ | ~2.5M |
| archive/old_code/ | 36+ | ~450K |
| docs/archive/ | 19 | ~301K |
| **Total** | **~195+ files** | **~3.4M** |

After cleanup, the active codebase should be ~90 files of meaningful code across 4 main modules (core, adapters, api, ai) plus tests and campaigns config.
