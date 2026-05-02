#!/bin/bash
# Job Search Agent — macOS/Linux Launcher

echo "🚀 Starting Job Search Agent..."
cd "$(dirname "$0")"

# Check if setup has been done
if [ ! -f ".env" ]; then
    echo "First time? Running setup wizard..."
    python3 setup.py
    if [ $? -ne 0 ]; then
        echo "Setup failed. Exiting."
        exit 1
    fi
fi

# Run the agent
python3 main.py --find
