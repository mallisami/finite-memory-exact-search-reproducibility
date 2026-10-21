# P7/P7B Invalidation Amendment — Actual Placement Change, 2026-10-05

## Trigger
The first frozen P7B sweep returned end-of-iteration portfolio width 1 in all 81 structural cases. A mechanistic audit of the baseline `24/6, |S|=8` setting found that 186–193 of 200 accepted proposals per domain were **placement no-ops** (zero nodes changed), yet the P7 online invalidation hook evicted checkpoints whenever `accepted=True`, treating the entire destroy set as moved.

## Why the old behavior was too conservative
PCR validity is affected by changes to the placement/cache state, not by the controller's acceptance flag itself. Accepting a proposal with `q == p` changes neither host occupancy, external gains, pair gains, nor residual capacity. Invalidating checkpoints on such an event is safe but scientifically inappropriate for measuring natural persistence opportunity because it destroys valid state that remained exactly reusable.

## Frozen correction
For P7 online derivatives only:
1. determine the **actual changed nodes** from the accepted placement (`q != p`);
2. if no host changes, do not invalidate or rebase any checkpoint;
3. if the producing repair changes hosts, rebase its own checkpoint using the existing same-scope rule;
4. for every other checkpoint:
   - conservatively invalidate if another repair changed one of its free nodes (no certified cross-context gain-offset rebase is implemented);
   - otherwise rebuild its local cache under the new placement and retain it only when the existing exact PCR `cache_equal_for_resume` rule passes.

This correction changes no exact-search semantics, P1–P6 evidence, P6 predictor, or P5.6 selector. It only makes online persistence validity depend on **actual state change** rather than the looser `accepted` control-flow event.

## Evidence status
- All P7 pilot/P7A results produced before this amendment are **superseded for online portfolio-width and reuse interpretation**.
- The first P7B width-1 sweep is retained as an engineering diagnostic showing the effect of the conservative invalidation hook, not as scientific evidence about natural portfolio width.
- P7B will be rerun from scratch under the corrected exact-compatibility logic using the previously frozen structural matrix and eligibility criteria. The regime-selection criteria are unchanged.
