#!/usr/bin/env python3
"""Remove blocked co-author trailers from a commit message file."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


BLOCKED_TRAILER = re.compile(r"^\s*co-authored-by\s*:\s*.+$", re.IGNORECASE)


def sanitize(text: str) -> tuple[str, bool]:
    kept_lines = [line for line in text.splitlines() if not BLOCKED_TRAILER.match(line)]
    cleaned = "\n".join(kept_lines).rstrip() + "\n"
    changed = cleaned != text
    return cleaned, changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("message_file")
    args = parser.parse_args()

    path = Path(args.message_file)
    original = path.read_text(encoding="utf-8")
    cleaned, changed = sanitize(original)
    if changed:
        path.write_text(cleaned, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
