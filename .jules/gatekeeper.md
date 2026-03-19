## 2024-03-15 - Explicit schemas over implicit dict responses
**Contract risk:** Routes returning ad-hoc dictionary structures (like `-> dict[str, str]: return {"status": "accepted"}`) lack robust schema validation, making it harder to track API contracts via OpenAPI or maintain reliable response structures for downstream clients.
**Learning:** The codebase should use explicit Pydantic response models across all endpoints, including internal management routes, to enforce predictable and typed API edges.
**Action:** Replace direct dict returns with dedicated Pydantic schemas (e.g., `ShutdownResponse`) and configure the `response_model` attribute in the FastAPI router decorators.
## 2026-03-19 - [Fix response_model in memory delete endpoint]
**Contract risk:** Missing or incorrect `response_model` when returning a union of a Pydantic model and a raw `Response`.
**Learning:** When a FastAPI route conditionally returns a raw `Response` (like a 204 No Content) and a structured Pydantic model, explicitly define the `response_model` as the Pydantic model instead of using `response_model=None`.
**Action:** Use the Pydantic model as the `response_model`. FastAPI bypasses the response validation for raw `Response`.
