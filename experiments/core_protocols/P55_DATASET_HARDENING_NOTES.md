# Paper 2 P5.5 — Dataset / Protocol Hardening Notes

## Status
**PASS — ready for baseline-first P6 under frozen splits/features.**

## What was added
- `paper2_dataset_hardening.py`: natural controller recurrence/compatibility event generation.
- `paper2_p55_hardening.py`: frozen 45-case corpus runner.
- strict decision-time feature firewall.
- grouped train/validation/test split by base instance.
- P5.5 unit/regression tests.

## Corpus
- 3 domains;
- 15 independent seeds/domain;
- 45 independent base cases;
- 200 natural controller iterations/case;
- 15 declared decision epochs/case;
- 675 natural decision events;
- no recurrence sampler;
- no supplied repair trace;
- no curated compatibility perturbation.

## Natural event prevalence
Overall:
- future exact recurrence within 40 iterations: **37.63%**;
- useful compatible recurrence: **26.37%**;
- conditional compatibility given recurrence: **70.08%**.

By split, useful compatible recurrence is:
- train: **26.67%**;
- validation: **22.96%**;
- test: **28.89%**.

The corpus therefore has nontrivial positive and negative classes without forcing a balanced label distribution.

## Group isolation
- train: 27 cases / 405 rows;
- validation: 9 cases / 135 rows;
- test: 9 cases / 135 rows;
- **0 base cases cross splits**;
- candidate IDs are unique across all 675 rows.

## Leakage hardening
The model-input whitelist contains 28 explicitly permitted decision-time fields.
Future/outcome/oracle fields are explicitly prohibited.

The initial deterministic invested-work cycle was rejected because it encoded decision time. P5.5 instead shuffles invested-work levels within each case using a seed fixed before future labels are observed. In the frozen corpus, invested work vs decision iteration correlation is approximately **-0.034**.

## Natural recurrence bookkeeping correction
The matched controller's `IterationRecord.recurrent` flag is only populated by the explicit recurrence/trace mechanisms. P5.5 therefore computes natural recurrence directly as repeated destroy-set occurrences in the ordinary controller trace. The frozen cases average **85.47** natural repeat events over 200 iterations (median 87).

## Verification
- P5.5 + P1-P5 focused tests: **21 passed**.
- derivative verification: **8,521 frozen-base files unchanged + 66 authorized derivative files**.
- P5.5 outputs regenerated independently: all five canonical output files matched SHA-256 exactly.
- Feature-firewall audit: 28/28 allowed features present; no forbidden field is in the allowed list.
- split audit: zero `(domain, seed)` groups cross splits.

## Scientific consequence
P5.5 removes the main methodological obstacle identified by the independent audit. P6 may now compare simple predictive models, but must use the frozen grouped split and feature firewall. P5 remains a controlled stress set; P5.5 is the primary natural prediction corpus.

## What remains unestablished
- no ML superiority claim;
- no GNN justification yet;
- no end-to-end finite-budget online controller gain;
- no universal real-world recurrence/compatibility prevalence claim.
