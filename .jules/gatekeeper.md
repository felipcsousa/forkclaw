## 2024-03-15 - Explicit schemas over implicit dict responses
**Contract risk:** Routes returning ad-hoc dictionary structures (like `-> dict[str, str]: return {"status": "accepted"}`) lack robust schema validation, making it harder to track API contracts via OpenAPI or maintain reliable response structures for downstream clients.
**Learning:** The codebase should use explicit Pydantic response models across all endpoints, including internal management routes, to enforce predictable and typed API edges.
**Action:** Replace direct dict returns with dedicated Pydantic schemas (e.g., `ShutdownResponse`) and configure the `response_model` attribute in the FastAPI router decorators.
## 2024-03-18 - [Missing Response Model on Route Returning Varying Types]
**Contract risk:** A `DELETE` endpoint (`/memory/items/{memory_id}`) used `response_model=None` but returned either a `Response` (with 204 status code for hard deletes) or a Pydantic model (`MemoryItemRead` for soft deletes).
**Learning:** Using `response_model=None` disables validation and documentation for the route's response schema. Returning mixed types (a `Response` vs a JSON dict) requires explicit definition using `Union` types for `response_model` or defining standard response models.
**Action:** Always declare the `response_model` explicitly. If an endpoint returns no content, use `Response(status_code=204)` with an explicit route level definition or a proper response model and remove `response_model=None`.
## 2024-05-23 - Consistency for response_model_exclude_none
**Contract risk:** Inconsistent usage of response_model_exclude_none=True across endpoints returning the same Pydantic schema (e.g., MemoryItemRead, SessionRead) can lead to mismatched response shapes. Some endpoints expose None fields while others exclude them.
**Learning:** It's easy to forget to add response_model_exclude_none=True when creating new sibling endpoints or refactoring existing ones, causing a drift in the API contract.
**Action:** Always verify sibling endpoints returning the same Pydantic schema and consistently apply response_model_exclude_none=True to all of them to prevent unpredictable API payloads.
