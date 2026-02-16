# Roadmap: Spotify-Telegram Sync

**Created:** 2026-02-15  
**Depth:** Standard (5-8 phases)

---

## Overview

A serverless Flask app that syncs the user's currently playing Spotify track to their Telegram display name. This roadmap addresses three critical issues: broken dashboard timestamps, missing "Now Playing" field removal, and insufficient logging to diagnose sync failures.

---

## Phases

### Phase 1: Dashboard & Bug Fixes

**Goal:** Fix user-facing dashboard issues and timestamp state bugs

**Dependencies:** None (this is the foundation)

**Requirements:**
- UI-01, UI-02, UI-03, BUG-01, BUG-02

**Success Criteria:**

1. **Dashboard no longer shows "Now Playing" section** — User visits dashboard and does not see any "Now Playing" field or display area
2. **"Last Sync" timestamp updates on every sync invocation** — Dashboard shows actual timestamp (not "Never") after sync cron runs, even when track hasn't changed
3. **"Last Update" timestamp updates when track changes** — Dashboard shows timestamp when track/name is actually updated, remains unchanged when no update needed
4. **Sync state correctly persists both timestamps to Redis** — last_sync updates on every run, last_update updates only on actual changes

**Plans:**
- [x] 01-01-PLAN.md — Dashboard UI (remove Now Playing, GMT+3 timestamps, syncing indicator)
- [x] 01-02-PLAN.md — Backend sync bugs (fix last_sync and last_update persistence)

---

### Phase 2: Comprehensive Logging

**Goal:** Add structured logging infrastructure to diagnose why sync stops working

**Dependencies:** Phase 1 (logging builds on working sync)

**Requirements:**
- LOG-01, LOG-02, LOG-03, LOG-04, LOG-05, LOG-06

**Success Criteria:**

1. **python-json-logger configured** — Sync function outputs JSON-formatted logs to stdout (visible in Vercel logs)
2. **Redis log handler persists last 500 entries** — Logs are retrievable from Redis for debugging after sync stops
3. **Structured logging with correlation IDs** — Each sync cycle has a correlation ID for tracing requests across logs
4. **spotify.py includes logging** — API calls, token refreshes, and errors are logged with relevant context
5. **telegram.py includes logging** — Name updates, rate limits, and errors are logged with relevant context
6. **storage.py includes logging** — Redis operations and errors are logged with relevant context

**Plans:**
- [x] 02-01-PLAN.md — Logging infrastructure (python-json-logger, correlation IDs, Redis handler)
- [x] 02-02-PLAN.md — Module logging (spotify.py, telegram.py)
- [x] 02-03-PLAN.md — Storage logging (storage.py operations)
- [ ] 02-04-PLAN.md — Sync function logging (correlation IDs, log persistence)

---

## Progress

| Phase | Goal | Status |
|-------|------|--------|
| 1 - Dashboard & Bug Fixes | Fix timestamp issues, remove unused UI | Complete |
| 2 - Comprehensive Logging | Add structured logging infrastructure | In progress |

---

## Coverage

| Requirement | Phase | Status |
|-------------|-------|--------|
| UI-01 | Phase 1 | Complete |
| UI-02 | Phase 1 | Complete |
| UI-03 | Phase 1 | Complete |
| LOG-01 | Phase 2 | Complete |
| LOG-02 | Phase 2 | Complete |
| LOG-03 | Phase 2 | Complete |
| LOG-04 | Phase 2 | Complete |
| LOG-05 | Phase 2 | Complete |
| LOG-06 | Phase 2 | Complete |
| BUG-01 | Phase 1 | Complete |
| BUG-02 | Phase 1 | Complete |

**Coverage:** 11/11 requirements mapped ✓
