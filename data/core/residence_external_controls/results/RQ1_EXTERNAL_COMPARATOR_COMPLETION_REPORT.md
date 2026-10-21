# PCR2 RQ1 external published-policy comparator — completion report

**Completion date:** 2026-10-12  
**Scope:** RQ1 finite-memory residence only; RQ2/RQ3 unchanged.  
**External policies:** checkpoint-level FIFO, LRU, and Random Replacement adaptations of Medema, Breeman & Lazovik (2024).

## Completion and integrity

- Raw executions: **945/945**.
- Unique task IDs: **945/945**; duplicates: **0**.
- FIFO: **135**; LRU: **135**; Random: **675**.
- Random repetitions: **5 unique fixed seeds in every one of 135 case×budget cells**.
- Independent cases: **45** (15 each: generic, workflow, microservice).
- Capacity conditions: **25%, 50%, 75%** of the authoritative case-specific keep-all peak.
- Byte-cap violations: **0**.
- `not_retained != 0` violations: **0** under the frozen always-admit-after-eviction rule.
- Original frozen comparator/P7 code and authoritative P7 inputs: **SHA-256 unchanged**.
- Final regression tests: **9/9 passed** (5 external-policy + 4 original online-retention).

### Execution-acceleration provenance

The confirmatory continuation used an exact-equivalent execution accelerator after the original Python path proved too slow in this container. No external-comparator outcome was inspected before this amendment. The bound accelerator was bit-exact on 150 independently generated partial states; the cache accelerator was bit-exact on 150 caches across all three domains; two development seeds × all three policies and three already-generated confirmatory FIFO/LRU/Random tasks reproduced every scientific field exactly. Only implementation timing counters may differ and are excluded from inference. The frozen task IDs, policies, seeds, exact branch-pop search semantics, checkpoint bytes, compatibility rules, and scientific outcomes were unchanged.

## Primary RQ1 result — 25% memory

Existing learned retention captures **0.9121** of keep-all reusable work on average. The existing empirical-compatible policy captures **0.8242**.

| External comparator | External mean reuse fraction | Learned − comparator | Paired bootstrap 95% CI | Learned better / worse / tied |
|---|---:|---:|---:|---:|
| FIFO | 0.5152 | +0.3970 | [0.3425, 0.4498] | 44 / 1 / 0 |
| LRU | 0.7574 | +0.1547 | [0.1120, 0.2002] | 42 / 3 / 0 |
| Random | 0.5583 | +0.3538 | [0.3107, 0.3963] | 44 / 1 / 0 |

**Primary interpretation.** LRU is the strongest external policy, but learned retention still improves keep-all-normalized reusable-work capture by **15.47 percentage points** on average, with the paired-bootstrap interval excluding zero. Learned is better than LRU in **42/45** cases. Against FIFO and Random, the mean gains are **39.70** and **35.38 percentage points**, respectively, and learned is better in **44/45** cases for each.

## Prespecified 50% and 75% sensitivity

| Budget | Comparator | External mean | Learned mean | Learned − comparator | Paired bootstrap 95% CI | Better / worse / tied |
|---:|---|---:|---:|---:|---:|---:|
| 50% | FIFO | 0.7826 | 0.9955 | +0.2129 | [0.1716, 0.2552] | 43 / 0 / 2 |
| 50% | LRU | 0.9340 | 0.9955 | +0.0615 | [0.0419, 0.0849] | 42 / 1 / 2 |
| 50% | Random | 0.8096 | 0.9955 | +0.1859 | [0.1602, 0.2128] | 45 / 0 / 0 |
| 75% | FIFO | 0.9253 | 0.9997 | +0.0743 | [0.0480, 0.1043] | 33 / 0 / 12 |
| 75% | LRU | 0.9904 | 0.9997 | +0.0092 | [0.0054, 0.0136] | 24 / 0 / 21 |
| 75% | Random | 0.9525 | 0.9997 | +0.0472 | [0.0370, 0.0579] | 45 / 0 / 0 |

The advantage narrows monotonically as capacity approaches keep-all. At 75%, LRU itself captures **0.9904** of keep-all reusable work, while learned captures **0.9997**; the paired learned–LRU difference remains positive at **+0.00923** [0.00537, 0.01357]. This is the expected saturation pattern for a finite-memory allocation mechanism.

## Additional RQ1 outcomes and claim boundary

At the shallow eight-pop RQ1 repair slice, external-policy differences in executed branch pops and objective response remain negligible: mean avoided branch pops versus restart are at most about **0.22 per case**, and best-objective/anytime contrasts are effectively zero at numerical precision. The new experiment therefore strengthens the **finite-memory residence/allocation** claim. It does **not** add a new runtime-dominance or optimization-quality claim; those remain the responsibility of the existing RQ2/RQ3 studies.

## Recommended manuscript use

Use the 25% learned-versus-LRU/FIFO/Random result as the direct published-policy comparator in the main RQ1 results, with LRU identified as the strongest external baseline. Keep the complete 50/75% sensitivity table and implementation details in the supplement. Do not describe the experiment as reproducing or outperforming the complete Medema et al. solver; these are checkpoint-level adaptations of its bounded-cache eviction policies.
