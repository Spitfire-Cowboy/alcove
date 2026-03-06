from __future__ import annotations

import argparse
import json

from .retriever import query_text


def main():
    parser = argparse.ArgumentParser(description="Query the local Alcove index")
    parser.add_argument("query", nargs="?", default="", help="question or search phrase")
    parser.add_argument("--k", type=int, default=3)
    args = parser.parse_args()

    if not args.query.strip():
        parser.error('Usage: make query Q="your question here"')

    res = query_text(args.query, n_results=args.k)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
