## 2024-05-24 - Extract duplicate FastAPI validation into dependency
**Smell:** The `sessions.py` route file contained identical `try/except` boilerplate across 5 endpoints to check `ensure_main_session_interaction_allowed(session_id)`.
**Learning:** This repo frequently uses manual service instantiation and validation in route functions instead of leveraging FastAPI's built-in dependency injection for path-level validation.
**Action:** Extract repeated validation logic into FastAPI dependencies (`Depends(...)`) to clean up route definitions and keep error handling central and DRY.
