## 2026-03-15 - [Optimize memory item list filtering]
**Learning:** Building the haystack string and doing lowercasing on every single memory/summary entry during list retrieval adds huge overhead for large datasets.
**Action:** Always defer expensive string manipulations (like concatenations and lowercasing) until after all fast boolean/property checks have been executed, and only perform them if actually needed (e.g. if a query is provided).

## 2024-05-15 - [Hoist \`utc_now\` calls out of loops]
**Learning:** Calling \`MemorySearchService._now()\` inside the list ranking loop \`_rank_working_items\` introduces huge overhead for large candidate arrays.
**Action:** Always hoist current time evaluations (like \`utc_now()\` or \`self._now()\`) outside loops to avoid significant execution overhead.

## 2026-03-27 - [Optimize list_running_subagents]
**Learning:** Fetching related items inside a loop using `self.get_session()` introduces N+1 query overhead.
**Action:** Always collect unique foreign key IDs into a set before the loop, fetch them in a single batch query (e.g. `self.get_sessions(list(session_ids))`), and map the results into a dictionary for fast local lookups.
