# End-to-End One-Shot Runbook V4

## Phase 0 — package verification
Run:
```bash
python scripts/verify_package.py
```

## Phase 1 — power on and inventory
Power on all three Azure VMs.

Wait for SSH.

Collect:
```bash
bash scripts/collect_cluster_inventory.sh cluster_inventory
python scripts/assign_roles.py cluster_inventory ROLE_ASSIGNMENT.json
```

If role assignment exits 3 because a primary is burstable, STOP before timing design is consumed.

## Phase 2 — prospective Python environment
Create the same dedicated venv on all three VMs.

Preferred Python: 3.12.15.

Install:
```bash
pip install -r config/requirements_pcr_tx.txt
```

Capture one canonical environment and compare all nodes.

## Phase 3 — source integration and development
Using a new extension namespace:
- implement deterministic counters + pC;
- keep `baseline_reference/` immutable;
- run PCR-v1 equivalence;
- fit cost weights on PRIMARY_A exposed data;
- integerize weights;
- validate fixed weights on PRIMARY_B;
- pass restart/resume sanity gate;
- pass pC cross-primary deterministic replay.

No new cases exist yet.

## Phase 4 — graph opportunity freeze
Using restart-only exposed development cases:
- characterize candidates 8/16/32/64/128/256/384;
- select L1-L4 by the frozen unfinished-rate rule;
- save selection report.

## Phase 5 — analysis/schedule dry run
- build dummy case manifests;
- generate schedules;
- run dummy WAL/completeness audit;
- run the frozen analysis script on dummy data.

## Phase 6 — scientific freeze
Hash:
- source;
- models;
- integer weights;
- selected levels;
- environment;
- analysis;
- generation code;
- role assignment.

Only after the checklist is fully PASS proceed.

## Phase 7 — generate untouched seeds/cases ONCE
Generate deterministic graph/MDKP seeds from the final protocol hash and prior-seed registry.

Create:
- 60 graph cases;
- 80 MDKP cases;
- case SHA-256 manifest.

Shard:
```bash
python scripts/make_case_shards.py --manifest confirmatory_cases.csv --roles ROLE_ASSIGNMENT.json --out case_shards
```

Freeze all case/subset assignments.

## Phase 8 — quiesce all three nodes
Preview then apply the quiesce script on each node.

Wait >=300 s after startup and pass:
```bash
python scripts/strict_timing_preflight.py --require-services-inactive
```

During primary timing, the secondary VM performs only light orchestration.

## Phase 9 — graph capacity characterization
Complete all 60×4 keep-all characterizations as a separate untimed phase.

Freeze:
\[
M=\max(m_{\max}, round(0.25P)).
\]

Do not calculate scientific policy effects.

## Phase 10 — generate primary schedules
For each primary shard:
```bash
python scripts/make_execution_schedule.py --shard case_shards/<host>.csv --out <host>_schedule.csv
```

The integrated scientific runner must execute this schedule exactly.

## Phase 11 — primary execution
Run PRIMARY_A and PRIMARY_B concurrently.

Within each machine:
- one timed process;
- one case block at a time;
- all policies/repeats/levels for that case local.

No aggregate effect display.

## Phase 12 — profiling subset
Run fixed profiling subset separately from primary timing.

## Phase 13 — completeness
Audit each primary schedule against its WAL.

## Phase 14 — secondary hardware block BEFORE unblinding
Run the frozen subset on CONTROL_SECONDARY:
- graph L4;
- MDKP principal;
- Restart / Learned-pW / Learned-pC.

No retuning.

## Phase 15 — final completeness audit
Only after primary + secondary are complete may aggregate effects be opened.

## Phase 16 — locked analysis once
Run frozen machine/family-stratified analysis.

## Phase 17 — manuscript integration
Apply strong/partial/null interpretation without removing historical negative/mixed evidence.

## Phase 18 — restore cluster services
Restore the exact service states captured before timing.
