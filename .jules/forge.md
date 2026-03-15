## 2024-03-15 - Testing build_tool_catalog sorting and properties
**Gap:** `build_tool_catalog` and `catalog_entry_from_descriptor` in `app/tools/catalog.py` had no explicit tests to verify correct attribute mapping or ordering of tools.
**Learning:** `build_tool_catalog` relies heavily on an external registry dependency. Mocking it using `unittest.mock.patch` allows us to verify alphabetical sorting and correctness independently of the tools registered in the default catalog.
**Action:** When adding or checking testing coverage for functions iterating over registry items, isolate the iteration logic using patched mock dependencies.
