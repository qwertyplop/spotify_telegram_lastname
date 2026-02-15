# Requirements: Spotify-Telegram Sync

**Defined:** 2026-02-15
**Core Value:** Automatically update Telegram last name to show current Spotify track

## v1 Requirements

### Dashboard UI

- [ ] **UI-01**: Remove "Now Playing" section from dashboard
- [ ] **UI-02**: Fix "Last Sync" timestamp - update on every sync invocation (not just when track changes)
- [ ] **UI-03**: Fix "Last Update" timestamp - update when track/name actually changes

### Logging

- [ ] **LOG-01**: Add python-json-logger for structured JSON logging
- [ ] **LOG-02**: Add Redis log handler to persist logs to Upstash (last 500 entries)
- [ ] **LOG-03**: Add structured logging to sync function with correlation IDs
- [ ] **LOG-04**: Add logging to spotify.py (API calls, errors)
- [ ] **LOG-05**: Add logging to telegram.py (updates, rate limits, errors)
- [ ] **LOG-06**: Add logging to storage.py (Redis operations, errors)

### Bug Fixes

- [ ] **BUG-01**: Fix sync state not saving last_sync timestamp when no update needed
- [ ] **BUG-02**: Fix sync state not saving last_update timestamp correctly

## v2 Requirements

(None currently - bug fixes only)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time push notifications | Not needed |
| Multiple Telegram accounts | Single user only |
| Webhook-based sync | Polling is sufficient |
| Vercel Log Drain | Requires Pro plan, Redis persistence is free alternative |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| UI-01 | Phase 1 | Pending |
| UI-02 | Phase 1 | Pending |
| UI-03 | Phase 1 | Pending |
| LOG-01 | Phase 2 | Pending |
| LOG-02 | Phase 2 | Pending |
| LOG-03 | Phase 2 | Pending |
| LOG-04 | Phase 2 | Pending |
| LOG-05 | Phase 2 | Pending |
| LOG-06 | Phase 2 | Pending |
| BUG-01 | Phase 1 | Pending |
| BUG-02 | Phase 1 | Pending |

**Coverage:**
- v1 requirements: 11 total
- Mapped to phases: 11
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-15*
*Last updated: 2026-02-15 after roadmap creation*
