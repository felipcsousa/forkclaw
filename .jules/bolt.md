## 2026-03-15 - [Optimize memory item list filtering]
**Learning:** Building the haystack string and doing lowercasing on every single memory/summary entry during list retrieval adds huge overhead for large datasets.
**Action:** Always defer expensive string manipulations (like concatenations and lowercasing) until after all fast boolean/property checks have been executed, and only perform them if actually needed (e.g. if a query is provided).

## 2024-05-15 - [Hoist \`utc_now\` calls out of loops]
**Learning:** Calling \`MemorySearchService._now()\` inside the list ranking loop \`_rank_working_items\` introduces huge overhead for large candidate arrays.
**Action:** Always hoist current time evaluations (like \`utc_now()\` or \`self._now()\`) outside loops to avoid significant execution overhead.

## 2025-03-22 - [Defer Pydantic model instantiations in list filtering]
**Learning:** Instantiating expensive Pydantic models (like `MemoryItemRead`) before filtering out unwanted items creates a significant CPU and memory bottleneck, especially for large datasets where the majority of items are discarded by application-level filters.
**Action:** Pre-filter raw database entities directly using native object attributes and helper methods. Only convert the entities that survive the fast boolean/property checks into the final response models.
