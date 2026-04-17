#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def shared_script() -> Path:
    here = Path(__file__).resolve()
    installed = here.parents[2] / "user" / "bin" / "drift.py"
    if installed.exists() and installed != here:
        return installed
    return here.parents[3] / "shared" / "user" / "bin" / "drift.py"


def main() -> int:
    result = subprocess.run(
        [sys.executable, str(shared_script()), "--adapter", "copilot-cli", *sys.argv[1:]],
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
