# P7 / RQ1 External Published-Policy Comparator — Pre-execution Freeze

**Freeze date:** 2026-10-12  
**Scope:** RQ1 finite-memory retention only. RQ2/RQ3 are out of scope for this extension.  
**Status at freeze:** implementation tests and development-seed smoke checks passed; no case from the frozen 45-case confirmatory set has been run with an external comparator.

## 1. Scientific purpose and claim boundary

This extension answers one narrow reviewer-facing question: how the frozen Paper-2 learned retention rule compares with direct, published bounded-cache eviction policies under the same RQ1 checkpoint stream and byte capacities.

The external baselines are **checkpoint-level adaptations** of the bounded-cache eviction strategies evaluated by Medema, Breeman, and Lazovik (2024), *Limiting the Memory Consumption of Caching for Detecting Subproblem Dominance in Constraint Problems*, *Constraints* 29, 152–191, DOI 10.1007/s10601-024-09374-7. The experiment does **not** reproduce their complete constraint-solving method and will not be described as “beating Medema et al.”

Across policies, the generated repair contexts, serialized checkpoint representation, exact repair engine, controller, acceptance variates, compatibility gate, accepted-move invalidation/revalidation, restoration semantics, case seeds, and exact byte budgets remain those of the frozen P7 RQ1 experiment. Only the finite-memory resident-set/eviction rule changes.

## 2. Frozen external policies

### FIFO

- A checkpoint's queue age is its original admission/creation iteration (`created_iteration`).
- A hit/recurrence does **not** refresh FIFO position.
- When space is needed, evict the resident checkpoint with the oldest creation iteration; ties use the checkpoint key for deterministic ordering.
- Repeat eviction until the incoming checkpoint fits the exact byte capacity.

### LRU

- Recency is the most recent repair-context occurrence/access available online at the decision step.
- In the P7 representation, the accessed/current checkpoint is reserialized with `last_scored_iteration = current iteration`; this timestamp is used solely as the access-recency field for the LRU adaptation.
- A newly admitted checkpoint is most recently used; a recurring/hit checkpoint becomes most recently used.
- Evict the resident checkpoint with the smallest last-access iteration; ties are broken by creation iteration and then checkpoint key.
- Repeat eviction until the incoming checkpoint fits.

### Random Replacement

- Each eviction victim is sampled uniformly from the **currently resident** checkpoints.
- Victims are removed sequentially, so multiple evictions are without replacement within one admission event.
- The incoming checkpoint is not an eviction victim.
- Five independent fixed Random-Replacement repetitions are run for each case × budget cell. Repetitions are averaged within the base case before cross-case estimation, so random repetitions are not treated as independent inferential units.

Frozen Random-Replacement seed formula, for repetition `rep` in 1..5:

`10,000,000*rep + 1,000,000*domain_code + 100*instance_seed + budget_code`

where `domain_code = {generic:1, workflow:2, microservice:3}` and `budget_code = {25%:25, 50%:50, 75%:75}`.

## 3. Admission and variable-size checkpoint adaptation

Medema et al.'s bounded cache evicts existing entries to make room for a newly added entry. The Paper-2 checkpoints have heterogeneous serialized byte sizes. Therefore:

1. remove the stale serialized version of the same checkpoint key on a recurrence/hit;
2. apply FIFO/LRU/Random only to the remaining resident set;
3. repeatedly evict existing residents until `resident_bytes + incoming_bytes <= M`;
4. admit the incoming checkpoint;
5. never treat that incoming checkpoint as an eviction candidate during its own admission.

The authoritative P7 capacity construction already guarantees `M >= max(single checkpoint size)` for each case, so an individual confirmatory checkpoint is admissible.

If an accepted placement change causes re-serialization of an already resident checkpoint and the changed byte size alone pushes the resident set over `M`, the same frozen policy order is applied to the current resident set until the exact cap is restored. Compatibility checks and invalidation rules are unchanged.

## 4. Frozen confirmatory design

- Domains/families: `generic`, `workflow`, `microservice`.
- Independent base cases: 45 total, 15 per family.
- Case seeds in each family: 3301–3315.
- Repair decisions per case: 200.
- Destroy size: 12.
- Exact-repair slice: 8 branch pops per decision.
- Memory capacities: 25%, 50%, 75% of the case-specific keep-all peak, using the already-authoritative `p7_confirmatory_budgets.csv` byte values unchanged.
- Primary constrained-memory regime: 25%.
- 50% and 75% are sensitivity regimes.
- Existing restart, empirical-compatible, learned, and keep-all outcomes are **not rerun**; the authoritative P7 result files are reused unchanged after their values were verified against the 2026-10-12 manuscript.
- External runs: FIFO once, LRU once, Random Replacement 5 times for every case × budget cell.
- Expected raw external executions: `45 × 3 × (1 + 1 + 5) = 945`.
- Expected external case-level rows after averaging Random repetitions: `45 × 3 × 3 = 405`.

## 5. Frozen outcomes and inference

Primary external outcome:

- keep-all-normalized reusable branch work, `reused_prior_branch_pops / keep_all_reused_prior_branch_pops`, evaluated at 25% capacity.

Additional already-defined RQ1 outcomes:

- gross reusable branch pops;
- compatible/useful resumes;
- capacity and invalidation evictions;
- peak and byte-time memory accounting;
- branch pops executed and objective-response contrasts versus restart where already defined by P7.

Inference:

- independent unit = base case;
- Random-Replacement repetitions are averaged within base case first;
- 10,000-replicate case bootstrap for means and 95% percentile intervals;
- paired case-bootstrap intervals for learned-minus-external-policy differences;
- no new null-hypothesis p-values are introduced;
- report positive/negative/tied paired-case counts descriptively.

The main comparison at 25% is learned valuation versus FIFO, LRU, and Random Replacement. The existing empirical-compatible and keep-all policies remain the internal comparator and upper-reference context, respectively.

## 6. Pre-execution gates completed

1. External-policy unit tests: 5/5 passed.
2. External + original online-retention regression suite: 9/9 passed after restoring the frozen P6 model from the same reproducibility archive.
3. Development-only smoke check: `workflow`, seed 2424, 200 decisions, destroy size 12, 8 pops, 25% capacity.
4. Smoke result: FIFO, LRU, and Random all respected `peak_bytes <= M`; all used exact-byte repeated eviction and `not_retained = 0`.
5. No 3301–3315 external-comparator outcome was inspected before this freeze.

## 7. Frozen implementation files

- `04_Source_Code_and_Tests/certified_assignment/paper2_external_eviction.py`
- `04_Source_Code_and_Tests/scripts/paper2_p7_external_comparators.py`
- `04_Source_Code_and_Tests/tests/test_external_eviction.py`

Unmodified P7 dependencies used for the experiment include:

- `04_Source_Code_and_Tests/certified_assignment/paper2_online_pilot.py`
- authoritative P7 budget/run/matched tables under `02_Authoritative_Experimental_Evidence/06_P7_Confirmatory_Retention/results/`.

The SHA-256 manifest written beside this protocol fixes the exact implementation and authoritative inputs used at execution.
