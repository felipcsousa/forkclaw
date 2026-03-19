## 2026-03-15 - [Optimize memory item list filtering]
**Learning:** Building the haystack string and doing lowercasing on every single memory/summary entry during list retrieval adds huge overhead for large datasets.
**Action:** Always defer expensive string manipulations (like concatenations and lowercasing) until after all fast boolean/property checks have been executed, and only perform them if actually needed (e.g. if a query is provided).

## 2024-05-23 - [Hoist current time evaluations outside data processing loops]
**Learning:** In backend data processing loops (e.g., iterating over memory search candidates), calling `utc_now()` or `self._now()` inside the loop adds significant execution overhead for large datasets.
**Action:** Always hoist current time evaluations outside the loop and pass the pre-calculated time down to functions that need it (like recency calculations).
