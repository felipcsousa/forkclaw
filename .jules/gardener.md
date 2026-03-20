## 2024-05-24 - Extract duplicate FastAPI validation into dependency
**Smell:** The `sessions.py` route file contained identical `try/except` boilerplate across 5 endpoints to check `ensure_main_session_interaction_allowed(session_id)`.
**Learning:** This repo frequently uses manual service instantiation and validation in route functions instead of leveraging FastAPI's built-in dependency injection for path-level validation.
**Action:** Extract repeated validation logic into FastAPI dependencies (`Depends(...)`) to clean up route definitions and keep error handling central and DRY.
## 2025-02-23 - Consolidate duplicate SessionSummary save operations
**Smell:** Duplicate ORM save/commit/refresh cycles when updating `SessionSummary` entities in `MemoryService`.
**Learning:** This repo has many distinct methods for memory state changes (promote, demote, hide, etc.), which led to repetitive boilerplates updating timestamps and saving models. Extracting small helpers reduces noise.
**Action:** When updating database models across many specialized service methods, extract the common timestamp-update and `session.commit()` cycle into a private helper method (e.g., `_save_summary`).
