## 2026-03-15 - [Optimize memory item list filtering]
**Learning:** Building the haystack string and doing lowercasing on every single memory/summary entry during list retrieval adds huge overhead for large datasets.
**Action:** Always defer expensive string manipulations (like concatenations and lowercasing) until after all fast boolean/property checks have been executed, and only perform them if actually needed (e.g. if a query is provided).

## 2024-05-23 - [Optimize memory item list retrieval]
**Learning:** Instantiating SQLModel objects into Pydantic models indiscriminately during list retrieval operations causes excessive overhead when large datasets exist.
**Action:** Defer expensive Pydantic model conversions (like `_read_entry` and `_read_summary`) by pushing filters into SQL `where()` clauses or pre-filtering raw database entities first.
