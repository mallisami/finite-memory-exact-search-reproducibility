# RQ3 negative and rejected-correction evidence (6 November 2026)

These are original diagnostic files from the author archive, retained for the
paper's RQ3 inference boundaries. **The correction is NOT adopted.** These are
not independent confirmatory results or additions to the paper's primary
multiplicity family.

### Original and reconstructed labels

- Historical training data: **1,948** candidate checkpoints from **25** seed groups;
  the reconstructed diagnostic contains **1,875**, not the original population.
- Reconstruction excludes **117** administratively censored cases and **31**
  terminal-quality mismatches, leaving **1,727** eligible observations.
- CPU timing repeatability test: **40** checkpoints, seven alternating repeats,
  with **13 of 36** zero-node-saving checkpoints exhibiting 6/7 same-sign
  reliability; the prespecified 90% reliability gate fails.
- The file `RECONSTRUCTION_AND_CORRECTION_GATE.json` and individual paired
  CPU observations retain this negative result.

### Seed-held-out correction experiment

- Original versus corrected separate leave-one-seed-out policies were tested
  only on the 25 development seeds. The corrected policy's geometric node
  ratio relative to historical = **1.017092**, 95% bootstrap interval
  **[0.996186, 1.055508]**; one seed regressed in terminal objective.
- Improved OOF prediction metrics do **not** establish closed-loop policy
  effectiveness. `RESULT_SUMMARY.json` designates this result **NO_GO**.
- Official RQ3 VM90 outcome remains unchanged; no fresh AWS confirmation
  has been performed on the rejected correction.

Run `PYTHONPATH=src pytest -q tests/test_rq3_rejected_diagnostics.py` to
recalculate the key denominators and gates from archived raw and JSON files.

No original VM host identifiers, IPs or author documents are deposited in
this negative-evidence subdirectory. These are development-stage scientific
diagnostics, not a validated new method.
