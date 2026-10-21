# Reproducibility limitations

This repository retains the evidence used for the paper, but two historical upstream inputs are not available in their original form.

## Graph pC coefficient fit

The historical raw per-repair rows used to fit the graph operation-cost coefficients were not retained. The repository does retain the fixed coefficients used by the reported evaluation, frozen configuration, downstream timing rows, and validation records. Consequently, the paper's reported pC evaluation can be inspected and reanalyzed, but the original coefficient-fitting dataset cannot be reconstructed from this release.

## DeathStarBench packet captures

The original packet-capture binaries were not retained. The repository retains packet-capture SHA-256 identifiers, measurement records, derived interaction/state files, sequence manifests, environment information, and the replay inputs used in the reported analysis. The measured replay can therefore be rerun from the retained derived states, but the packet-level preprocessing cannot be reconstructed from the original binaries.

## Timing portability

Elapsed-time results depend on the recorded execution environments. The repository includes hardware/software environment records and counterbalanced schedules for the timing campaigns. Fresh execution on other hardware is useful as replication evidence but must not be treated as identical to the original timing experiment.


## Publication-figure regeneration boundary

The exact six final publication PDFs are retained in `figures/publication/` and were byte-compared with the figure files in the current manuscript package. The included plotting utility regenerates derived summary data and auxiliary diagnostic figures, not the exact final publication PDFs. Use the frozen `figures/publication/` files as the authoritative manuscript artwork; do not substitute diagnostic outputs for them.
