#!/usr/bin/env python3
"""
Fail fast when diffs reintroduce deprecated model identifiers.

Usage:
    python scripts/check_model_policy.py
    python scripts/check_model_policy.py --diff
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from config.models import (
    DEPRECATED_MODEL_IDS,
    MODEL_POLICY_VERSION,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXTENSIONS = {".py", ".md", ".json", ".yaml", ".yml", ".toml"}
IGNORE_DIRS = {".git", ".venv", "__pycache__", "inbox"}


def gather_files_from_diff() -> Iterable[Path]:
    """Return changed files in the current git diff (staged + unstaged)."""
    try:
        diff_output = subprocess.check_output(
            ["git", "diff", "--name-only"], cwd=REPO_ROOT, text=True
        )
        staged_output = subprocess.check_output(
            ["git", "diff", "--name-only", "--cached"], cwd=REPO_ROOT, text=True
        )
    except subprocess.CalledProcessError as exc:
        print(f"Failed to inspect git diff: {exc}", file=sys.stderr)
        sys.exit(2)

    files = set()
    for line in diff_output.splitlines() + staged_output.splitlines():
        path = (REPO_ROOT / line.strip()).resolve()
        if path.is_file():
            files.add(path)
    return sorted(files)


def gather_repo_files() -> Iterable[Path]:
    """Scan the repository for candidate files."""
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        if path.suffix and path.suffix not in DEFAULT_EXTENSIONS:
            continue
        yield path


def scan_files(files: Iterable[Path]) -> int:
    """Return the number of violations found."""
    violations = 0
    banned = set(DEPRECATED_MODEL_IDS)

    for file_path in files:
        # Allow policy doc to mention banned identifiers explicitly.
        if file_path == REPO_ROOT / "docs" / "model_policy.md":
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for model in banned:
            if model in content:
                print(f"[ERROR] {model} detected in {file_path.relative_to(REPO_ROOT)}")
                violations += 1

    return violations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Only check files touched in the current git diff (staged + unstaged).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    files = list(gather_files_from_diff() if args.diff else gather_repo_files())
    if not files:
        print("No files to scan.")
        return 0

    violations = scan_files(files)
    if violations:
        print(
            f"Model policy check failed with {violations} violation(s). "
            f"See docs/model_policy.md (v{MODEL_POLICY_VERSION})."
        )
        return 1

    print(
        f"Model policy check passed ({len(files)} file(s) scanned, policy v{MODEL_POLICY_VERSION})."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
