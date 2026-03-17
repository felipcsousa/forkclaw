## 2026-03-15 - [Optimize memory item list filtering]
**Learning:** Building the haystack string and doing lowercasing on every single memory/summary entry during list retrieval adds huge overhead for large datasets.
**Action:** Always defer expensive string manipulations (like concatenations and lowercasing) until after all fast boolean/property checks have been executed, and only perform them if actually needed (e.g. if a query is provided).

## 2024-03-24 - [Hoist time calls from loops]
**Learning:** Re-evaluating `utc_now()` via `self._now()` and instantiating `timedelta` objects inside a loop over memory candidates introduces significant execution overhead.
**Action:** Always hoist current time evaluations outside of loops to compute them exactly once per request, unless precise individual item timing is strictly required.
