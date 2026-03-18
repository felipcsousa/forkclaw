## 2026-03-15 - [Optimize memory item list filtering]
**Learning:** Building the haystack string and doing lowercasing on every single memory/summary entry during list retrieval adds huge overhead for large datasets.
**Action:** Always defer expensive string manipulations (like concatenations and lowercasing) until after all fast boolean/property checks have been executed, and only perform them if actually needed (e.g. if a query is provided).

## 2026-03-18 - Hoist current time evaluation out of loops
**Learning:** Evaluating the current time (`utc_now()`) inside a tight loop can add significant overhead in backend data processing loops like memory search candidates.
**Action:** Hoist the current time evaluations (like `utc_now()` or `self._now()`) outside the loop to avoid significant execution overhead.
