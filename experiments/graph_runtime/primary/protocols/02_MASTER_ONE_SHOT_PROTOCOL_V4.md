# PCR Transactions — Audited 3-VM One-Shot Master Protocol V4

**Status:** pre-implementation/pre-confirmation freeze candidate  
**Supersedes:** V1, V2 and V3 protocol packages for future execution decisions.  
**Historical evidence:** unchanged.

---

## 1. Immutable baseline

PCR-v1:

\[
v^W_{i,t}=\hat p^{UA}_{i,t}W_{i,t}.
\]

Frozen:
- problem formulations;
- exact-search semantics;
- graph recurrence horizon \(H=40\);
- graph and MDKP frozen recurrence models;
- empirical-compatible probability rule;
- exact byte-constrained allocator;
- exact compatibility gate;
- original scientific checkpoint blob and byte accounting;
- all prior RQ1/RQ2/RQ3 evidence.

Prediction controls residence only. Exact compatibility alone authorizes execution.

---

## 2. Research questions remain unchanged

### RQ1
Can future legally compatible recurrence be predicted from retention-time information well enough to improve finite-memory allocation?

No new RQ1 confirmation.

### RQ2
Under what recurrence and search-cost conditions does improved retention convert into less repeated exact-search work and downstream computational benefit?

The existing measured-replay regimes already vary recurrence pattern. V4 adds the missing **search-opportunity** axis.

### RQ3
Which components of predictive persistence transfer when the combinatorial problem and exact-search backend change?

V4 uses a new untouched MDKP block.

---

## 3. Minimal compute-aware refinement

\[
v^C_{i,t}=\hat p^{UA}_{i,t}C_{i,t},
\]

where

\[
C_{i,t}=\sum_k\tilde\omega_k N_{ik,t}.
\]

Only \(W_i\rightarrow C_i\) changes.

No:
- second recurrence model;
- admissibility-survival model;
- neural value model;
- adaptive enable/disable gate;
- multi-period stochastic control;
- generic cache-value novelty claim.

### Fixed operation counters

Per exact-search checkpoint sidecar:
1. expanded nodes;
2. bound evaluations;
3. generated children;
4. feasibility checks;
5. incumbent evaluations;
6. frontier insertions.

Counters are integer, retention-time observable, branch-safe, monotone across legal resume, and never serialized into the scientific solver-state blob.

### Deterministic weights

Development calibration initially estimates nonnegative CPU-ns-per-operation weights.

Before policy use, each coefficient is rounded to a nonnegative integer number of nanoseconds per operation:

\[
\tilde\omega_k=\max(0,\operatorname{round}(\omega_k)).
\]

All validation is repeated with the quantized coefficients. Policy \(C_i\) is therefore an integer deterministic compute unit.

A global positive scale factor is irrelevant to the knapsack ranking and is never machine-tuned during confirmation.

---

## 4. Calibration and validation

### Calibration machine
Fit graph and MDKP cost weights using exposed development data on **PRIMARY_A only**, chosen by the deterministic hardware-role rule rather than performance.

### Within-machine grouped CV gate on PRIMARY_A
Grouped five-fold CV by independent case, with the six fixed counters.

Required after coefficient integerization:

1. Spearman predicted-compute vs exact-search process CPU:
   \[
   \rho \ge 0.70;
   \]
2. normalized median absolute error:
   \[
   \frac{\operatorname{median}|aC-T_{\rm CPU}|}
        {\operatorname{median}(T_{\rm CPU})}\le0.35,
   \]
   where \(a>0\) is one development-only scalar fitted for error reporting. The policy does not use \(a\).

### Cross-machine validation gate on PRIMARY_B
Use the **same frozen integer weights**; no refit.

Required:
1. Spearman \(C\) vs exact-search CPU \(\rho\ge0.70\);
2. scale-adjusted normalized median absolute error \(\le0.35\).

The scale adjustment is validation-only and cannot alter checkpoint ranking.

### Continuation-value sanity gate
On matched compatible restart/resume development checks on each primary:

\[
\rho(C_i,\;T^{CPU}_{restart}-T^{CPU}_{resume})\ge0.60.
\]

If any backend fails, no untouched pC confirmation for that backend begins.

There is no gate requiring pC to outperform pW or even choose different states.

---

## 5. Scientific checkpoint bytes

Instrumentation/value sidecars must not alter the historical solver-state blob.

For the same checkpoint:
- blob SHA-256 unchanged;
- `scientific_bytes = len(original_blob)` unchanged;
- byte budget uses `scientific_bytes` only.

Controller metadata are outside the scientific continuation object for every policy.

---

## 6. Common implementation optimization

Allowed only before untouched cases and only under exact semantic equivalence.

Examples:
- exact export of frozen model arithmetic;
- preallocated feature buffers;
- caching invariant transforms;
- avoiding redundant copies;
- metadata-first incompatibility rejection;
- mathematically identical allocator workspace reuse.

Required PCR-v1 equivalence on exposed data:
- prediction difference \(\le10^{-12}\);
- same selected checkpoint IDs at every decision;
- same compatibility result;
- same branch trajectory hash;
- same returned repair;
- same objective trajectory;
- same scientific checkpoint bytes.

Any optimization that fails is disabled.

### pC cross-machine determinism gate
After weights freeze, replay at least 10 exposed graph cases and 10 exposed MDKP cases on both primaries.

Ignoring timing fields, require:
- identical pC resident sets;
- identical compatibility outcomes;
- identical branch/objective trajectory hashes.

Failure blocks untouched confirmation.

---

## 7. Three-VM architecture

Hardware roles are assigned only after live inventory.

Expected:
- 2 × 4-vCPU / ~16-GiB = PRIMARY_A / PRIMARY_B;
- 1 × 2-vCPU / ~8-GiB = CONTROL_SECONDARY.

PRIMARY_A/B are assigned lexically by host alias among the two 4-vCPU machines; performance never determines role.

### Azure timing-class gate
Capture VM size from Azure Instance Metadata Service when available.

If either primary is B-series/burstable, primary runtime confirmation is NO-GO until resized to a non-burstable class or a new frozen timing plan is approved before case generation.

### Execution rule
Parallel **between** PRIMARY_A and PRIMARY_B.

Sequential **within** each primary:
- one timed PCR process;
- no concurrent case timing on spare vCPUs.

All policies/repeats/opportunity levels for one case stay on the same primary machine.

---

## 8. Environment

Preferred prospective runtime:
- Python **3.12.15**, matching the authoritative original PCR campaign;
- exact package versions in `config/requirements_pcr_tx.txt`.

If 3.12.15 cannot be installed on all three machines, choose one exact Python 3.12.x patch common to all machines **before development gates**, record it as a new prospective runtime, and do not describe it as the historical captured runtime.

Absolute new runtimes are not pooled with historical timings.

All machines use:
- same Python patch;
- same package lock;
- same source hash;
- same model hashes;
- same integer compute weights.

Thread caps:
- OMP=1
- MKL=1
- OPENBLAS=1
- NUMEXPR=1
- PYTHONHASHSEED=0

---

## 9. Background isolation and execution epoch

Before primary timing, quiesce experiment-related/background services on **all three nodes**:
- k3s / k3s-agent;
- Docker socket/daemon;
- standalone containerd if active;
- Zeek if active;
- unattended-upgrades and apt daily timers if active.

Do not stop SSH/networking.

After Azure startup, wait at least 300 s and pass strict idle/preflight checks.

Once a primary shard begins, do not intentionally deallocate/reboot that primary until its shard completes.

Record:
- Linux boot ID;
- Azure VM size;
- CPU model;
- kernel;
- clocksource;
- Python/package lock.

If an unavoidable reboot occurs:
- all completed case blocks remain historical valid runs;
- the interrupted case block is a technical failure and is rerun in full;
- a new execution epoch is recorded;
- no aggregate effect is viewed.

---

## 10. Development firewall

All previously inspected graph/DeathStarBench/MDKP cases and timing diagnostics are development-only for pC.

They may be used for:
- instrumentation;
- calibration;
- equivalence;
- opportunity-level selection;
- precision planning;
- debugging.

They may not become untouched evidence for pC.

---

## 11. New graph RQ2 sample

60 new independent base cases:
- 20 Generic;
- 20 Workflow;
- 20 Microservice.

Use distinct new seeds per case (no reuse of one seed across families).

Fixed:
- 24 nodes;
- 6 hosts;
- destroy size 12;
- 200 controller decisions;
- horizon 40;
- frozen graph recurrence predictor;
- same deterministic replay construction across policies within case/level.

### Search-opportunity candidates

\[
B\in\{8,16,32,64,128,256,384\}.
\]

- L1 = 8.
- Using **restart-only exposed development cases**, calculate fraction of repair calls unfinished at each candidate.
- L2 = unused candidate nearest 75% unfinished.
- L3 = larger unused candidate nearest 50% unfinished.
- L4 = larger unused candidate nearest 25% unfinished.
- Ties choose the smaller eligible candidate.
- If target-nearest would duplicate/not exceed the previous level, take the nearest larger unused candidate.
- No pW/pC/learned/empirical runtime or objective outcome enters level selection.

### Capacity characterization

For each new case \(c\) and level \(\ell\), before any compared-policy timing:
1. run an untimed keep-all characterization;
2. record peak scientific checkpoint bytes \(P_{c,\ell}\);
3. record largest scientific checkpoint \(m^{max}_{c,\ell}\);
4. freeze:
   \[
   M_{c,\ell}=
   \max\left(
   m^{max}_{c,\ell},
   \operatorname{round}(0.25P_{c,\ell})
   \right).
   \]

This preserves the original P7 capacity-normalization principle and guarantees at least one checkpoint can fit.

Capacity characterization is completed for the full graph sample as a separate phase before primary timing.

---

## 12. New MDKP RQ3 sample

80 new untouched cases.

Fixed:
- 168 items;
- 3 dimensions;
- destroy size 54;
- 384-node repair slice;
- 18 contexts;
- 200 controller decisions;
- horizon 40;
- scientific byte capacity 4,206 bytes;
- frozen existing MDKP recurrence model;
- same independent serializable DFS branch-and-bound backend.

No refitting of recurrence models on the new 80 cases.

---

## 13. Policies

Both RQ2 and RQ3:

1. Restart;
2. Empirical-pW;
3. Learned-pW (PCR-v1);
4. Empirical-pC;
5. Learned-pC.

Optional keep-all is used only for graph capacity characterization/descriptive upper-resource reference and is outside the primary superiority family.

### Interpretation
- Learned-pC vs Learned-pW isolates value-unit refinement under the learned probability mechanism.
- Learned-pC vs Empirical-pC isolates incremental predictive probability value under compute valuation.
- Empirical-pC vs Empirical-pW is secondary mechanism decomposition.

---

## 14. Primary machine sharding

Graph:
- each family sorted by frozen case SHA-256;
- alternate A/B;
- 10/family/primary = 30 graph cases/primary.

MDKP:
- sort 80 by frozen SHA-256;
- alternate A/B;
- 40/primary.

Assignment is outcome-blind and frozen before timing.

---

## 15. Primary timing

Five timed repeats because five policies are compared.

Base order:
1. Restart
2. Empirical-pW
3. Learned-pW
4. Empirical-pC
5. Learned-pC

For each case/level, derive deterministic offset from frozen case+level hash.

Repeat \(r=0,\dots,4\) uses cyclic rotation by \((offset+r)\bmod5\).

Thus every policy occupies every ordinal run position exactly once.

Primary case/policy runtime = median of five repeats.

### Timing scope
The outer timer surrounds the same complete controller scope for every policy.

Exclude only:
- one-time model loading;
- instance generation;
- trace generation;
- precomputed capacity characterization;
- result file flushing.

No per-decision disk writes or detailed nested timers inside primary timed runs.

Use:
- `perf_counter_ns()` primary wall time;
- whole-run `process_time_ns()` secondary.

---

## 16. Profiling subset

Before outcomes are opened, select prospectively:
- 10 lowest-hash graph cases from each primary shard = 20 total;
- 10 lowest-hash MDKP cases from each primary shard = 20 total.

Separate non-primary profiling:
- graph L1 + L4;
- all five policies;
- MDKP principal setting;
- all five policies.

Collect mutually exclusive buckets:
- feature;
- prediction;
- allocation;
- exact search;
- serialization;
- compatibility gate;
- restoration;
- maintenance;
- remaining controller.

These profiling runs do not enter primary runtime inference.

---

## 17. Secondary hardware robustness

Select before primary analysis:
- Graph: 20 total, family-balanced as 7 Generic / 7 Workflow / 6 Microservice, with the selection rule frozen by hash and primary-origin balance.
- MDKP: 10 lowest-hash assigned cases from each primary = 20.

On CONTROL_SECONDARY:
- Graph L4 only;
- MDKP principal setting;
- Restart / Learned-pW / Learned-pC;
- five repeats;
- same frozen source/models/weights/cases;
- no retuning.

Run this block **after primary completeness but before aggregate primary effects are unblinded**.

It is descriptive robustness and is not pooled into primary hypothesis tests.

---

## 18. RQ2 primary estimands

Define:

\[
S^\pi_{c,\ell}
=
\log\frac{T^{e2e}_{restart,c,\ell}}
{T^{e2e}_{\pi,c,\ell}}.
\]

### RQ2-A: opportunity conversion
\[
D^{opp}_c=
S^{learned-pW}_{c,L4}
-
S^{learned-pW}_{c,L1}.
\]

### RQ2-B: compute-aware refinement
\[
D^{value}_c=
\log\frac{T^{e2e}_{learned-pW,c,L4}}
{T^{e2e}_{learned-pC,c,L4}}.
\]

### RQ2-C: net acceleration
\[
D^{net}_c=
\log\frac{T^{e2e}_{restart,c,L4}}
{T^{e2e}_{learned-pC,c,L4}}.
\]

All four opportunity levels are reported; L4 is the frozen primary refinement level.

---

## 19. RQ3 primary estimands

### RQ3-A
\[
D^{value}_c=
\log\frac{T^{e2e}_{learned-pW,c}}
{T^{e2e}_{learned-pC,c}}.
\]

### RQ3-B
\[
D^{net}_c=
\log\frac{T^{e2e}_{restart,c}}
{T^{e2e}_{learned-pC,c}}.
\]

### RQ3-C
\[
D^{learn}_c=
\log\frac{T^{e2e}_{empirical-pC,c}}
{T^{e2e}_{learned-pC,c}}.
\]

---

## 20. Statistical analysis

Independent unit = case.

Nested:
- repair decisions;
- checkpoints;
- opportunity levels;
- timing repeats.

For every primary contrast:
- mean case-level log effect;
- exponentiated geometric mean runtime ratio;
- percent runtime effect;
- mean and median paired millisecond difference;
- 95% case-bootstrap CI, 10,000 resamples;
- two-sided paired Wilcoxon as complementary test.

Multiplicity:
- Holm across RQ2-A/B/C;
- separately Holm across RQ3-A/B/C.

### Machine/family blocking

RQ2 bootstrap:
- resample within machine × graph-family strata;
- combine with original equal case weighting.

RQ3:
- resample within primary-machine strata.

Report machine-specific descriptive effects beside the pooled effect.

No runtime-magnitude outlier deletion.

A node/compute-unit improvement cannot rescue a failed runtime endpoint.

---

## 21. Technical failure and attempt ledger

Every attempted timed execution appends to an immutable write-ahead log.

Rerun permitted only for:
- process crash;
- incomplete/corrupted output;
- VM reboot/suspend during the case block;
- strict preflight failure;
- deterministic trajectory mismatch;
- missing required run cell.

A technically valid completed execution is never rerun because its scientific outcome is unfavorable.

If reboot occurs during a case block, rerun the **whole case block** under the new execution epoch; retain earlier attempts in the WAL.

No aggregate policy effect is displayed until:
- both primary shards complete;
- secondary robustness block completes;
- completeness audit passes.

---

## 22. Seed freeze

Generate new seeds deterministically from the final protocol SHA-256.

Reject every seed in `config/PRIOR_SEED_REGISTRY.json`.

Freeze:
- graph 60 case seeds;
- MDKP 80 seeds;
- instance hashes;
- machine assignment;
- profiling subset;
- secondary subset;
- timing schedule.

No seed replacement based on observed difficulty/outcome.

---

## 23. Success interpretation

### Strong strengthening
- RQ2 opportunity conversion favorable;
- pC improves over pW at frozen L4;
- net acceleration appears at L4 and/or MDKP;
- exactness unchanged;
- direction broadly consistent across backends.

### Partial
Examples:
- conversion improves with opportunity but pC adds little;
- pC beats pW but not restart;
- benefit is backend-dependent;
- semantics-preserving implementation optimization explains more than valuation.

### Null
pC does not improve untouched runtime.

Interpretation: heterogeneous operation cost is insufficient to explain the conversion boundary.

### Falsification
- correctness/compatibility changes;
- future leakage;
- post-unblinding retuning;
- selective outcome exclusion.

There is no fourth post-hoc method on the same untouched cases.

---

## 24. Manuscript integration

Do not rewrite results before the campaign.

The final Transactions manuscript must retain:
- original RQ1 positive evidence;
- original RQ2 mixed conversion evidence;
- original P10 null/negative primary result.

Then add the prospective extension as diagnosis → frozen refinement → untouched confirmation.

The literature positioning remains bounded: pC is a conversion refinement, not a claim of first cost-aware predictive retention.
