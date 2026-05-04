#!/bin/bash
# Job Search Agent — Smart Launcher
set -e
cd "$(dirname "$0")"

PYTHON=""
for p in python3.11 /opt/homebrew/bin/python3.11 python3 python; do
    if command -v "$p" &>/dev/null; then PYTHON="$p"; break; fi
done
[ -z "$PYTHON" ] && { echo "Python not found. Install: brew install python@3.11"; exit 1; }

# First-time setup check
if [ ! -f ".env" ]; then
    echo "First run detected — launching setup wizard..."
    "$PYTHON" setup.py
fi

# Validate profile is configured
NAME=$("$PYTHON" -c "import json,os; p=json.load(open('config/profile.json')); print(p.get('name',''))" 2>/dev/null || echo "")
if [ -z "$NAME" ] || [ "$NAME" = "Your Full Name" ]; then
    echo "Profile not configured — launching setup wizard..."
    "$PYTHON" setup.py
fi

# Smart start: check hours since last run
HOURS=$("$PYTHON" -c "
import sqlite3, os
from datetime import datetime, timezone
from pathlib import Path
db = Path('data/jobs.db')
if not db.exists():
    print(999)
else:
    try:
        con = sqlite3.connect(str(db))
        row = con.execute('SELECT run_date FROM runs ORDER BY run_id DESC LIMIT 1').fetchone()
        if not row:
            print(999)
        else:
            from dateutil import parser as dp
            last = dp.parse(row[0])
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            diff = (datetime.now(timezone.utc) - last).total_seconds() / 3600
            print(int(diff))
        con.close()
    except:
        print(999)
" 2>/dev/null || echo "999")

echo "Configured for: $NAME"
if [ "$HOURS" -gt 8 ] 2>/dev/null; then
    echo "Running full pipeline (--find)..."
    "$PYTHON" main.py --find
else
    echo "Recent run found — opening UI..."
    "$PYTHON" main.py --ui
fi
