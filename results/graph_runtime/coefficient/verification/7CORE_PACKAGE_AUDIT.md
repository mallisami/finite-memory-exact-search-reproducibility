# 7-Core + Full-Isolated P0 Package Audit

## Design
- Peak concurrent Phase-A timed processes: **7** (VM-A CPUs 0/1/2; VM-B CPUs 0/1/2; VM-C CPU 0).
- Reserved OS vCPUs: VM-A CPU 3, VM-B CPU 3, VM-C CPU 1.
- Phase-A primary rows: **6,000**, exactly the original 60-case L1-L4 schedule, repartitioned by whole case into six disjoint 1,000-row lanes.
- Phase-B isolated rows: **6,000**, exactly the original full A/B primary schedules in original row order.
- VM-C descriptive rows: **500**, unchanged frozen L4 secondary subset.
- All five policies and five repeats are retained.

## Why Phase B is full rather than L4-only
The reviewer concern applies to the repeated graph timing experiment as a whole. A previous draft package isolated only L4 after the seven-core campaign. This final package instead repeats **all four operating levels in isolation**, so the reviewer-facing timing rerun preserves the original 60-case L1-L4 design and changes the learned scorer without relying on multi-process contention for the primary conclusion.

## Lane balancing
Phase-A lane assignment was frozen from historical original-campaign runtimes only, before coefficient-only timing outcomes existed. Each primary lane has ten complete cases, and family composition rotates 4/3/3 so the host-level total remains 10/10/10.

## Scientific protection
Phase A is supporting evidence under a fixed high-throughput load. After Phase A, each primary VM automatically waits 300 s, re-passes low-load preflight, warms CPU 0, and executes its complete original 3,000-row schedule with one process pinned to CPU 0. **Phase B is the authoritative P0 inference.** Phase-A and Phase-B wall times are never pooled.

## Verification gates
- Schedule/partition validation must pass.
- Coefficient-only scorer vs frozen sklearn pipeline on 225 held-out rows must pass at <1e-12 maximum absolute probability error.
- Development end-to-end trajectory/counter equivalence must pass.
- Runner smoke tests and analysis-contract test must pass before release.
- Python and Bash syntax checks must pass.
- Immutable package manifest must pass after final archive creation.

## Interpretation boundary
Historical original-scorer timings are descriptive context only. The final P0 scientific conclusion is based on the newly executed full isolated Phase-B coefficient-only learned-versus-empirical comparisons. No experimental result is pre-populated in `09_RESULTS`.
