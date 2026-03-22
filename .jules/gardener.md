## 2024-05-24 - Extract duplicate FastAPI validation into dependency
**Smell:** The `sessions.py` route file contained identical `try/except` boilerplate across 5 endpoints to check `ensure_main_session_interaction_allowed(session_id)`.
**Learning:** This repo frequently uses manual service instantiation and validation in route functions instead of leveraging FastAPI's built-in dependency injection for path-level validation.
**Action:** Extract repeated validation logic into FastAPI dependencies (`Depends(...)`) to clean up route definitions and keep error handling central and DRY.

## 2025-02-23 - Consolidate duplicate SessionSummary save operations
**Smell:** Duplicate ORM save/commit/refresh cycles when updating `SessionSummary` entities in `MemoryService`.
**Learning:** This repo has many distinct methods for memory state changes (promote, demote, hide, etc.), which led to repetitive boilerplates updating timestamps and saving models. Extracting small helpers reduces noise.
**Action:** When updating database models across many specialized service methods, extract the common timestamp-update and `session.commit()` cycle into a private helper method (e.g., `_save_summary`).

## 2024-03-17 - Extract duplicated audit logging in memory admin service
**Smell:** Eight identical, multi-line `self.repository.add_change_log(...)` calls duplicated across all CRUD actions, cluttering the domain logic with infrastructure boilerplate.
**Learning:** In services where every mutating operation must be audited, repeating the full audit payload (actor_type, actor_id, etc.) makes the code verbose and increases the risk of drift.
**Action:** Extract a private helper (e.g., `_log_change`) within the service to encapsulate the repetitive audit arguments, keeping the domain methods focused on their primary intent.

## 2024-05-24 - Extract duplicated SessionSummary instantiations
**Smell:** Large Pydantic/SQLModel instantiations (`SessionSummary`) with ~18 arguments were duplicated verbatim across conditional guard clauses in `MemoryCaptureService.capture_execution_result`.
**Learning:** This repo tends to copy-paste large model instantiations across branches which increases visual noise and the risk of drift if the model schema changes.
**Action:** Extract large, repeated model instantiations into private helper functions (like `_build_session_summary`) to reduce duplication and keep complex route/service methods clean.
## 2025-02-18 - Extract duplicated batch item fetching logic in memory service
**Smell:** Duplicated loops gathering record IDs from grouped recall rows to perform batch fetching in `recall_for_session` and `recall_log`.
**Learning:** In backend data processing, gathering lists of IDs from grouped datasets before batch lookups is a common pattern that tends to drift if duplicated.
**Action:** Extract a dedicated helper method `_batch_get_items_for_groups` to consolidate the loop and ID gathering before passing to `_batch_get_items`.
