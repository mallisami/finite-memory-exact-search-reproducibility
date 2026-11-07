# PCR2 original publication-figure builder: provenance and verification

## Scientific source and non-destructive path port

The final author archive is `PCR2_PAPER2_FIGURES_TABLES_CORRECTED_FINAL_20261107.zip`
(SHA-256 `5e826e0112e5b17cba5703fa5e8df3abbbbd06aa7ff98ae2744e76d4e384fc01`).
Its exact original publication source artifacts are:

| Original archive relative path | Author SHA-256 |
| --- | --- |
| `02_Code/analysis/rebuild_paper_outputs.py` | `fcceb38f6a3cad3d64d11efbc900e2aa07657bd35e69ed914cf57ff7bb01c9e6` |
| `01_Manuscript/source/rebuild_Fig4_AWS.py` | `4c8bb8a4fa2e31dc0162a82a4a98a8b1f12aeea59d3fb4cd625ad32e7bc1fb41` |

The two files copied into **this public GitHub release** are the recovered original plotting logic with only source-path/output-path adaptation:

| GitHub source path | Ported source SHA-256 |
| --- | --- |
| `src/analysis/rebuild_publication_figures.py` | `e81e294bcdd4e54ac15178e39e498716e1551ae37e47536ffa9ccd384dc8113c` |
| `src/analysis/rebuild_Fig4_AWS_author.py` | `b7a9980217a0849902bb96e22123e8337580830c2022cbb3c2f84eb1bdb8dc9d` |

All scientific inputs are referenced from frozen repository P6/P7/P8/P9, RQ2 and measurement data. The author-side `01_Manuscript/source` path is deliberately replaced with `results/reproduced/publication_figures`; publication PDFs are never overwritten and manuscript source files are never copied to GitHub.

## Local independent figure test

The port was run from the standalone GitHub-style source layout against the author package's frozen evidence. Figures **2, 3, 4, 5 and S1** rendered **pixel-identically** to the authoritative final author-package PDFs when rasterized with PyMuPDF at 1.2× scaling. Figure 1 is a frozen schematic, not a data-dependent plot. PDF binary identity is not claimed across hosts because of potential metadata/font differences.

No experiment, trial, original AWS host execution, packet-capture preprocessing or unreported analysis was executed by this reconstruction.

Run:

```bash
python src/analysis/rebuild_publication_figures.py
bash verify.sh
bash run_tests.sh
```

The code checks the current AWS P8 source summary and November headline against retained observations and fails if expected P6/P7/P9 or graph-timing data are missing. CI runs the builder as part of its reproducibility suite. The original author archive is preserved as source provenance only, not offered as an alternative reviewer repository.

## Historical-record availability boundary

The original AWS host-record bundle, some P0 machine tar archives and other raw VM provenance remain in the provided author archive. They are not necessary for confirming the public matched numerical estimates, but a third party cannot reconstruct historical host execution byte-for-byte from the curated GitHub alone. Historical graph coefficient-fitting rows and original DeathStarBench packet captures were never retained; this cannot be repaired by exporting a larger GitHub archive. These limits are disclosed openly in `docs/REPRODUCIBILITY_LIMITATIONS.md`.

This release is therefore the single **available, verified, reviewer-facing computational repository** for the scientific claims, with no false claim of possessing missing original physical upstream inputs.
