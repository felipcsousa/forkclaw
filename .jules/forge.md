## 2026-03-15 - Missing tests for get_activity_timeline endpoint
**Gap:** The `/activity/timeline` endpoint lacked test coverage, specifically regarding pagination (limit and cursor) and error handling.
**Learning:** FastAPI's `response_model_exclude_none=True` omits `None` fields entirely from the returned JSON, meaning assertions must check for absence of keys rather than `is None`. Furthermore, when testing with a persistent SQLite database (or one that isn't fully reset per test), tests requiring a clean slate must explicitly wipe seeded data using raw `DELETE FROM` statements.
**Action:** Always check `response_model_exclude_none` when asserting against `None` fields in FastAPI JSON responses. Always clear necessary tables explicitly in test setup if `conftest.py` is actively seeding data for the session.
## 2024-03-15 - Missing tests for configure_logging
**Gap:** The function `configure_logging()` in `apps/backend/app/core/logging.py` lacked test coverage, specifically regarding exception formatting, JSON defaults, interaction with `Settings.ensure_data_dir()`, and its behavior on multiple consecutive calls.
**Learning:** `pytest-cov` is a valuable tool for accurately measuring test coverage and identifying missed branches. Additionally, mocking internal methods on pydantic models or configuration objects directly (e.g., `Settings.ensure_data_dir`) using `monkeypatch.setattr` ensures tests can intercept and monitor executions without triggering actual I/O side effects, although care must be taken to retain the original implementation.
**Action:** When filling coverage gaps, always attempt to execute the target function in an isolated state using fixtures like `tmp_path` and `monkeypatch`. Ensure logging handlers are cleared out before and after the test to prevent polluting the test environment, and ensure custom formatters are explicitly validated.
## 2024-03-15 - Testing build_tool_catalog sorting and properties
**Gap:** `build_tool_catalog` and `catalog_entry_from_descriptor` in `app/tools/catalog.py` had no explicit tests to verify correct attribute mapping or ordering of tools.
**Learning:** `build_tool_catalog` relies heavily on an external registry dependency. Mocking it using `unittest.mock.patch` allows us to verify alphabetical sorting and correctness independently of the tools registered in the default catalog.
**Action:** When adding or checking testing coverage for functions iterating over registry items, isolate the iteration logic using patched mock dependencies.
## 2024-03-16 - Testing Memory Importance via Admin Endpoints
**Gap:** The memory item `/promote` and `/demote` endpoints lacked integration test coverage to assert the underlying semantic shifts from "stable" to "episodic" scopes mapping to importance levels.
**Learning:** For memory entries, promoting an item functionally switches its `scope_type` mapping underneath, which is returned through `MemoryItemRead.kind`. In testing, adjusting "importance" metrics using `promote/demote` requires verifying `kind` instead of numerical or textual `importance` properties directly, because memory administration handles these state transitions via "stable" vs "episodic" scope types.
**Action:** When writing tests that manipulate semantic properties (like promoting/demoting memory or changing scopes), verify the domain-specific enumerated mappings (like `kind="stable"`) on the updated response model, not just the raw integer or label property.



## 2026-03-22 - Testing Subagent Delegation State Getters and Updaters
**Gap:** The helper methods `aggregate_counts_for_sessions`, `ensure_main_session_interaction_allowed`, `get_main_session`, and `_mark_run_as_acp_mapped` in `app/services/subagents.py` lacked test coverage, which could lead to regressions in state management or session isolation.
**Learning:** Small, pure getters and single-action state updaters are often skipped in initial PRs because they are 'too simple to fail', but they represent critical boundaries (like ensuring only main sessions can be interacted with).
**Action:** When adding state-transitioning methods or validation guards for sessions, always add a basic unit test to lock the expected behavior against accidental regression.
