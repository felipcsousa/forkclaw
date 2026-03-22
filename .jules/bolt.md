## 2026-03-15 - [Optimize memory item list filtering]
**Learning:** Building the haystack string and doing lowercasing on every single memory/summary entry during list retrieval adds huge overhead for large datasets.
**Action:** Always defer expensive string manipulations (like concatenations and lowercasing) until after all fast boolean/property checks have been executed, and only perform them if actually needed (e.g. if a query is provided).

## 2024-05-15 - [Hoist \`utc_now\` calls out of loops]
**Learning:** Calling \`MemorySearchService._now()\` inside the list ranking loop \`_rank_working_items\` introduces huge overhead for large candidate arrays.
**Action:** Always hoist current time evaluations (like \`utc_now()\` or \`self._now()\`) outside loops to avoid significant execution overhead.

## 2024-05-15 - [Defer Pydantic model conversion]
**Learning:** Instantiating large Pydantic response models (like `MemoryItemRead`) across an entire list of entries *before* filtering them introduces immense overhead due to unnecessary validation and data transformation for items that will simply be discarded.
**Action:** Always defer expensive Pydantic model conversions (e.g., `_read_entry` and `_read_summary`) by pre-filtering raw database entities first using basic native object attributes. Only convert items that survive the filtering.
