## 2026-03-15 - [Optimize memory item list filtering]
**Learning:** Building the haystack string and doing lowercasing on every single memory/summary entry during list retrieval adds huge overhead for large datasets.
**Action:** Always defer expensive string manipulations (like concatenations and lowercasing) until after all fast boolean/property checks have been executed, and only perform them if actually needed (e.g. if a query is provided).

## 2024-05-15 - [Hoist \`utc_now\` calls out of loops]
**Learning:** Calling \`MemorySearchService._now()\` inside the list ranking loop \`_rank_working_items\` introduces huge overhead for large candidate arrays.
**Action:** Always hoist current time evaluations (like \`utc_now()\` or \`self._now()\`) outside loops to avoid significant execution overhead.
## 2026-03-24 - [Fast-path empty JSON decoding]
**Learning:** Calling `json.loads()` on empty JSON objects (like `'{}'`) introduces meaningful overhead when parsing thousands of payload entries in loops (e.g., memory recall items), scaling linearly with dataset size.
**Action:** Add an explicit fast-path check (`if not value or value == '{}': return {}`) before invoking the JSON parser to bypass the serialization overhead entirely.
