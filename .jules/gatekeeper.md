## 2024-03-15 - Explicit schemas over implicit dict responses
**Contract risk:** Routes returning ad-hoc dictionary structures (like `-> dict[str, str]: return {"status": "accepted"}`) lack robust schema validation, making it harder to track API contracts via OpenAPI or maintain reliable response structures for downstream clients.
**Learning:** The codebase should use explicit Pydantic response models across all endpoints, including internal management routes, to enforce predictable and typed API edges.
**Action:** Replace direct dict returns with dedicated Pydantic schemas (e.g., `ShutdownResponse`) and configure the `response_model` attribute in the FastAPI router decorators.
## 2024-03-18 - [Missing Response Model on Route Returning Varying Types]
**Contract risk:** A `DELETE` endpoint (`/memory/items/{memory_id}`) used `response_model=None` but returned either a `Response` (with 204 status code for hard deletes) or a Pydantic model (`MemoryItemRead` for soft deletes).
**Learning:** Using `response_model=None` disables validation and documentation for the route's response schema. Returning mixed types (a `Response` vs a JSON dict) requires explicit definition using `Union` types for `response_model` or defining standard response models.
**Action:** Always declare the `response_model` explicitly. If an endpoint returns no content, use `Response(status_code=204)` with an explicit route level definition or a proper response model and remove `response_model=None`.
## 2024-03-24 - Response Exclude None Inconsistency
**Contract risk:** Endpoints returning the exact same schema (e.g., SessionRead, MemoryItemRead) selectively apply `response_model_exclude_none=True`, causing inconsistent API payload shapes for the same domain model.
**Learning:** Different developers implement sibling endpoints without copying the response serialization arguments from the model's primary fetch endpoints, leading to null-key presence variations.
**Action:** Normalize `response_model_exclude_none=True` across sibling endpoints that return the same schema so the API boundary remains predictable.
