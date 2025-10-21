#!/usr/bin/env python3
"""
Main setup script - orchestrates all setup tasks
Run with: python scripts/setup.py
"""
import subprocess
import sys
from pathlib import Path


def main():
    scripts_dir = Path(__file__).parent

    try:
        # Step 1: Create groups
        print("=" * 50)
        print("Step 1: Creating groups")
        print("=" * 50)
        subprocess.run([sys.executable, scripts_dir / "upload_groups.py"], check=True)

        # Step 2: Upload problems
        print("\n" + "=" * 50)
        print("Step 2: Uploading problems")
        print("=" * 50)
        subprocess.run([sys.executable, scripts_dir / "upload_problems.py"], check=True)

        print("\n" + "=" * 50)
        print("Setup complete!")
        print("=" * 50)

    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Setup failed at step {e.cmd}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
