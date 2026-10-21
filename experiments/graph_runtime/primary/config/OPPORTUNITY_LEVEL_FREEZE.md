# Graph Search-Opportunity Level Selection Report

**Generated:** 2026-10-09T16:27:22Z  
**Rule:** Protocol V4 Section 11: L1=8, L2~75%, L3~50%, L4~25% unfinished rate on restart-only exposed development cases  

## Candidate Budget Characterization

| Budget ($B$) | Total Repair Calls | Unfinished Count | Unfinished Rate | Target Milestone |
|:---:|:---:|:---:|:---:|:---:|
| 8 | 1800 | 1791 | 0.9950 (99.5%) | **L1** (frozen baseline (8)) |
| 16 | 1800 | 1581 | 0.8783 (87.8%) | **L2** (nearest 75% unfinished) |
| 32 | 1800 | 990 | 0.5500 (55.0%) | **L3** (nearest 50% unfinished) |
| 64 | 1800 | 365 | 0.2028 (20.3%) | **L4** (nearest 25% unfinished) |
| 128 | 1800 | 62 | 0.0344 (3.4%) |  |
| 256 | 1800 | 6 | 0.0033 (0.3%) |  |
| 384 | 1800 | 1 | 0.0006 (0.1%) |  |

## Frozen Operational Levels

- **L1**: `8` branch pops (unfinished rate = 99.50%, frozen baseline (8))
- **L2**: `16` branch pops (unfinished rate = 87.83%, nearest 75% unfinished)
- **L3**: `32` branch pops (unfinished rate = 55.00%, nearest 50% unfinished)
- **L4**: `64` branch pops (unfinished rate = 20.28%, nearest 25% unfinished)
