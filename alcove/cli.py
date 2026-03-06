"""Alcove CLI — local-first document retrieval."""

from __future__ import annotations

import argparse
import sys

from alcove import __version__


def cmd_serve(args):
    import uvicorn
    from alcove.query.api import app
    uvicorn.run(app, host=args.host, port=args.port)


def cmd_ingest(args):
    import os
    from alcove.ingest.pipeline import run
    if args.chunk_size is not None:
        os.environ["CHUNK_SIZE"] = str(args.chunk_size)
    n = run(raw_dir=args.path)
    print(f"wrote {n} chunks")


def cmd_query(args):
    import json
    from alcove.query.retriever import query_text
    result = query_text(args.query, n_results=args.k)
    print(json.dumps(result, indent=2))


def cmd_plugins(_args):
    from alcove.plugins import list_plugins
    plugins = list_plugins()
    if not plugins:
        print("No plugins installed.")
        print("Install plugins via pip, e.g.: pip install alcove-docx")
        return
    for p in plugins:
        print(f"  {p['type']:10s}  {p['name']:20s}  {p['module']}")


def cmd_seed_demo(_args):
    import subprocess
    from pathlib import Path
    scripts_dir = Path("scripts")
    if not scripts_dir.is_dir():
        print("Error: 'scripts/' directory not found. Run seed-demo from the Alcove repo root.", file=sys.stderr)
        sys.exit(1)
    for s in ["fetch_seed_corpus.py", "ingest_seed_demo.py", "build_seed_index.py"]:
        script_path = scripts_dir / s
        if not script_path.is_file():
            print(f"Error: '{script_path}' not found.", file=sys.stderr)
            sys.exit(1)
        subprocess.check_call([sys.executable, str(script_path)])


def main():
    parser = argparse.ArgumentParser(
        prog="alcove",
        description="Local-first document retrieval. Your data never leaves your disk.",
    )
    parser.add_argument("--version", action="version", version=f"alcove {__version__}")
    sub = parser.add_subparsers(dest="command")

    # serve
    p_serve = sub.add_parser("serve", help="Start web UI and API server")
    p_serve.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1; use 0.0.0.0 to expose on network)")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.set_defaults(func=cmd_serve)

    # ingest
    p_ingest = sub.add_parser("ingest", help="Ingest documents from a directory")
    p_ingest.add_argument("path", nargs="?", default=None, help="Directory with raw documents")
    p_ingest.add_argument("--chunk-size", type=int, default=None, help="Chunk size in characters (default: 1000)")
    p_ingest.set_defaults(func=cmd_ingest)

    # query
    p_query = sub.add_parser("query", help="Search local index")
    p_query.add_argument("query", help="Search terms")
    p_query.add_argument("--k", type=int, default=3)
    p_query.set_defaults(func=cmd_query)

    # seed-demo
    p_seed = sub.add_parser("seed-demo", help="Fetch and index demo corpus")
    p_seed.set_defaults(func=cmd_seed_demo)

    # plugins
    p_plugins = sub.add_parser("plugins", help="List installed plugins")
    p_plugins.set_defaults(func=cmd_plugins)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)
