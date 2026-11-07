# Reproducibility limitations

This repository retains the evidence used for the paper, but two historical upstream inputs are not available in their original form.

## Graph pC coefficient fit

The historical raw per-repair rows used to fit the graph operation-cost coefficients were not retained. The repository does retain the fixed coefficients used by the reported evaluation, frozen configuration, downstream timing rows, and validation records. Consequently, the paper's reported pC evaluation can be inspected and reanalyzed, but the original coefficient-fitting dataset cannot be reconstructed from this release.

## DeathStarBench packet captures

The original packet-capture binaries were not retained. The repository retains packet-capture SHA-256 identifiers, measurement records, derived interaction/state files, sequence manifests, environment information, and the replay inputs used in the reported analysis. The measured replay can therefore be rerun from the retained derived states, but the packet-level preprocessing cannot be reconstructed from the original binaries.

## Timing portability

Elapsed-time results depend on the recorded execution environments. The repository includes hardware/software environment records and counterbalanced schedules for the timing campaigns. Fresh execution on other hardware is useful as replication evidence but must not be treated as identical to the original timing experiment.


## Publication-figure regeneration boundary

All six final publication PDFs remain frozen in `figures/publication/`; Figure 1 is the source artwork schematic. The **author-derived original plotting builder** now lives at `src/analysis/rebuild_publication_figures.py` with its corrected AWS Fig4 helper at `src/analysis/rebuild_Fig4_AWS_author.py`. Its output in `results/reproduced/publication_figures/` regenerated Figures 2–5 and S1 pixel-identically to the author's PDFs in local verification. PDF metadata/binary identity is not promised on other platforms. No plotting run recreates physical AWS experiments or the missing packet captures.
