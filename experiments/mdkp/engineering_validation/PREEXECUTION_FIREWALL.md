# P10 Pre-execution Firewall — Re-audited Freeze

Engineering development and re-audit checks use only non-authoritative identities. The authoritative blocks are:

- outcome-blind screen seeds: **8051–8059**;
- predictor development seeds: **8101–8130**;
- sealed holdout seeds: **8251–8265**;
- confirmatory seeds: **8401–8445**.

Non-authoritative warm-up seeds are 8049 (screen) and 8399 (confirmatory timing). Engineering certificates use the 70000-series and test/smoke identities outside every authoritative block.

The seed sets are disjoint and are machine-checked before any P10 stage executes.

Package-authoring and re-audit smoke checks do not use the authoritative screen, holdout, or confirmatory blocks. Development data may be inspected because it is development data by definition.

After this firewall and `P10_FROZEN_CONFIG.json` are hashed into the package manifest, no authoritative P10 outcome should be inspected before its frozen stage is executed. The recommended path is `p10_all`, which avoids human outcome-based selection between stages.

Authoritative stage outputs are not silently overwritten. Existing stage outputs cause the driver to stop and require a fresh output directory.
