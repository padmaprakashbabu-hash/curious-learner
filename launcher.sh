#!/bin/bash
# Job Search Agent — Smart Launcher
# Runs --find if last run was >8 hours ago, else just opens the UI
set -e
cd "$(dirname "$0")"

# Find python3.11
PYTHON=""
for candidate in python3.11 /opt/homebrew/bin/python3.11 /usr/local/bin/python3.11 python3 python; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    osascript -e 'display alert "Python not found" message "Please install Python 3.11 via Homebrew:\nbrew install python@3.11"'
    exit 1
fi

# First-time setup check
if [ ! -f ".env" ]; then
    echo "First run detected — launching setup wizard..."
    "$PYTHON" setup.py
fi

# Smart start: check hours since last run
HOURS_SINCE=$("$PYTHON" -c "
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

echo "Hours since last run: $HOURS_SINCE"

if [ "$HOURS_SINCE" -gt 8 ] 2>/dev/null; then
    echo "Running full pipeline (--find)..."
    "$PYTHON" main.py --find
else
    echo "Recent run found — opening UI only (--ui)..."
    "$PYTHON" main.py --ui
fi
