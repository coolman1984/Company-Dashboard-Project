#!/usr/bin/env bash
#
# setup.sh — one command to get the Company Dashboard running on a fresh machine.
#
# It installs everything the dashboard needs, installs the OPTIONAL report
# dependencies (Excel/PDF export), builds a synthetic database if none exists,
# and prints a clear readiness report — including which export formats are
# available — so a non-developer can tell at a glance whether the product is
# ready. CSV export and the live dashboard work even if the optional report
# dependencies fail to install.
#
# Usage:
#   ./setup.sh              # install + seed (English synthetic data)
#   ./setup.sh --locale ar  # seed Arabic synthetic data instead
#   ./setup.sh --force      # rebuild the database even if one exists
#
set -u
cd "$(dirname "$0")"

LOCALE="en"
FORCE_SEED="0"
while [ $# -gt 0 ]; do
    case "$1" in
        --locale) LOCALE="${2:-en}"; shift 2 ;;
        --force)  FORCE_SEED="1"; shift ;;
        *) echo "Unknown option: $1"; exit 2 ;;
    esac
done

ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }
err()  { printf '  \033[31m✗\033[0m %s\n' "$1"; }
step() { printf '\n\033[1m%s\033[0m\n' "$1"; }

MISSING_CORE=0

step "1. Checking prerequisites"
if command -v node >/dev/null 2>&1; then
    ok "Node.js $(node --version)"
else
    err "Node.js is not installed — get it from https://nodejs.org (LTS)."
    MISSING_CORE=1
fi
if command -v python3 >/dev/null 2>&1; then
    ok "Python $(python3 --version 2>&1 | awk '{print $2}')"
else
    err "Python 3 is not installed — get it from https://python.org."
    MISSING_CORE=1
fi
if [ "$MISSING_CORE" = "1" ]; then
    err "Install the missing prerequisite(s) above, then re-run ./setup.sh"
    exit 1
fi

step "2. Installing dashboard dependencies (npm)"
if npm install --no-audit --no-fund; then
    ok "Node dependencies installed"
else
    err "npm install failed — the dashboard cannot run without it."
    exit 1
fi

step "3. Installing optional report-export dependencies (pip)"
# These power Excel/PDF export and the Arabic board pack. They are optional:
# the dashboard and CSV export work without them, and the UI hides any export
# button it cannot fulfil.
if python3 -m pip install -q -r reports/requirements.txt; then
    ok "Report-export dependencies installed (Excel/PDF available)"
else
    warn "Could not install report-export dependencies."
    warn "The dashboard and CSV export still work; Excel/PDF buttons will be disabled."
    warn "Retry later with: python3 -m pip install -r reports/requirements.txt"
fi

step "4. Building a database"
if [ -f pl_detail.db ] && [ "$FORCE_SEED" = "0" ]; then
    ok "pl_detail.db already exists (use --force to rebuild)"
else
    if python3 seed_db.py --force --locale "$LOCALE"; then
        ok "Synthetic database built (locale: $LOCALE)"
    else
        err "Failed to build the synthetic database."
        exit 1
    fi
fi

step "5. Readiness report"
node --check server.js >/dev/null 2>&1 && ok "Server passes syntax check" || err "Server failed syntax check"
CAPS="$(python3 -m reports.cli --capabilities 2>/dev/null)"
case "$CAPS" in
    *'"xlsx": true'*) ok "Excel (.xlsx) export: available" ;;
    *)                warn "Excel (.xlsx) export: unavailable (pip install openpyxl)" ;;
esac
case "$CAPS" in
    *'"pdf": true'*)  ok "PDF export: available" ;;
    *)                warn "PDF export: unavailable (pip install reportlab)" ;;
esac
ok "CSV export: always available"

step "Done — start the dashboard with:"
printf '  npm start      # then open http://localhost:3001\n\n'
