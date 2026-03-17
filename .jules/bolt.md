## 2026-03-15 - [Optimize memory item list filtering]
**Learning:** Building the haystack string and doing lowercasing on every single memory/summary entry during list retrieval adds huge overhead for large datasets.
**Action:** Always defer expensive string manipulations (like concatenations and lowercasing) until after all fast boolean/property checks have been executed, and only perform them if actually needed (e.g. if a query is provided).

## 2026-03-17 - [Optimize memory list items early filtering]
**Learning:** In backend data processing, doing Pydantic validation (e.g. `_read_entry`) on database rows that will subsequently be filtered out wastes significant CPU and memory. Furthermore, string operations (like `lower()` and `" ".join()`) applied iteratively add severe overhead for large sets.
**Action:** Defer Pydantic parsing and heavy string manipulation. Push fast property checks and boolean conditions up against the raw ORM entities, only converting objects when they pass the early filters.
