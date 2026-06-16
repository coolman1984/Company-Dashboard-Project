# CLAUDE.md

**STOP — this project is worked on by multiple AI agents (Claude, OpenAI Codex,
DeepSeek). The mandatory shared protocol lives in [`AGENTS.md`](AGENTS.md).**

Before doing anything:
1. Read [`AGENTS.md`](AGENTS.md) in full — start with its **§0 Quick start
   (exactly what to do)** — then [`ARCHITECTURE.md`](ARCHITECTURE.md) (the layer
   map + where new code goes) and [`ROADMAP.md`](ROADMAP.md).
2. Claim your task on the Task Board in `AGENTS.md`.
3. When you finish, add an entry to the top of the Work Journal in `AGENTS.md`.
   **A task is not done until the journal is updated.**

`Agent.md` holds technical lessons learned (COM gotchas, performance patterns) —
useful, but `AGENTS.md` is the rules. To explore the system safely, the
read-only MCP server (`mcp_server/`) exposes DB / extraction / wiki tools. Do
not commit `intake/` or `raw/` data.
