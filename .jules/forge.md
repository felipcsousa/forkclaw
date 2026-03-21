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

## 2026-03-20 - [Session Reset Contract Validation]
**Gap:** The `/sessions/{session_id}/reset` endpoint had no test coverage for error boundaries, meaning breaking changes to how `ValueError`s from `AgentOSService.reset_session_conversation` were mapped to HTTP 400s (or how `ensure_main_session` handled non-existent/subagent sessions) would go undetected.
**Learning:** In the FastAPI routing layer, exceptions raised by deep service logic (like `AgentOSService`) are often caught and translated via `value_error_as_http_exception`. Testing these translation boundaries ensures API contracts remain stable even if underlying validation messages change.
**Action:** When adding new FastAPI endpoints that perform domain validation, always include negative test cases that explicitly trigger those domain errors (e.g., via mocking or invalid state setup) to verify the correct HTTP status code is returned.

## 2026-03-17 - AgentOSService Edge Case and Domain Constraint Testing Gap
**Gap**: Missing service-level edge-case error tests for core `AgentOSService` session operations (`reset_session_conversation`, `create_session` missing agents).
**Learning**: Service tests that don't cover default bootstrapping states (e.g. what if there's no default agent) or domain constraints (only "main" sessions can be reset) leave gaps that can hide edge case failures. Relying solely on endpoint tests often skips these edge branches inside the service implementation.
**Action**: Explicitly write localized service-level tests that handle negative scenarios (such as manually unseeding default database defaults) and strictly assert on entity constraints like `session.kind` exceptions.

## 2026-03-19 - Test tool registry and web providers
**Gap:** The local utility tool registry (`app/tools/registry.py`) and provider implementations (like `BraveWebSearchProvider`) had virtually no test coverage (40-60%), leaving caching behavior, error handling, and parameter parsing vulnerable to regressions.
**Learning:** These components depend heavily on file system operations, external network requests, and system commands (like clipboard). This requires extensive use of `unittest.mock` to mock `pathlib.Path`, `subprocess.run`, and `httpx.Client` reliably without relying on the host environment.
**Action:** When testing system-level or external-facing utility tools, always utilize `patch` (for `subprocess` and `httpx`) and `MagicMock` (for `ToolExecutionContext` and `Path`) to simulate success and failure boundaries deterministically without actual side effects.
