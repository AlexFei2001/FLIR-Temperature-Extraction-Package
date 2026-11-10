# Validation — 2026-11-10

This is a code-packaging and numerical-regression validation, not independent absolute thermometry calibration.

## Checks completed

- 17 standalone automated cases passed; 20 existing multi-format thermal adapter cases passed (37 total, no failures or skips).
- Core decoder functions and calibration-field definitions are copied verbatim from the existing adapter; their source-expression hashes match. See `SOURCE_PROVENANCE.json`.
- Four real FLIR T1020 radiometric JPEGs were processed from a working directory outside the thesis repository, using explicit `swap16`, no measurement overrides and ExifTool 13.61.
- All four exported matrices have shape `(768, 1024)`, float64 Celsius and **exactly equal** the archived preparation matrices: maximum absolute difference = 0.0°C.
- All four full CSV matrices read back exactly equal to their NPY matrices.
- Source-file SHA-256 hashes stayed unchanged. Existing source code and historical outputs were not rewritten.
- Synthetic cases cover Planck inversion, nontrivial environmental correction, missing/invalid metadata, both byte orders, malformed grids, ordinary JPEG rejection, Unicode paths, duplicate names, per-file error continuation, unique output directories, CSV round trips, output hashes and input changes during reading.

## Tested environment

Python 3.10.20 on Windows; NumPy 2.2.6; Pillow 12.2.0; ExifTool 13.61. Other operating systems and camera/file types were not tested on real data in this release.

## Limits

Exact agreement verifies preservation of the existing implementation; it does not prove that the original metadata describes the scene correctly or that absolute temperatures match an independently calibrated instrument. Vendor-software spot checks at matching coordinates/settings remain pending. `swap16` is not a universal setting for every FLIR file. New camera/file formats require separate validation. No raw photographs, saved temperature matrices, external binaries or machine-specific config files are in the shared archive.

Machine-readable check results: `validation_report.json`.

Version 1.0.1 updates publication materials, language guides and the package version. Its core numerical function expressions are unchanged from 1.0.0. The four-file numerical comparison above was performed for 1.0.0; the standalone suite is rerun for the 1.0.1 distribution. These scopes are recorded separately in `validation_report.json`.
