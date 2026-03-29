## 2024-03-15 - Explicit schemas over implicit dict responses
**Contract risk:** Routes returning ad-hoc dictionary structures (like `-> dict[str, str]: return {"status": "accepted"}`) lack robust schema validation, making it harder to track API contracts via OpenAPI or maintain reliable response structures for downstream clients.
**Learning:** The codebase should use explicit Pydantic response models across all endpoints, including internal management routes, to enforce predictable and typed API edges.
**Action:** Replace direct dict returns with dedicated Pydantic schemas (e.g., `ShutdownResponse`) and configure the `response_model` attribute in the FastAPI router decorators.
## 2024-03-18 - [Missing Response Model on Route Returning Varying Types]
**Contract risk:** A `DELETE` endpoint (`/memory/items/{memory_id}`) used `response_model=None` but returned either a `Response` (with 204 status code for hard deletes) or a Pydantic model (`MemoryItemRead` for soft deletes).
**Learning:** Using `response_model=None` disables validation and documentation for the route's response schema. Returning mixed types (a `Response` vs a JSON dict) requires explicit definition using `Union` types for `response_model` or defining standard response models.
**Action:** Always declare the `response_model` explicitly. If an endpoint returns no content, use `Response(status_code=204)` with an explicit route level definition or a proper response model and remove `response_model=None`.
## 2026-03-29 - Standardize Hard Delete Responses
**Contract risk:** Raw FastAPI `Response(status_code=204)` objects were returned conditionally from routes with defined Pydantic `response_model`s, violating contract typing and OpenAPI docs.
**Learning:** Returning a raw response overrides FastAPI's schema documentation and creates a split contract for API clients handling 200 OK vs 204 No Content.
**Action:** Standardize on returning explicit `MemoryDeleteResponse(deleted=True)` models with HTTP 200 for deletion confirmations instead of raw 204s.
