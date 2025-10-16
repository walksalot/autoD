#!/usr/bin/env python3
"""
Paper Autopilot daemon entry point.

Automatically processes PDFs as they arrive from scanner.

Usage:
    export OPENAI_API_KEY=sk-...
    export PAPER_AUTOPILOT_INBOX_PATH=inbox  # Optional, defaults to "inbox"
    python run_daemon.py

For macOS LaunchAgent:
    Copy com.paperautopilot.daemon.plist to ~/Library/LaunchAgents/
    launchctl load ~/Library/LaunchAgents/com.paperautopilot.daemon.plist

For Linux systemd:
    sudo systemctl start paper-autopilot
    sudo systemctl status paper-autopilot
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src/ to Python path if running directly
if __name__ == "__main__":
    src_path = Path(__file__).parent.resolve()
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

from src.daemon import main

if __name__ == "__main__":
    main()
