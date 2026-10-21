# Final Pre-Confirmation Checklist

Untouched cases may be generated only when every item is PASS.

## Hardware / environment
- [ ] live role assignment identifies exactly 2 × 4-vCPU/~16-GiB + 1 × 2-vCPU/~8-GiB
- [ ] primary Azure SKUs are non-burstable
- [ ] same exact Python patch on both primaries
- [ ] same exact package lock
- [ ] same source/model hashes
- [ ] thread caps verified
- [ ] services quiesced
- [ ] boot IDs frozen

## Baseline equivalence
- [ ] pW probabilities match reference <=1e-12
- [ ] pW selected checkpoint IDs identical
- [ ] compatibility identical
- [ ] branch trajectory hashes identical
- [ ] objective trajectories identical
- [ ] scientific blob SHA/size identical

## pC method
- [ ] six fixed counters implemented
- [ ] sidecars do not alter scientific bytes
- [ ] integer weights fitted only on PRIMARY_A exposed development data
- [ ] PRIMARY_A grouped-CV gates pass
- [ ] PRIMARY_B fixed-weight validation gates pass
- [ ] restart/resume leverage sanity gate passes on both
- [ ] pC cross-primary deterministic replay passes

## RQ2 design
- [ ] L1-L4 frozen from restart-only development unfinished fractions
- [ ] level-selection audit saved
- [ ] capacity formula uses max(max_cp, round(.25*peak))
- [ ] 60 new graph seeds not yet generated before this point

## RQ3 design
- [ ] MDKP fixed settings match protocol
- [ ] 80 new MDKP seeds not yet generated before this point

## Statistics / operations
- [ ] analysis script dry-run on synthetic dummy data passes
- [ ] policy schedule generator passes
- [ ] WAL schema passes
- [ ] completeness checker passes on dummy schedule
- [ ] profiling subset rule frozen
- [ ] secondary subset rule frozen
- [ ] protocol/source/config/analysis hashes frozen

Only now:
- [ ] generate untouched seeds/cases once
- [ ] freeze case hashes and shards
- [ ] run the campaign
