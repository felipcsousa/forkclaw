## 2026-03-15 - [Optimize memory item list filtering]
**Learning:** Building the haystack string and doing lowercasing on every single memory/summary entry during list retrieval adds huge overhead for large datasets.
**Action:** Always defer expensive string manipulations (like concatenations and lowercasing) until after all fast boolean/property checks have been executed, and only perform them if actually needed (e.g. if a query is provided).

## 2024-05-15 - [Hoist \`utc_now\` calls out of loops]
**Learning:** Calling \`MemorySearchService._now()\` inside the list ranking loop \`_rank_working_items\` introduces huge overhead for large candidate arrays.
**Action:** Always hoist current time evaluations (like \`utc_now()\` or \`self._now()\`) outside loops to avoid significant execution overhead.

## 2026-03-21 - Hoist Time Evaluations Outside Loops
**Learning:** In backend data processing loops (e.g., iterating over memory search candidates), evaluating current time (like `utc_now()` or `self._now()`) inside the loop introduces significant execution overhead.
**Action:** Always hoist current time evaluations outside the loop and pass the pre-calculated time as an argument to helper methods.
