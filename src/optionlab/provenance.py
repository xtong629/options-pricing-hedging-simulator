"""Resolve revision only for a source checkout of this package."""

import subprocess
from pathlib import Path


def source_revision() -> str | None:
    root = Path(__file__).resolve().parents[2]
    if not (root / ".git").exists() or not (root / "src/optionlab").is_dir():
        return None
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
