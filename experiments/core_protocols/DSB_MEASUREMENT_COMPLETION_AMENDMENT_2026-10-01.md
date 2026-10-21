# E-DSB protocol amendment and completion record — 1 October 2026

This record is appended after completion of the primary E-DSB campaign. The original preregistration in
`PREREGISTRATION_DSB_DYNAMIC_2026-09-30.md` is preserved unchanged.

## Primary campaign status

The primary Azure campaign completed and passed its run-verification and construct-validation gates:

- measured states: **900/900**;
- good-state fraction: **0.996667**;
- prepared sequences: **90**;
- solver sequences: **90**;
- run verification: **PASS**.

## Second-environment subset

The preregistration described a separate burst-only second-host robustness subset. That optional follow-up was
**not executed**. It is not part of the primary confirmatory analysis, no second-host result is claimed in the
manuscript or this package, and its absence does not change the prespecified H1/H2 primary-campaign analysis.
The clean reproducibility package therefore does not include a pending second-host execution launcher.

## Socket-error state-quality guard

The frozen configuration used by the completed run includes an additional state-quality guard requiring socket
errors to remain at or below 2% for a state to count as good. The prose preregistration explicitly listed the
90% achieved-RPS and <=2% HTTP non-2xx criteria but did not separately spell out this socket-error guard.
The guard was present in the frozen implementation/configuration before solver outcomes were generated and is
retained in `config/dsb_dynamic.json`. This is documented here as a protocol-documentation clarification, not as
a post-outcome threshold change. The construct gate passed under the stricter implemented rule.

## Interpretation boundary

The primary H1 contrast (persistent PCR minus reset PCR) was unresolved at the prespecified sample size and is
not interpreted as equivalence. The primary campaign therefore does **not** establish an optimization-quality
advantage attributable specifically to cross-state persistence. The PCR-versus-HiGHS contrast is reported
separately, and the ramp regime remains a prespecified operating-boundary control.
