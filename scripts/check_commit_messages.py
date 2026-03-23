#!/usr/bin/env python3
"""Fail CI when blocked co-author trailers appear in commit messages."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys


BLOCKED_TRAILER_PATTERNS = [
    re.compile(r"^\s*co-authored-by\s*:\s*.+$", re.IGNORECASE),
]


def _git_log(rev_range: str) -> list[tuple[str, str]]:
    cmd = ["git", "log", "--format=%H%x00%B%x00", rev_range]
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    raw = proc.stdout
    if not raw:
        return []

    parts = raw.split("\x00")
    if parts and parts[-1] == "":
        parts.pop()

    commits: list[tuple[str, str]] = []
    for idx in range(0, len(parts), 2):
        if idx + 1 >= len(parts):
            break
        commits.append((parts[idx], parts[idx + 1]))
    return commits


def _find_matches(message: str) -> list[str]:
    matches: list[str] = []
    for line in message.splitlines():
        if any(pattern.match(line) for pattern in BLOCKED_TRAILER_PATTERNS):
            matches.append(line.strip())
    return matches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("rev_range", help="Git rev-range, e.g. base..head")
    args = parser.parse_args()

    violations: list[tuple[str, list[str]]] = []
    for sha, message in _git_log(args.rev_range):
        matched_lines = _find_matches(message)
        if matched_lines:
            violations.append((sha, matched_lines))

    if not violations:
        print("Commit message policy check passed.")
        return 0

    print("Blocked: found disallowed co-author trailers in commit messages:")
    for sha, lines in violations:
        print(f"- {sha}")
        for line in lines:
            print(f"  {line}")
    print(
        "\nRemove Co-authored-by trailers from commit messages before merging."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
