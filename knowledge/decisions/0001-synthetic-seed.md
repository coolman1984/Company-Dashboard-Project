---
title: ADR 0001 - Synthetic Seed Database
tags: [decision, adr]
---

# ADR 0001 — Synthetic Seed Database

**Status:** accepted. #decision

**Context:** the production database could only be built on Windows from a
proprietary Excel workbook, so the project could not run, test, or be built on
anywhere else.

**Decision:** add a deterministic synthetic seed (`seed_db.py`) so the dashboard,
[[reports]], and the [[data-pipeline]] run on any machine and in CI.

**Consequences:** development is decoupled from client data; conventions are kept
in [[conventions]] and the seed honours them.
