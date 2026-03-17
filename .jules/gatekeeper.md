## 2024-03-15 - Explicit schemas over implicit dict responses
**Contract risk:** Routes returning ad-hoc dictionary structures (like `-> dict[str, str]: return {"status": "accepted"}`) lack robust schema validation, making it harder to track API contracts via OpenAPI or maintain reliable response structures for downstream clients.
**Learning:** The codebase should use explicit Pydantic response models across all endpoints, including internal management routes, to enforce predictable and typed API edges.
**Action:** Replace direct dict returns with dedicated Pydantic schemas (e.g., `ShutdownResponse`) and configure the `response_model` attribute in the FastAPI router decorators.

## 2024-03-17 - Fix null response models on delete routes
**Contract risk:** The `delete_memory_item` endpoint returned `response_model=None` while also potentially returning soft-deleted objects or generic HTTP responses. This bypassed validation and returned an undocumented response shape to clients.
**Learning:** API boundaries must strictly define explicit types in the response model, especially when conditionally returning data or acknowledging deletion.
**Action:** Align delete routes to consistently return typed objects (like `MemoryDeleteResponse`) and remove implicit or None response models.
