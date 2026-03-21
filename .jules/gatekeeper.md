## 2024-03-15 - Explicit schemas over implicit dict responses
**Contract risk:** Routes returning ad-hoc dictionary structures (like `-> dict[str, str]: return {"status": "accepted"}`) lack robust schema validation, making it harder to track API contracts via OpenAPI or maintain reliable response structures for downstream clients.
**Learning:** The codebase should use explicit Pydantic response models across all endpoints, including internal management routes, to enforce predictable and typed API edges.
**Action:** Replace direct dict returns with dedicated Pydantic schemas (e.g., `ShutdownResponse`) and configure the `response_model` attribute in the FastAPI router decorators.

## 2024-03-21 - Explicit response models for conditional Response objects
**Contract risk:** Using `response_model=None` on routes that conditionally return a raw `Response` (like a 204 No Content) alongside a structured Pydantic model obscures the structured payload schema in OpenAPI documentation.
**Learning:** FastAPI gracefully ignores the `response_model` when returning a raw `Response`.
**Action:** Always set the `response_model` to the expected Pydantic schema, even if the endpoint occasionally returns a raw `Response`.
