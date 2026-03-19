## 2026-03-15 - [Optimize memory item list filtering]
**Learning:** Building the haystack string and doing lowercasing on every single memory/summary entry during list retrieval adds huge overhead for large datasets.
**Action:** Always defer expensive string manipulations (like concatenations and lowercasing) until after all fast boolean/property checks have been executed, and only perform them if actually needed (e.g. if a query is provided).

## 2023-11-09 - [Hoist current time evaluation in memory search loop]
**Learning:** Repeatedly evaluating `datetime.now(UTC)` inside a loop iterating over large datasets adds significant overhead.
**Action:** Hoist the time evaluation outside the loop to be reused across iterations when processing many items, ensuring both a performance boost and temporal consistency.
