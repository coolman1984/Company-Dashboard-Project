---
title: Data Pipeline
tags: [process]
---

# Data Pipeline

How a client's mess becomes insight. #process

1. **Extract** messy files (Excel, PDF, Word, Outlook) into faithful raw JSON
   (`extractor/`).
2. **Map** raw JSON into the canonical `pl_detail` database
   (`map_raw_to_db.py`).
3. **Analyse** via the live dashboard, [[reports]], and what-if scenarios.

Terms are in [[glossary]]; timing conventions in [[conventions]]; key decisions
are recorded as ADRs such as [[0001-synthetic-seed]].
