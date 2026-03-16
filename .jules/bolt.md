## 2026-03-15 - [Optimize memory item list filtering]
**Learning:** Building the haystack string and doing lowercasing on every single memory/summary entry during list retrieval adds huge overhead for large datasets.
**Action:** Always defer expensive string manipulations (like concatenations and lowercasing) until after all fast boolean/property checks have been executed, and only perform them if actually needed (e.g. if a query is provided).

## 2024-03-16 - [Performance Optimization] Hoist current time evaluation out of loop
**Learning:** In backend data processing loops (e.g., iterating over memory search candidates in `_rank_working_items`), calling a function that determines the current time (like `utc_now()` or `self._now()`) inside the loop introduces significant execution overhead. Benchmarks showed that evaluating the time once and passing it drops execution time from 0.252s to 0.079s for 100k items.
**Action:** When performing operations on collections, always evaluate the current time outside the loop and pass it as an argument or variable to inner functions, avoiding repeated instantiation.
