# Project Vision & Roadmap

> The big picture, in plain language. This is the north star for the whole
> project — far bigger than the dashboard alone. We build it in **stages**, and
> **each stage is useful on its own**, so value arrives early and often.

---

## The vision in one sentence

Walk into a company with messy files, turn that mess into clean data, and give
management a living picture of their business — plus a "second brain" that
remembers everything and an AI assistant that runs and improves the work.

---

## How the whole machine fits together

Think of it as an assembly line. Data comes in messy on the left and comes out
as insight, knowledge, and automation on the right:

```
 Messy files            Clean data            Understanding          Brains
 -----------            -----------           --------------         --------
 Excel  ┐                                      Reports  ┐
 PDF    ┼─►  EXTRACT  ─►  DATABASE  ─►  CALCULATE  ─►  Dashboard ┼─►  Wiki ("2nd brain")
 Word   ┘   (+ save raw     (fast,      & QUERY        Scenarios ┘        │
            as JSON)        queryable)                                    ▼
                                                                   AI Agent ("Hermes")
                                                                   runs & improves it all
```

---

## The stages

### ✅ Stage 0 — The dashboard foundation (DONE)
The management webapp: charts, tables, trends, outlook, CSV export — and a solid,
runnable core that works on any computer with practice data.
**You have this today.**

### Stage 1 — Take in real data (the extraction engine) ⭐ the keystone — *foundation built*

> **Status:** the engine foundation exists in `extractor/` — it captures Excel
> and Word into faithful raw JSON today (tested), with COM-first Excel for
> Windows and PDF/Outlook extractors written and ready to switch on. Captured
> **spreadsheet** raw JSON can now reach the dashboard database via
> `map_raw_to_db.py` and a reviewed per-client mapping (`mapping.example.json`).
> Still to do: the scanned-PDF OCR path, live-Outlook COM, and mappings for
> non-spreadsheet sources. See `extractor/README.md`.

A drop-folder where you put a client's **Excel, PDF, and Word** files. The system
reads them, pulls out the real numbers, and loads them into the fast database.
Every original is also saved **exactly as-is in JSON** so nothing is ever lost.
- **Why it matters:** this is what lets you actually *go to a client* and turn
  their mess into the dashboard. Everything downstream becomes real.
- **Honesty about difficulty:** Excel is the easiest. PDFs and Word vary wildly —
  clean digital PDFs are doable; **scanned/photographed documents** need
  text-recognition (OCR) and AI, and usually a quick **"check what was
  extracted"** step before trusting it. We start with the easy wins and grow.

### Stage 2 — The reports engine — *first version built*
Define report templates once, then generate them from the database on demand.
Each report is also saved as JSON (your "target" format) and shown in the webapp
or exported to Excel/PDF.

> **Status:** `reports/` generates six core P&L reports from the database as
> self-describing JSON, CSV, **management-ready Excel (.xlsx)**, and
> **PDF** — see `reports/README.md`. Next: client-specific report templates,
> richer/forecast reports, and a bundled "board pack".

### Stage 3 — Scenarios & forecasting
"What-if" modelling and forward forecasts — change an assumption and watch the
outlook update. (The dashboard's outlook tab is an early piece of this.)

### Stage 4 — The "second brain" (Obsidian-style wiki)
A linked knowledge base of the company: how things work, definitions, decisions,
meeting notes — connected to the live data so knowledge and numbers live together.

### Stage 5 — The AI agent ("Hermes")
An assistant that learns the company's workflows, does the repetitive work,
automates steps, and suggests better ways of working.
- **Why it's last:** an agent needs the data, reports, and knowledge base
  (Stages 1–4) to already exist before it has anything to act on.

---

## Big decisions to keep in mind (not all today)

- **Where it runs & privacy.** Client financial data is sensitive. We decide
  whether this runs **on your own/their computer (most private)** or in the
  **cloud (easier to share)**. This shapes everything, so we settle it early.
- **One client or many.** A tool for one client at a time is much simpler than a
  product that serves many companies at once. We can start with one and grow.
- **Human-in-the-loop.** Especially for messy PDFs, a person confirming the
  extracted numbers keeps trust high. The AI does 90%; a quick review catches the
  rest.

---

## Recommended order

1. **Stage 1 first** — it unlocks real client work and feeds everything else.
2. Then **Stage 2 (reports)** and **Stage 3 (scenarios)** to deepen the value.
3. Then **Stage 4 (knowledge base)**.
4. Then **Stage 5 (the AI agent)**, once there's a real system for it to run.

Each stage ships something you can use and show — no waiting months for a "big
reveal."
