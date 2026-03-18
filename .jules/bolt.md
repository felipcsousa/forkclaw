## 2026-03-15 - [Optimize memory item list filtering]
**Learning:** Building the haystack string and doing lowercasing on every single memory/summary entry during list retrieval adds huge overhead for large datasets.
**Action:** Always defer expensive string manipulations (like concatenations and lowercasing) until after all fast boolean/property checks have been executed, and only perform them if actually needed (e.g. if a query is provided).

## 2025-02-18 - [Hoist time evaluation out of loops]
**Learning:** Re-evaluating current time (like `utc_now()`) inside data processing loops (e.g., when scoring hundreds of memory search candidates) adds overhead due to function calls and object creation.
**Action:** Always hoist time evaluations (like `utc_now()` or `self._now()`) outside the loop and pass the static value into the loop body to avoid significant execution overhead.
