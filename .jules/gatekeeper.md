## 2024-03-15 - Explicit schemas over implicit dict responses
**Contract risk:** Routes returning ad-hoc dictionary structures (like `-> dict[str, str]: return {"status": "accepted"}`) lack robust schema validation, making it harder to track API contracts via OpenAPI or maintain reliable response structures for downstream clients.
**Learning:** The codebase should use explicit Pydantic response models across all endpoints, including internal management routes, to enforce predictable and typed API edges.
**Action:** Replace direct dict returns with dedicated Pydantic schemas (e.g., `ShutdownResponse`) and configure the `response_model` attribute in the FastAPI router decorators.
## 2024-03-18 - [Missing Response Model on Route Returning Varying Types]
**Contract risk:** A `DELETE` endpoint (`/memory/items/{memory_id}`) used `response_model=None` but returned either a `Response` (with 204 status code for hard deletes) or a Pydantic model (`MemoryItemRead` for soft deletes).
**Learning:** Using `response_model=None` disables validation and documentation for the route's response schema. Returning mixed types (a `Response` vs a JSON dict) requires explicit definition using `Union` types for `response_model` or defining standard response models.
**Action:** Always declare the `response_model` explicitly. If an endpoint returns no content, use `Response(status_code=204)` with an explicit route level definition or a proper response model and remove `response_model=None`.

## 2026-03-27 - [Consistent response_model_exclude_none]
**Contract risk:** Inconsistent usage of `response_model_exclude_none=True` across FastAPI endpoints that return the same or similar models (e.g., `SessionRead`, `MemoryItemRead`). This inconsistency causes some endpoints to return optional fields as `null` while others omit them completely.
**Learning:** This drift typically occurs because the parameter must be explicitly added per-route, rather than being a default property of the Pydantic model itself. As new routes are added or existing ones refactored, the parameter is often forgotten.
**Action:** Always apply `response_model_exclude_none=True` consistently across all sibling endpoints that return models with optional fields (like `SessionRead`, `MemoryItemRead`), ensuring API payloads maintain a stable and predictable shape.
