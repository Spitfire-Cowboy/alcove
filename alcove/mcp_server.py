"""Model Context Protocol server for local Alcove indexes.

This module implements a small STDIO JSON-RPC 2.0 MCP server without requiring
an external MCP framework. It exposes retrieval tools only: Alcove returns
matching document chunks from the local index and does not generate answers.
"""
from __future__ import annotations

import json
import sys


SERVER_INFO = {
    "name": "alcove",
    "version": "0.1.0",
}

CAPABILITIES = {
    "tools": {},
}

SEARCH_TOOL_NAME = "search"
SEARCH_ALIAS_TOOL_NAME = "search_alcove_knowledge_sources"


def _search_tool_definition(name: str) -> dict:
    return {
        "name": name,
        "description": (
            "Search a local Alcove index. Returns matching document chunks "
            "for a natural-language query."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural-language search query",
                },
                "collection": {
                    "type": "string",
                    "description": "Collection name to search, if using named collections",
                },
                "n_results": {
                    "type": "integer",
                    "description": "Number of results to return",
                    "default": 5,
                },
                "top_k": {
                    "type": "integer",
                    "description": "Alias for n_results; takes precedence when set",
                },
                "language_filter": {
                    "type": "string",
                    "description": "Language code filter matched against result metadata",
                },
                "_meta": {
                    "type": "object",
                    "description": "Optional retrieval controls",
                    "properties": {
                        "source_ids_include": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "source_group_ids_include": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
            },
            "required": ["query"],
        },
    }


TOOLS: list[dict] = [
    _search_tool_definition(SEARCH_TOOL_NAME),
    _search_tool_definition(SEARCH_ALIAS_TOOL_NAME),
    {
        "name": "list_collections",
        "description": "List available Alcove collection names.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def _do_search(
    query: str,
    collection: str | None = None,
    n_results: int = 5,
    language_filter: str | None = None,
    source_ids_include: list[str] | None = None,
    source_group_ids_include: list[str] | None = None,
) -> list[dict]:
    from alcove.query.retriever import query_text

    collections = [collection] if collection else None
    raw = query_text(query, n_results=n_results, collections=collections)
    documents = raw.get("documents", [[]])[0]
    metadatas = raw.get("metadatas", [[]])[0]
    distances = raw.get("distances", [[]])[0]

    source_ids = set(source_ids_include or [])
    source_group_ids = set(source_group_ids_include or [])
    language = (language_filter or "").strip()

    results = []
    for doc, meta, dist in zip(documents, metadatas, distances, strict=True):
        meta = meta if isinstance(meta, dict) else {}
        source = str(meta.get("source", ""))
        source_id = str(meta.get("source_id") or source)
        source_group_id = str(meta.get("source_group_id") or meta.get("source_group") or "")
        result_language = str(meta.get("language", ""))

        if language and result_language != language:
            continue
        if source_ids and source_id not in source_ids:
            continue
        if source_group_ids and source_group_id not in source_group_ids:
            continue

        score = max(0.0, min(1.0, 1.0 - float(dist)))
        results.append({
            "text": doc,
            "source": source,
            "source_id": source_id,
            "source_group_id": source_group_id,
            "language": result_language,
            "score": round(score, 3),
        })
    return results


def _do_list_collections() -> list[str]:
    from alcove.index.backend import get_backend
    from alcove.index.embedder import get_embedder

    backend = get_backend(get_embedder())
    collections = backend.list_collections()
    names: list[str] = []
    for item in collections:
        if isinstance(item, dict):
            name = item.get("name")
            if name:
                names.append(str(name))
        else:
            names.append(str(item))
    return names


def _ok(id_: object, result: object) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _err(id_: object, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def _parse_positive_int(value: object, field_name: str, default: int = 5) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return parsed


def _parse_include_filters(meta: object) -> tuple[list[str] | None, list[str] | None]:
    if meta is None:
        return None, None
    if not isinstance(meta, dict):
        raise ValueError("_meta must be an object")

    def _parse_string_list(value: object, field_name: str) -> list[str] | None:
        if value is None:
            return None
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError(f"_meta.{field_name} must be an array of strings")
        return value

    return (
        _parse_string_list(meta.get("source_ids_include"), "source_ids_include"),
        _parse_string_list(meta.get("source_group_ids_include"), "source_group_ids_include"),
    )


def handle_request(req: dict) -> dict | None:
    method = req.get("method", "")
    id_ = req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        return _ok(id_, {
            "protocolVersion": "2024-11-05",
            "capabilities": CAPABILITIES,
            "serverInfo": SERVER_INFO,
        })

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return _ok(id_, {"tools": TOOLS})

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}

        if tool_name in {SEARCH_TOOL_NAME, SEARCH_ALIAS_TOOL_NAME}:
            query = arguments.get("query")
            if not query:
                return _err(id_, -32602, "Missing required argument: query")
            try:
                top_k = arguments.get("top_k")
                n_results = _parse_positive_int(
                    top_k if top_k is not None else arguments.get("n_results", 5),
                    "top_k" if top_k is not None else "n_results",
                )
                source_ids_include, source_group_ids_include = _parse_include_filters(
                    arguments.get("_meta")
                )
                results = _do_search(
                    query=query,
                    collection=arguments.get("collection"),
                    n_results=n_results,
                    language_filter=arguments.get("language_filter"),
                    source_ids_include=source_ids_include,
                    source_group_ids_include=source_group_ids_include,
                )
            except ValueError as exc:
                return _err(id_, -32602, str(exc))
            except Exception as exc:
                return _err(id_, -32603, f"Search failed: {exc}")
            return _ok(id_, {
                "content": [{"type": "text", "text": json.dumps(results, indent=2)}],
            })

        if tool_name == "list_collections":
            try:
                collections = _do_list_collections()
            except Exception as exc:
                return _err(id_, -32603, f"list_collections failed: {exc}")
            return _ok(id_, {
                "content": [{"type": "text", "text": json.dumps(collections)}],
            })

        return _err(id_, -32601, f"Unknown tool: {tool_name!r}")

    return _err(id_, -32601, f"Unknown method: {method!r}")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req)
        except json.JSONDecodeError as exc:
            resp = _err(None, -32700, f"Parse error: {exc}")
        except Exception as exc:
            resp = _err(None, -32603, f"Internal error: {exc}")

        if resp is not None:
            print(json.dumps(resp), flush=True)


if __name__ == "__main__":
    main()
