from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from alcove.mcp_server import SEARCH_ALIAS_TOOL_NAME, _do_search, handle_request


def test_initialize_returns_server_info():
    req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}

    resp = handle_request(req)

    assert resp is not None
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"] == "alcove"
    assert "protocolVersion" in resp["result"]


def test_initialized_notification_returns_no_response():
    req = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}

    assert handle_request(req) is None


def test_tools_list_returns_search_and_collection_tools():
    req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}

    resp = handle_request(req)

    assert resp is not None
    tool_names = {tool["name"] for tool in resp["result"]["tools"]}
    assert "search" in tool_names
    assert SEARCH_ALIAS_TOOL_NAME in tool_names
    assert "list_collections" in tool_names


def test_tools_list_search_schema_has_expected_inputs():
    req = {"jsonrpc": "2.0", "id": 3, "method": "tools/list"}

    resp = handle_request(req)

    assert resp is not None
    search_tool = next(tool for tool in resp["result"]["tools"] if tool["name"] == "search")
    properties = search_tool["inputSchema"]["properties"]
    assert "query" in properties
    assert "query" in search_tool["inputSchema"]["required"]
    assert "top_k" in properties
    assert "_meta" in properties


def test_search_tool_calls_search_adapter():
    with patch("alcove.mcp_server._do_search") as mock_search:
        mock_search.return_value = [
            {
                "text": "Test document chunk",
                "source": "data/raw/test.txt",
                "language": "en",
                "score": 0.85,
            }
        ]
        req = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "search",
                "arguments": {"query": "local history", "n_results": 3},
            },
        }
        resp = handle_request(req)

    assert resp is not None
    content = resp["result"]["content"]
    results = json.loads(content[0]["text"])
    assert results[0]["score"] == 0.85
    mock_search.assert_called_once_with(
        query="local history",
        collection=None,
        n_results=3,
        language_filter=None,
        source_ids_include=None,
        source_group_ids_include=None,
    )


def test_search_tool_missing_query_returns_invalid_params():
    req = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {"name": "search", "arguments": {}},
    }

    resp = handle_request(req)

    assert resp is not None
    assert resp["error"]["code"] == -32602


def test_search_alias_tool_routes_to_search_with_controls():
    with patch("alcove.mcp_server._do_search", return_value=[]) as mock_search:
        req = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": SEARCH_ALIAS_TOOL_NAME,
                "arguments": {
                    "query": "schools",
                    "collection": "archive",
                    "top_k": 2,
                    "language_filter": "en",
                    "_meta": {
                        "source_ids_include": ["source-1"],
                        "source_group_ids_include": ["group-a"],
                    },
                },
            },
        }
        resp = handle_request(req)

    assert resp is not None
    assert "result" in resp
    mock_search.assert_called_once_with(
        query="schools",
        collection="archive",
        n_results=2,
        language_filter="en",
        source_ids_include=["source-1"],
        source_group_ids_include=["group-a"],
    )


def test_search_tool_invalid_top_k_returns_invalid_params():
    req = {
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {
            "name": SEARCH_ALIAS_TOOL_NAME,
            "arguments": {"query": "anything", "top_k": "two"},
        },
    }

    resp = handle_request(req)

    assert resp is not None
    assert resp["error"]["code"] == -32602


@pytest.mark.parametrize(
    "meta_value",
    [
        [],
        {"source_ids_include": "not-a-list"},
        {"source_group_ids_include": [1, 2]},
    ],
)
def test_search_tool_invalid_meta_returns_invalid_params(meta_value):
    req = {
        "jsonrpc": "2.0",
        "id": 12,
        "method": "tools/call",
        "params": {
            "name": SEARCH_ALIAS_TOOL_NAME,
            "arguments": {"query": "anything", "_meta": meta_value},
        },
    }

    resp = handle_request(req)

    assert resp is not None
    assert resp["error"]["code"] == -32602


def test_do_search_applies_metadata_filters():
    mock_result = {
        "documents": [["Doc A", "Doc B", "Doc C"]],
        "metadatas": [[
            {"source": "raw/a.txt", "source_id": "source-a", "source_group_id": "group-1", "language": "en"},
            {"source": "raw/b.txt", "source_id": "source-b", "source_group_id": "group-2", "language": "en"},
            {"source": "raw/c.txt", "source_id": "source-c", "source_group_id": "group-2", "language": "es"},
        ]],
        "distances": [[0.1, 0.2, 0.3]],
    }
    with patch("alcove.query.retriever.query_text", return_value=mock_result) as mock_query:
        filtered = _do_search(
            query="test",
            collection="archive",
            n_results=5,
            language_filter="en",
            source_ids_include=["source-b"],
            source_group_ids_include=["group-2"],
        )

    mock_query.assert_called_once_with("test", n_results=5, collections=["archive"])
    assert len(filtered) == 1
    assert filtered[0]["source_id"] == "source-b"
    assert filtered[0]["score"] == 0.8


def test_list_collections_returns_names():
    with patch("alcove.mcp_server._do_list_collections", return_value=["archive", "docs"]):
        req = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "list_collections", "arguments": {}},
        }
        resp = handle_request(req)

    assert resp is not None
    names = json.loads(resp["result"]["content"][0]["text"])
    assert names == ["archive", "docs"]


def test_unknown_method_returns_error():
    req = {"jsonrpc": "2.0", "id": 8, "method": "nonexistent/method"}

    resp = handle_request(req)

    assert resp is not None
    assert resp["error"]["code"] == -32601


def test_unknown_tool_returns_error():
    req = {
        "jsonrpc": "2.0",
        "id": 9,
        "method": "tools/call",
        "params": {"name": "unknown_tool", "arguments": {}},
    }

    resp = handle_request(req)

    assert resp is not None
    assert resp["error"]["code"] == -32601
