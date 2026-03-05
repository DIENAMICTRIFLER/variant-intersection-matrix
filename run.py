#!/usr/bin/env python3
"""
Variant Intersection Matrix Analyzer — Entry Point
====================================================

Usage:
    python run.py              # Launch Streamlit app
    python run.py --help       # Show help
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Launch the Streamlit application."""
    app_path = Path(__file__).parent / "interface" / "app.py"

    if not app_path.exists():
        print(f"Error: Application file not found at {app_path}")
        sys.exit(1)

    print("🚀 Launching Variant Intersection Matrix Analyzer...")
    print(f"   App: {app_path}")
    print()

    subprocess.run(
        [
            sys.executable, "-m", "streamlit", "run",
            str(app_path),
            "--server.maxUploadSize=200",
            "--theme.primaryColor=#1a237e",
            "--theme.backgroundColor=#ffffff",
            "--theme.secondaryBackgroundColor=#f8f9fa",
            "--theme.textColor=#212121",
        ],
        cwd=str(Path(__file__).parent),
    )


if __name__ == "__main__":
    main()
