---
title: Data Conventions
tags: [reference]
---

# Data Conventions

How the ledger encodes time and forecast versions. #reference

- **Period** is stored as `year + period_number / 1000` (e.g. `2026.001` = P01,
  `2026.012` = P12).
- **Versions:** `Actual` (realised), `T06` (bridge period P06), `T07` (outlook
  periods P07–P12).
- **Outlook year** = Actual P01–P05 + T06 P06 + T07 P07–P12.

See [[glossary]] for line definitions and [[data-pipeline]] for how data arrives.
