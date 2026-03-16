## 2024-05-24 - Extract duplicate FastAPI validation into dependency
**Smell:** The `sessions.py` route file contained identical `try/except` boilerplate across 5 endpoints to check `ensure_main_session_interaction_allowed(session_id)`.
**Learning:** This repo frequently uses manual service instantiation and validation in route functions instead of leveraging FastAPI's built-in dependency injection for path-level validation.
**Action:** Extract repeated validation logic into FastAPI dependencies (`Depends(...)`) to clean up route definitions and keep error handling central and DRY.

## 2026-03-16 - Extract duplicate SessionSummary logic into private helper
**Smell:** Identical `SessionSummary` model instantiation boilerplate code was duplicated across different conditional paths in `MemoryCaptureService`.
**Learning:** Model objects with many fields frequently end up duplicated across conditional guard clauses, especially when instantiating complex structures with mostly static arguments.
**Action:** Extract large, repetitive model instantiation calls into private helper functions (like `_build_system_summary`) to reduce visual noise and the risk of drift.
