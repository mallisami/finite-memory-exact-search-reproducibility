# Technical Failure, Attempt Ledger, and No-Peeking Rules

## Immutable attempt WAL

Each scheduled execution appends:
- run_id
- case_id
- domain
- level
- policy
- repeat
- machine
- boot_id
- start/end UTC
- status
- technical_valid
- failure_code
- trajectory hash
- output artifact hash

Append; never rewrite earlier attempts.

## Rerunable technical failures

Only:
- process crash;
- incomplete/corrupted output;
- VM reboot/suspend during case block;
- strict preflight failure;
- deterministic trajectory mismatch;
- missing scheduled output.

Runtime magnitude, unfavorable policy ranking, or null scientific result are never rerun reasons.

## Reboot rule

If reboot occurs during a case block:
- retain prior attempts in WAL;
- invalidate that incomplete case block prospectively;
- rerun the entire case block on the same VM after a new preflight;
- record a new execution epoch.

Completed cases from the prior epoch remain valid.

## No peeking

During primary and secondary campaign:
- completion counts are visible;
- technical failure counts are visible;
- aggregate scientific effects are not computed/displayed.

Unblind only after:
- both primary shards complete;
- secondary robustness block complete;
- completeness audit passes.
