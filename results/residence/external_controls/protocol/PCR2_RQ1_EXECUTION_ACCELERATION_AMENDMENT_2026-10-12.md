# RQ1 external-comparator execution acceleration amendment — 2026-10-12

This amendment changes **execution only**, not the frozen scientific design.
It was introduced before any external-comparator outcome was inspected or summarized.

## Reason
The original Python implementation of `partial_assignment_upper_bound` is the dominant CPU hotspot in the exact repair replay. Running all 945 frozen executions in the current ChatGPT container would otherwise be impractical.

## Exact-equivalence acceleration
A Numba-compiled implementation evaluates the same independent upper-bound expression in the same local-index, host, and accumulation order, with `fastmath=False` (Numba default). The original checkpoint, exact-repair, controller, compatibility, invalidation, eviction, byte-budget, seed, and acceptance logic are unchanged.

Validation before accelerated confirmatory continuation:
- 150 independently generated partial-bound states: **150/150 bit-exact bound values**.
- Two development seeds (3399, 3400) × FIFO/LRU/Random full 200-decision replays: **all scientific fields exactly equal**.
- Three already-generated confirmatory executions selected by task ID only (FIFO, LRU, Random): **all scientific fields exactly equal** when rerun with the accelerator.

The only fields allowed to differ are implementation timing counters (`serialization_ms`, `restoration_ms`, `selection_ms`, `model_scoring_ms`). These timing counters are **not RQ1 external-comparator estimands and must not be analyzed from the mixed execution journal**.

The frozen 945 task IDs, five Random repetitions, random seeds, 45 cases, three capacities, exact branch-pop slice, and all scientific outputs remain unchanged.

## Exact cache-construction acceleration
The same amendment also vectorizes only the pair-gain matrix construction inside `build_destroy_repair_cache`; residual-capacity and external-gain calculations preserve the original operations. Validation before use:
- 150 caches across all three domains: **150/150 bit-exact** for `original_hosts`, `residual_capacity`, `external_gain`, and `pair_gain`.
- The same three already-generated confirmatory FIFO/LRU/Random tasks: **all scientific fields exactly equal** with both accelerators installed.
