# Getting Started — the simple guide

This guide is for **non-technical users**. It explains, in plain steps, how to
open the dashboard on your own computer. No programming needed.

---

## What you're setting up

The dashboard is a **website that runs on your own PC** (nobody else sees it).
It needs two things to work:

1. **A program to run it** — already included (you don't install anything).
2. **A file of numbers to show** — you create this once, in a few seconds.

That's it. Two one-time steps, then you just double-click to open it.

> **No internet required.** Everything the dashboard needs is already in the
> folder — charts, fonts, everything. It works fully offline.

---

## First time only: two steps

### Step 1 — Create the practice numbers

The dashboard ships **without** any data (your real figures stay private). To
see it working, create a set of **realistic practice numbers** first.

1. Make sure **Python** is installed (a free, safe tool). If you're not sure,
   download it once from <https://www.python.org/downloads/> and, during
   install, tick the box that says **"Add Python to PATH"**.
2. In the project folder, **double-click `Create Sample Data.bat`**.
3. A black window appears, works for a few seconds, and says **"Done."**
   You can close it.

You now have a file called `pl_detail.db` — that's the data. ✅

> Later, when you want your **real** company numbers instead of practice ones,
> just ask and we'll set that up. Nothing else changes.

### Step 2 — Open the dashboard

1. **Double-click `Start Dashboard.bat`**.
2. Wait a few seconds. Your web browser opens automatically at the dashboard.

That's it. 🎉

---

## Every time after that

Just **double-click `Start Dashboard.bat`**. That's the only step.

To close it, double-click **`Stop Dashboard.bat`**.

---

## What you'll see

A finance dashboard with sections down the left side:

- **Executive Overview** — the headline numbers and this year's outlook.
- **Regional / Product / Customer** — performance broken down different ways.
- **Trends** — five years of history.
- **Portfolio** — which products to grow vs. fix.

Each table has an **Export CSV** button to open the data in Excel.

---

## If something looks wrong

- **A yellow message bar saying "We couldn't load the data."**
  The numbers aren't set up yet. Do **Step 1** above (Create Sample Data),
  then click **Try again**.

- **The browser didn't open by itself.**
  Open your browser and type this in the address bar: `http://localhost:3001`

- **"Python is not installed."**
  Install it once from <https://www.python.org/downloads/> (tick
  "Add Python to PATH"), then double-click `Create Sample Data.bat` again.

---

## For a technical helper

If a developer is assisting you, they can run everything from a terminal:

```bash
npm install                 # one-time
pip install -r extractor/requirements.txt -r reports/requirements.txt  # one-time
python3 seed_db.py --force  # create the practice database
npm start                    # open http://localhost:3001 (localhost only)
npm test                     # run the automated checks
```

Shared/remote access (for demos or team use):

```bash
HOST=0.0.0.0 ACCESS_TOKEN=your-shared-secret npm start
```

See `README.md` for the full technical details.
