# Paper 2 P7B — Structural Portfolio-Width Characterization Results

**Status:** PASS — a genuine multi-state online regime exists and was selected using the preregistered mechanistic rule only.

## Why P7B was necessary
The original P7 pilot suggested a maximum live portfolio width of only two checkpoints. A mechanistic audit then found that the online invalidation hook treated every accepted proposal as a placement change, including accepted no-ops with `q == p`. That conservatively destroyed still-valid state and therefore underestimated natural persistence opportunity.

The corrected online validity rule depends on **actual placement change**:
- accepted no-op: no invalidation;
- producing repair with real host changes: existing same-scope rebase;
- other dormant checkpoints: retain only if the exact PCR cache-equality rule still passes; if another repair changes one of their free nodes, invalidate conservatively.

The pre-amendment pilot/P7A width results are superseded for online portfolio-width/reuse interpretation.

## Frozen structural matrix
- domains: generic, workflow, microservice;
- scales: `(24,6)`, `(32,8)`, `(40,10)`;
- destroy sizes: 5, 8, 12;
- fresh seeds/domain: 2626, 2727, 2828;
- 81 independent cases;
- 200 controller iterations/case;
- 8 deterministic exact-search branch pops/call;
- keep-all valid unfinished checkpoints;
- ordinary matched-controller repair contexts;
- no recurrence sampler;
- no outcome-tuned trace.

## Eligibility rule
A regime was eligible only if, across its 9 independent cases:
1. median peak live checkpoints >= 4;
2. at least 6/9 cases reach `K_live >= 4`;
3. median fraction of iterations with `K_live >= 4` >= 0.05;
4. median useful compatible resumes > 0;
5. median unfinished-return fraction >= 0.20;
6. median largest-checkpoint / keep-all-peak-bytes <= 0.40.

No objective or learned-policy outcome enters eligibility or selection.

## Result
Six of the nine structural regimes were eligible.

The preregistered lexicographic rule selected:

- **nodes:** 24
- **hosts:** 6
- **destroy size:** 12
- **slice:** 8 branch pops/call

because it had the highest median fraction of iterations with `K_live >= 4`.

### Selected-regime mechanistic statistics
Across 9 independent cases:

| Endpoint | Median | Range |
|---|---:|---:|
| Peak live checkpoints | **51** | 41–77 |
| Mean live checkpoints/end iteration | **20.285** | 14.135–38.900 |
| Fraction iterations `K_live >= 4` | **0.880** | 0.810–0.955 |
| Natural exact-context recurrence events | **85** | 61–103 |
| Useful compatible resumes | **59** | 34–83 |
| Reused prior branch pops | **1,024** | 384–3,744 |
| Unfinished-return fraction | **1.000** | 1.000–1.000 |
| Invalidation evictions | **115** | 40–164 |
| Keep-all peak bytes | **2,491,477** | 2,051,979–4,175,322 |
| Largest checkpoint bytes | **69,645** | 61,026–149,778 |
| Largest checkpoint / peak bytes | **0.0270** | 0.0166–0.0402 |

This is a genuine finite-portfolio regime: one checkpoint occupies only about 2.7% of peak keep-all bytes at the median, while dozens of valid unfinished states can coexist.

## Scientific interpretation
The earlier low-width result was an artifact of overly conservative invalidation on accepted no-op proposals, not a property of the underlying optimization problem. Under validity based on actual state change plus exact cache equality, the same base scale with a larger destroy set naturally supports sustained multi-state competition.

The selected regime was chosen without looking at final objective, anytime objective, learned-policy performance, or restart-vs-persistence advantage. It is therefore suitable for the confirmatory online P7 experiment.

## Reproducibility
- focused P1–P7 tests: 28 passed;
- a representative three-case rerun (one case/domain) reproduced all integer/count/trajectory endpoints exactly; the only apparent CSV mismatch was floating-point text round-trip at ~1e-16 in a derived ratio;
- frozen structural outputs are retained under `PAPER2_P7B_STRUCTURAL/`.
