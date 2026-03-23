## 2026-03-15 - [Optimize memory item list filtering]
**Learning:** Building the haystack string and doing lowercasing on every single memory/summary entry during list retrieval adds huge overhead for large datasets.
**Action:** Always defer expensive string manipulations (like concatenations and lowercasing) until after all fast boolean/property checks have been executed, and only perform them if actually needed (e.g. if a query is provided).

## 2024-05-15 - [Hoist \`utc_now\` calls out of loops]
**Learning:** Calling \`MemorySearchService._now()\` inside the list ranking loop \`_rank_working_items\` introduces huge overhead for large candidate arrays.
**Action:** Always hoist current time evaluations (like \`utc_now()\` or \`self._now()\`) outside loops to avoid significant execution overhead.

## 2026-03-23 - [Defer Pydantic Conversions]
**Learning:** Instantiating Pydantic models (like MemoryItemRead) for every row before applying filters causes significant overhead in large datasets.
**Action:** Defer expensive Pydantic model conversions by pre-filtering raw database entities first using native object attributes. Only convert items that survive filtering.

## 2026-03-23 - [Defer Pydantic Conversions via SQL filtering in list_items]
**Learning:** Recreating Pydantic formatting logic inside Python loops to defer instantiations breaks encapsulation and violates DRY. It leads to duplicate serialization logic across the backend.
**Action:** Push domain-level filters (like `mode` and `kind`) directly into the database as SQLModel `where()` clauses. This naturally avoids fetching and instantiating large numbers of unnecessary rows, significantly boosting performance while maintaining clean, encapsulated code.
