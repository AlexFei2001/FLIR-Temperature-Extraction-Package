# Changelog

## 1.0.1 — 2026-11-10

- Published the standalone tool in its own GitHub repository.
- Expanded the English README and added a full Italian README, with navigation between English, Italian and Chinese.
- Included the repository's existing MIT license, a standalone `.gitignore`, and a ready-to-share ZIP with a SHA-256 checksum.
- Preserved the numerical FLIR decoder and temperature-conversion expressions from 1.0.0 without changes.

## 1.0.0 — 2026-11-10

- Extracted the existing FLIR decoder into an independent tool package.
- Added single-file/folder batch input, explicit byte-order selection, native Celsius NPY and optional CSV export, provenance records and an interactive Windows launcher.
- Validated 17 standalone test cases, 20 existing-adapter regression cases and four real FLIR T1020 matrices against the archived outputs.
