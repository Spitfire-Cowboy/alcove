from __future__ import annotations

import io
import json
import sys
from unittest.mock import patch

import pytest

from alcove.mcp_server import SEARCH_ALIAS_TOOL_NAME, _do_list_collections, _do_search, handle_request, main


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


@pytest.mark.parametrize(
    "req",
    [
        [],
        {"jsonrpc": "2.0", "id": 15, "method": "tools/call", "params": []},
        {
            "jsonrpc": "2.0",
            "id": 16,
            "method": "tools/call",
            "params": {"name": "search", "arguments": []},
        },
    ],
)
def test_malformed_request_shapes_return_invalid_params(req):
    resp = handle_request(req)

    assert resp is not None
    assert resp["error"]["code"] == -32602


@pytest.mark.parametrize("query", [123, [], "", "   "])
def test_search_tool_non_string_or_empty_query_returns_invalid_params(query):
    req = {
        "jsonrpc": "2.0",
        "id": 17,
        "method": "tools/call",
        "params": {"name": "search", "arguments": {"query": query}},
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


def test_do_search_applies_group_filter():
    mock_result = {
        "documents": [["Doc A", "Doc B"]],
        "metadatas": [[
            {"source": "raw/a.txt", "source_id": "source-a", "source_group_id": "group-1"},
            {"source": "raw/b.txt", "source_id": "source-b", "source_group_id": "group-2"},
        ]],
        "distances": [[0.1, 0.2]],
    }
    with patch("alcove.query.retriever.query_text", return_value=mock_result):
        filtered = _do_search(
            query="test",
            n_results=5,
            source_group_ids_include=["group-1"],
        )

    assert len(filtered) == 1
    assert filtered[0]["source_group_id"] == "group-1"


def test_do_list_collections_normalizes_backend_entries():
    class FakeBackend:
        def list_collections(self):
            return [
                {"name": "archive", "doc_count": 2},
                {"doc_count": 0},
                "plain",
            ]

    with (
        patch("alcove.index.embedder.get_embedder", return_value=object()),
        patch("alcove.index.backend.get_backend", return_value=FakeBackend()),
    ):
        assert _do_list_collections() == ["archive", "plain"]


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


def test_list_collections_backend_error_returns_internal_error():
    with patch("alcove.mcp_server._do_list_collections", side_effect=RuntimeError("boom")):
        req = {
            "jsonrpc": "2.0",
            "id": 13,
            "method": "tools/call",
            "params": {"name": "list_collections", "arguments": {}},
        }
        resp = handle_request(req)

    assert resp is not None
    assert resp["error"]["code"] == -32603
    assert resp["error"]["message"] == "list_collections failed"


def test_search_backend_error_returns_internal_error():
    with patch("alcove.mcp_server._do_search", side_effect=RuntimeError("offline")):
        req = {
            "jsonrpc": "2.0",
            "id": 14,
            "method": "tools/call",
            "params": {"name": "search", "arguments": {"query": "anything"}},
        }
        resp = handle_request(req)

    assert resp is not None
    assert resp["error"]["code"] == -32603
    assert resp["error"]["message"] == "Search failed"


def test_unknown_method_returns_error():
    req = {"jsonrpc": "2.0", "id": 8, "method": "nonexistent/method"}

    resp = handle_request(req)

    assert resp is not None
    assert resp["error"]["code"] == -32601


def test_main_reads_json_lines_and_writes_responses(monkeypatch, capsys):
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    monkeypatch.setattr(sys, "stdin", io.StringIO("\n" + json.dumps(payload) + "\n"))

    main()

    lines = [line for line in capsys.readouterr().out.splitlines() if line]
    assert len(lines) == 1
    response = json.loads(lines[0])
    assert response["id"] == 1
    assert "tools" in response["result"]


def test_main_reports_parse_errors(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("{bad json}\n"))

    main()

    response = json.loads(capsys.readouterr().out)
    assert response["error"]["code"] == -32700


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
