# November 2026 PCR2 source alignment (curated GitHub subset)

The authoritative full author-side research archive is `PCR2_PAPER2_FIGURES_TABLES_CORRECTED_FINAL_20261107.zip`. This GitHub repository is a separately curated research subset, **not** the full five-folder archive. The public subset must not be substituted for the author's complete evidence package.

## Versions and estimands

- P6 held-out prediction and the original P7 study retain their original frozen datasets; those historical records are not overwritten.
- The original `data/core/measured_replay/` and `results/measured_replay/` records reflect an earlier measured-replay version. The **current manuscript's corrected AWS P8** uses 90 sequences in 30 application-repetition blocks, with the derived results deposited in `figures/data/p8_aws_triplet_block_work_saving_20261107.csv` and `figures/data/p8_aws_app_regime_heterogeneity_20261107.csv`.
- In the corrected P8 AWS analysis, learned versus restart displaced 24.388889 fresh pops per sequence (95% triplet-block CI 16.766667 to 32.422222). Learned versus empirical-compatible displaced 1.911111 additional pops (95% triplet-block CI 0.044444 to 4.689167). The latter is a derived post-hoc interval, not a preregistered adjusted discovery. Execution overhead is substantially higher for learned. Do not claim overall runtime superiority.
- The original `results/transfer/p9_cross_domain_metrics.csv` is the earlier fixed-selection P9 evaluation. The current paper's **nested family-held-out P9** uses `figures/data/p9_nested_family_heldout_20261107.csv`. These results must not be interchanged.
- The 45-case P10 confirmatory study was run and sealed. A subsequent timing replication on the **same 45 case identities** is recorded in `results/mdkp/p10_original_vs_replication_20261107.csv`. Do not count those as 90 independent cases.

## Figure status and full reproduction

The 2026-11-07 author-side archive retains the current manuscript source, the exact final figure PDF files, repaired general figure builder, corrected AWS P8 rows, nested P9 source analysis, and original P10 execution and repeat files. **The repaired author figure builder and corrected AWS Figure 4 helper are now also source-ported into GitHub, with only release-relative paths adapted.** The GitHub `figures/publication/` PDFs are the corrected November figures. Figures 2–5 and S1 are byte-identical to the author's release; Figure 1 has review-safety metadata and an embedded Content Credentials attachment removed while retaining the same rendered pixels.

No manuscript, reviewer identity, host IP, AWS account identifier, private key, or full original VM log archive is added through this alignment. GitHub remains a public, identity-bearing repository. Because the current manuscript PDF says *Anonymous submission*, cite or expose the repository URL to reviewers only when the destination journal confirms that this is permitted.

## Verification scope

`python verify.py` verifies the original curated evidence and the November 2026 additional numerical summaries. The corrected summary files are supported by the corresponding deposited P8 AWS rows, P9 nested analysis, and P10 original/repeated result files under `results/`. These verify the retained evidence and do not recreate the original cloud executions. Historical raw-input and cross-environment byte-identity boundaries remain documented separately.
