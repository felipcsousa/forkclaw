## 2026-03-15 - [Optimize memory item list filtering]
**Learning:** Building the haystack string and doing lowercasing on every single memory/summary entry during list retrieval adds huge overhead for large datasets.
**Action:** Always defer expensive string manipulations (like concatenations and lowercasing) until after all fast boolean/property checks have been executed, and only perform them if actually needed (e.g. if a query is provided).

## 2024-05-15 - [Hoist \`utc_now\` calls out of loops]
**Learning:** Calling \`MemorySearchService._now()\` inside the list ranking loop \`_rank_working_items\` introduces huge overhead for large candidate arrays.
**Action:** Always hoist current time evaluations (like \`utc_now()\` or \`self._now()\`) outside loops to avoid significant execution overhead.

## 2026-03-26 - Batch ID gathering in loops vs N+1
**Learning:** In backend data processing, gathering lists of IDs from grouped datasets before batch lookups is a common pattern that tends to drift if duplicated. When N+1 bottlenecks exist when retrieving related ORM objects within a loop, using list.extend instead of a set to collect IDs leads to passing non-unique arrays to `IN (...)` queries.
**Action:** Extract dedicated helper methods (like `_batch_get_items_for_groups`) to consolidate the loop and ID gathering using sets before passing them to batch retrieval methods to shrink payload sizes and serialize less data.
