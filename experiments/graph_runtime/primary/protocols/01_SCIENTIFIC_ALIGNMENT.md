# Scientific Alignment with the Current Paper

## Current evidence that must remain

### RQ1
The graph-assignment study establishes a direct finite-memory allocation benefit for learned valuation. This is the core positive result and is not reopened.

### RQ2
The existing shallow graph setting gives very little realized new-work saving, while DeathStarBench-derived measured replay gives a larger but still modest search-work saving and unresolved objective benefit.

This is interpreted as a **value-conversion boundary**, not a failed RQ1.

### RQ3
The independent MDKP backend shows:
- persistence itself displaces repeated branch-and-bound work relative to restart;
- learned valuation does not establish superiority over the mechanism-matched empirical comparator;
- the original learned implementation does not achieve net wall-clock acceleration.

The extension is motivated by this result and must not erase it.

## Transactions extension purpose

The extension asks two tightly scoped questions inside existing RQ2/RQ3:

1. Does the existing PCR-v1 persistence architecture become computationally consequential as repeated exact-search opportunity increases?
2. Does replacing homogeneous branch-work value with deterministic computational-work value improve that conversion when node costs are heterogeneous?

No new primary research problem is introduced.

## Evidence chain

\[
\text{prediction}
\rightarrow
\text{retention}
\rightarrow
\text{compatible reuse}
\rightarrow
\text{displaced computation}
\rightarrow
\text{runtime}
\rightarrow
\text{outer objective}.
\]

The new experiments target only the middle conversion stages.
