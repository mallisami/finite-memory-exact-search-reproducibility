# Independently checked author-release bytes (7 November 2026)

The source is `PCR2_PAPER2_FIGURES_TABLES_CORRECTED_FINAL_20261107.zip` (SHA-256 `5e826e0112e5b17cba5703fa5e8df3abbbbd06aa7ff98ae2744e76d4e384fc01`). Its full `05_Reproduce/FILE_INDEX.csv` inventory has **7,972 of 7,972 matching checksums**, verified against all ZIP members.

`AUTHOR_RELEASE_EXACT_SOURCE_CROSSWALK_20261107.csv` checks 16 **selected authoritative** files by their exact Git blob SHA-1 and byte size. The current P8 author headline was explicitly synchronized on 7 November after a mismatch with a pre-AWS summary was detected. These selected matches span P6/P7, corrected AWS P8, nested P9, P10 original/same-case repeat, P0, RQ3 VM90, and five final figure PDFs.

The matrix is **not** a claim that all 7,972 author-archive scientific files are included in public GitHub. Original machine-specific raw captures and historical provenance remain a documented release boundary. Figure 1 was intentionally sanitized at PDF metadata level and is excluded from these exact-byte tests; its rendered appearance is separately documented as unchanged.

`tests/test_author_source_crosswalk.py` runs on every CI push and prevents silent source regression.
