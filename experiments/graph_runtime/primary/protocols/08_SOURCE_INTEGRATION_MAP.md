# Source Integration Map — Required Before Untouched Cases

V4 intentionally carries immutable copies of the authoritative baseline files under `baseline_reference/`.

The extension implementation must be made in a **new source namespace**, never by overwriting those references.

## Graph backend

Reference:
- `certified_assignment/paper2_online_pilot.py`
- `certified_assignment/anytime_gap_certified_repair.py`
- `certified_assignment/step_resumption.py`
- `certified_assignment/paper2_exact_selection.py`
- `scripts/paper2_p7_confirmatory.py`

Required changes:
- controller-side deterministic operation counters;
- sidecar cumulative compute units;
- `empirical_pC` and `learned_pC` value modes;
- primary timing mode with buffered logging;
- five-policy schedule support;
- capacity-characterization command for arbitrary slice budget;
- development calibration export;
- trajectory hashing.

## MDKP backend

Reference:
- `independent_mdkp/controller.py`
- `independent_mdkp/core.py`
- `independent_mdkp/allocation.py`
- `independent_mdkp/model.py`
- `scripts/paper2_p10_independent_validation.py`

Required changes:
- controller-side deterministic operation counters;
- no modification of `MDKPCheckpoint` scientific blob solely for instrumentation;
- sidecar compute value;
- empirical-pC / learned-pC;
- five-repeat five-policy timing schedule;
- metadata-first compatibility allowed only after equivalence proof;
- buffered primary timing output;
- trajectory hashing.

## Hard source gate

Before untouched seed generation, an executable extension runner must exist and pass:
- baseline-source hash check;
- PCR-v1 equivalence;
- pC calibration gates;
- pC cross-primary deterministic replay;
- dummy schedule completion;
- frozen analysis dry-run.

A package containing only orchestration scripts is **not** sufficient to begin confirmation.

No document in V4 references a nonexistent primary runner as though it already exists.
