# P10 Final Independent Validation Protocol — Re-audited Freeze

**Status:** frozen before authoritative execution  
**Purpose:** close the remaining generalization/practical-value gap without reopening P6–P9 or outcome-shopping.

## 1. Scientific question

Does predictive finite-memory persistence remain valid when moved away from the original graph-assignment repair implementation to a distinct combinatorial problem and separately implemented exact-search backend, and does useful retained state translate into reduced new exact-search work and/or controller-runtime wall-clock time under a live optimizer trajectory?

P10 is a final external validation block. It does not replace P6–P9 and does not retroactively redefine an earlier primary endpoint.

## 2. Independent problem and exact-repair backend

P10 uses **0–1 multidimensional knapsack (MDKP)** with integer profits and three integer resource constraints. The outer controller repeatedly reoptimizes a selected item subset while all outside items remain fixed.

The exact repair backend is a new serializable depth-first branch-and-bound implementation in `independent_mdkp/` (`code/independent_mdkp/` in the standalone package; `04_CODE/independent_mdkp/` in the complete archive). It does not call the Paper-2 graph-assignment repair engine. P10 also carries its own instantaneous byte-allocation implementation in `independent_mdkp/allocation.py`; learned and empirical-compatible policies use that identical allocator, while P6–P9 remain tied to their original frozen code. A checkpoint contains the unresolved frontier, incumbent, fixed item ordering, residual-capacity vector, invested node count, and an instance fingerprint.

A retained checkpoint may execute only if its instance fingerprint, repair context, and residual capacities implied by the current outside assignment match exactly. For MDKP these quantities are sufficient for the saved search state because outside-item profit contributes only a constant to the repair subproblem and all constraints are additive in the residual capacities.

For engineering certification, completed repair subproblems at small and **representative P10 scales** are solved independently by SciPy/HiGHS MILP and compared with the custom branch-and-bound optimum. HiGHS is not used as the resumable repair engine.

### Independent allocation layer

To avoid an unnecessary implementation dependency on the original Paper-2 allocation module, P10 uses a local exact instantaneous 0/1 byte allocator. Pools of at most 12 checkpoints use an exact sparse dynamic program; wider pools use the equivalent binary MILP through SciPy/HiGHS with requested `mip_rel_gap=0.0`. The same P10-local allocator is used for learned and empirical-compatible policies. This changes no P6–P9 code or evidence.

## 3. Exact work-accounting gate

Before scientific execution, the deterministic exact-repeat identity must hold on engineering cases:

`restart nodes to exact closure - new nodes after checkpoint resume = nodes already invested in the checkpoint`.

This directly validates the interpretation of invested exact-search nodes as avoided repeated work under compatible deterministic resume semantics.

## 4. Live execution rather than shadow replay

Every policy executes a real optimization-controller trajectory. Checkpoints are actually serialized, admitted/evicted, deserialized, compatibility-checked, resumed, and advanced. Controller-runtime timing includes policy scoring, exact memory allocation, serialization/restoration, compatibility handling, controller logic, and exact repair work.

Timing **excludes one-time model loading, instance generation, and context-trace construction**, which occur before the timed controller loop. This boundary is recorded in the environment metadata.

The repair-context trace and acceptance uniforms are exogenous and identical across policies within a case. State trajectories may still diverge because policies can produce different repair incumbents and acceptance decisions. The estimand is therefore policy-level performance under matched exogenous opportunities, not identical future candidate pools.

P10 is a live optimization-controller validation, **not** a production DeathStarBench redeployment or microservice-SLO experiment.

## 5. Outcome-blind structural/runtime screen

The screen uses keep-all only. No learned-policy, learned-versus-empirical, objective-improvement, work-saving contrast, or policy wall-clock contrast enters regime selection.

Candidate cells are frozen:

- 120 items / destroy size 42;
- 144 items / destroy size 48;
- 168 items / destroy size 54.

Each cell uses **nine independent screen seeds (8051–8059)**, 120 controller iterations, 18 recurring contexts, and 384 branch-and-bound node expansions per interrupted repair call.

A non-authoritative warm-up seed (8049) executes before screen timing. Candidate cells are then rotated/interleaved within screen seeds so a fixed cell order cannot determine the runtime ranking.

Eligibility requires:

1. median peak live checkpoints at least 4;
2. median fraction of iterations with at least four live checkpoints at least 0.10;
3. median useful compatible resumes at least 1;
4. median largest-checkpoint / keep-all-peak-byte ratio at most 0.40.

Among eligible cells, select lexicographically by:

1. median repair-search milliseconds per decision (largest first);
2. median fraction of iterations with at least four live checkpoints;
3. median peak live checkpoints.

This intentionally selects a nontrivial exact-repair regime without using any learned-policy or comparative outcome.

### Fixed confirmatory byte budget

After the outcome-blind screen, the primary byte budget is fixed as

`max(median largest checkpoint bytes, round(0.25 × median keep-all peak bytes))`

from the selected screen cell. The same fixed `M` is supplied to learned and empirical-compatible policies in all confirmatory cases. Confirmatory execution never observes a case-specific future keep-all peak.

## 6. Predictor development and feature firewall

The P10 predictor is a domain-specific replication of the policy architecture; the P6 fitted coefficients are not claimed to transfer unchanged across unrelated numerical scales.

The model family is fixed before authoritative data generation:

- logistic regression, `C = 10`;
- five case-grouped folds;
- Platt calibration fitted to out-of-fold logits;
- no model-family search on P10.

The 14 frozen decision-time features are listed explicitly in `P10_FROZEN_CONFIG.json`. They contain recurrence history and observable controller dynamics only. The synthetic generator's latent hot/warm/cold identifier (`current_context_class`) is **forbidden** and is not supplied to the predictor. Future recurrence, future compatibility, future saved work, and policy outcomes are likewise excluded.

Development uses 30 independent seeds. A separate 15-case holdout uses seeds 8251–8265 after the screen-selected regime is fixed. Holdout reporting includes prevalence, a history-only logistic baseline, and the frozen H+D analogue, with 2,000 independent-case bootstrap intervals. Learned-probability calibration intercept and slope are also evaluated at the case level.

The binary target is useful compatible recurrence within 40 future iterations for a currently unfinished exact repair. Labels are generated from restart-only reference trajectories.

## 7. Confirmatory policies

The four prespecified policies are:

1. `restart` — no persistence;
2. `empirical_compatible` — smoothed recurrence × observed compatibility, multiplied by invested exact-search nodes;
3. `learned` — calibrated P10 probability × invested exact-search nodes;
4. `keep_all` — upper-resource reference.

Learned and empirical-compatible use the same checkpoint representation, byte accounting, compatibility gate, and exact instantaneous memory allocator. Their designed difference is probability valuation.

## 8. Confirmatory sample and timing design

- 45 independent confirmatory seeds (8401–8445), fixed before outcomes;
- 200 controller decisions per case;
- screen-selected scale/destroy size;
- screen-selected fixed byte budget for learned and empirical-compatible;
- three deterministic timing repeats per case-policy;
- authoritative wall-clock execution is sequential, not multiprocessing.

The 45-case size is fixed to match the prior confirmatory scale and support paired case-level estimation. There is no sequential or outcome-dependent sample-size expansion.

Before authoritative timing, a non-authoritative warm-up seed (8399) is executed. Within each confirmatory case and repeat, the four policies are run using a frozen 4×4 Latin-square counterbalancing rule; repeats are interleaved rather than running all repeats of one policy consecutively. Thus no policy is systematically first or last.

All non-timing scientific counters must be identical across the three repeats of a case-policy. The per-case timing statistic is the median controller-runtime milliseconds over the three repeats.

The execution wrapper pins `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, and `NUMEXPR_NUM_THREADS` to 1 and sets `PYTHONHASHSEED=0`. `P10_ENVIRONMENT.json` records platform, CPU, Python/package versions, and timing scope before confirmatory execution.

## 9. Frozen endpoint hierarchy

### Primary mechanistic endpoint

Paired learned-minus-empirical **total prior exact-search nodes represented at legal compatible resumes per case**. This is trajectory-native and has no policy-dependent keep-all denominator. It is a resume-weighted mechanistic quantity rather than a count of unique historical nodes.

### Primary operational endpoint

Paired empirical-minus-learned **new exact-search nodes executed per case**. Positive values mean learned executes less new search.

### Primary wall-clock endpoint

Paired restart-minus-learned **median controller-runtime milliseconds per case** over three counterbalanced repeats. Positive values mean learned is faster than restart and therefore directly tests net wall-clock benefit. Empirical-compatible minus learned timing is retained as a secondary incremental learned-policy contrast.

### Downstream optimization endpoint

Relative best-objective improvement of learned versus restart. Positive values indicate a better minimization objective under learned persistence.

A null objective effect is retained as a legitimate downstream boundary and is not a trigger for experiment replacement.

### Secondary endpoints and references

- empirical-compatible minus learned controller-runtime milliseconds;
- restart-minus-learned new exact-search nodes;
- learned-minus-empirical useful compatible resumes;
- learned-minus-empirical checkpoint byte-time and peak bytes;
- learned-minus-empirical capacity evictions and compatibility invalidations;
- policy-level serialization/restoration/selection/model-scoring/repair-search timing components;
- learned-versus-empirical downstream objective contrast;
- keep-all policy-level retention/work/memory/timing outcomes as an upper-resource descriptive reference only.

Because online policy choices can alter later trajectories, keep-all is not treated as a common-trajectory clairvoyant oracle.

## 10. Inference and multiplicity

The independent **case** is the inferential unit. Each prespecified paired contrast reports its mean paired case effect, deterministic 10,000-resample case-bootstrap 95% confidence interval, median effect, and positive/negative/tied case counts. Events, checkpoints, B&B nodes, and timing repeats are not independent replicates.

If formal rank tests are reported for the three P10 primary contrasts—learned-minus-empirical reused prior nodes, empirical-minus-learned newly executed nodes, and restart-minus-learned wall-clock time—use one-sided Wilcoxon signed-rank tests in the prespecified positive direction and **Holm-adjust across this three-primary-endpoint family**. Bootstrap intervals remain estimation intervals. Secondary and downstream endpoints cannot replace a failed primary endpoint.

## 11. Engineering gates

Before authoritative P10 execution:

1. custom MDKP B&B exact completions must match HiGHS MILP optima on small and representative-scale engineering cases;
2. interrupted → serialized → restored → exact completion must equal uninterrupted exact completion;
3. deterministic restart-minus-resume node accounting must equal invested checkpoint nodes;
4. residual-capacity changes outside the repair context must invalidate stale checkpoints;
5. the optimized NumPy scoring path must match the fitted scikit-learn + Platt computation numerically;
6. the P10-local wide-pool byte allocator must match an exact brute-force objective on an engineering instance and request zero MIP relative gap in authoritative wide-pool solves;
7. repeated timing runs must reproduce all non-timing scientific counters exactly;
8. authoritative screen/development/holdout/confirmatory/warm-up seed sets must be disjoint;
9. the privileged generator class must be absent from the frozen prediction feature contract;
10. the sealed holdout stage must complete before confirmatory execution.

A gate failure halts execution and is an engineering issue, not a scientific outcome.

## 12. Output preservation, provenance, and reporting completeness

Authoritative stage files are **not overwritten** by default. If an authoritative stage output already exists, the driver halts and requires a fresh output directory. This protects the first execution record from silent replacement.

The confirmatory analysis emits both the frozen inferential contrasts and `p10_policy_descriptives.csv`, which contains policy-level retention, work, memory, eviction, objective, and median timing-component summaries, including keep-all.

After confirmatory completion, `P10_EXECUTION_SEAL.json` hashes:

- the frozen configuration;
- the actual P10 source files executed;
- the pre-execution package manifest when available;
- the recorded environment file;
- every principal confirmatory result file.

## 13. Stop rule

After the frozen P10 confirmatory block is executed and analyzed, **do not add another experiment merely because wall-clock, work-saving, or objective effects are null or smaller than expected**. The observed result becomes the result.

Further work is justified only if P10 reveals a pre-existing engineering invalidity that prevents the protocol from answering its stated question.
