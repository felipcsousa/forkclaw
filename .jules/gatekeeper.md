## 2024-03-15 - Explicit schemas over implicit dict responses
**Contract risk:** Routes returning ad-hoc dictionary structures (like `-> dict[str, str]: return {"status": "accepted"}`) lack robust schema validation, making it harder to track API contracts via OpenAPI or maintain reliable response structures for downstream clients.
**Learning:** The codebase should use explicit Pydantic response models across all endpoints, including internal management routes, to enforce predictable and typed API edges.
**Action:** Replace direct dict returns with dedicated Pydantic schemas (e.g., `ShutdownResponse`) and configure the `response_model` attribute in the FastAPI router decorators.

## 2024-03-20 - Explicit response_model for conditional raw responses
**Contract risk:** Using `response_model=None` for endpoints that conditionally return a raw `Response` (like a 204 No Content) and a structured Pydantic model bypasses response validation and creates an inaccurate OpenAPI documentation for successful data payloads.
**Learning:** FastAPI safely bypasses the response validation when a raw `Response` is returned, keeping the OpenAPI documentation accurate for successful data payloads.
**Action:** When a FastAPI route conditionally returns a raw `Response` and a structured Pydantic model, explicitly define the `response_model` as the Pydantic model instead of using `response_model=None`.
