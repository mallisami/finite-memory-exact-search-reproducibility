# Pre-execution checklist — P0 coefficient-only graph timing rerun

## Package and environment
- [ ] Use the same frozen ZIP on all three VMs; do not edit source, schedules, models, config, or protocol after timing starts.
- [ ] VM-A and VM-B each expose exactly 4 logical CPUs and at least 14 GiB RAM.
- [ ] VM-C exposes exactly 2 logical CPUs and at least 7 GiB RAM.
- [ ] Primary VMs are not burstable Azure B-series instances.
- [ ] Python 3.12.x and the venv module are installed before running `setup_vm.sh`.
- [ ] `bash 07_SCRIPTS/setup_vm.sh` passes on each VM.

## Frozen experimental design
- [ ] Phase-A primary schedules contain exactly 6,000 rows over 60 cases, L1-L4, five policies, and five repeats.
- [ ] The six primary Phase-A lanes are disjoint by whole case and reproduce the original A/B schedule union exactly.
- [ ] Phase-B full isolated schedules contain exactly the complete original 3,000-row A and 3,000-row B schedules, in original row order.
- [ ] VM-C contains the frozen 500-row L4 robustness schedule and is descriptive only.
- [ ] Coefficient-only scorer equivalence passes at <1e-12 maximum absolute probability error and development trajectory/counter equivalence passes.

## Execution
- [ ] Start VM-A, VM-B, and VM-C wrappers without manually changing CPU affinity.
- [ ] Do not inspect Phase-A timing outcomes before Phase B completes.
- [ ] Do not selectively rerun successful run IDs.
- [ ] Use `--resume` only through the supplied wrappers after a technical interruption.
- [ ] Bundle each VM's results before restoring services.

## Post-run acceptance gates
- [ ] Phase A: 6,000/6,000 primary successful observations.
- [ ] Phase B: 6,000/6,000 full isolated primary successful observations.
- [ ] VM-C: 500/500 successful descriptive observations.
- [ ] Every new run ID maps to the original campaign and reproduces trajectory hashes and non-timing scientific counters.
- [ ] Primary inference uses Phase B only; Phase A and VM-C remain supporting/descriptive.
