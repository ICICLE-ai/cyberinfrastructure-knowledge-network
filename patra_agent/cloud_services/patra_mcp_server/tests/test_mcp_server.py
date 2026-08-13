from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from server import mcp_server


def _fake_response(json_value=None, raise_for_status_error=None):
    response = MagicMock()
    if raise_for_status_error is not None:
        response.raise_for_status.side_effect = raise_for_status_error
    else:
        response.raise_for_status.return_value = None
    response.json.return_value = json_value or {}
    return response


@pytest.mark.asyncio
async def test_handle_list_tools_returns_all_twelve_documented_tools():
    result = await mcp_server.handle_list_tools()

    names = [tool.name for tool in result.tools]
    assert len(names) == 12
    assert set(names) == {
        "search_model_cards", "get_model_card", "list_all_model_cards",
        "add_model_card", "update_model_card", "get_model_deployments",
        "get_model_download_url", "set_model_location", "generate_model_id",
        "add_datasheet", "register_device", "register_user",
    }


@pytest.mark.asyncio
async def test_search_model_cards_missing_query_does_not_call_http_client(monkeypatch):
    monkeypatch.setattr(mcp_server, "http_client", AsyncMock())

    result = await mcp_server.handle_call_tool("search_model_cards", {})

    assert "Query parameter is required" in result.content[0].text
    mcp_server.http_client.get.assert_not_called()


@pytest.mark.asyncio
async def test_get_model_card_happy_path_calls_expected_url(monkeypatch):
    fake_client = AsyncMock()
    fake_client.get.return_value = _fake_response(json_value={"id": "model-1"})
    monkeypatch.setattr(mcp_server, "http_client", fake_client)

    result = await mcp_server.handle_call_tool("get_model_card", {"model_id": "model-1"})

    fake_client.get.assert_called_once_with(f"{mcp_server.PATRA_SERVER_URL}/modelcard/model-1")
    assert "Model card for model-1" in result.content[0].text


@pytest.mark.asyncio
async def test_add_model_card_happy_path_posts_payload(monkeypatch):
    fake_client = AsyncMock()
    fake_client.post.return_value = _fake_response(json_value={"id": "new-model"})
    monkeypatch.setattr(mcp_server, "http_client", fake_client)

    card_data = {"name": "ResNet", "author": "Alice"}
    result = await mcp_server.handle_call_tool("add_model_card", {"model_card_data": card_data})

    fake_client.post.assert_called_once_with(
        f"{mcp_server.PATRA_SERVER_URL}/modelcard", json=card_data
    )
    assert "Model card added successfully" in result.content[0].text


@pytest.mark.asyncio
async def test_http_error_surfaces_as_text_not_raised(monkeypatch):
    fake_client = AsyncMock()
    fake_client.get.side_effect = httpx.HTTPError("connection failed")
    monkeypatch.setattr(mcp_server, "http_client", fake_client)

    result = await mcp_server.handle_call_tool("get_model_card", {"model_id": "model-1"})

    assert "HTTP error: connection failed" in result.content[0].text


@pytest.mark.asyncio
async def test_set_model_location_rejects_non_url_without_calling_http_client(monkeypatch):
    fake_client = AsyncMock()
    monkeypatch.setattr(mcp_server, "http_client", fake_client)

    result = await mcp_server.handle_call_tool(
        "set_model_location", {"model_id": "model-1", "location": "not-a-url"}
    )

    assert "Location must be a valid URL" in result.content[0].text
    fake_client.put.assert_not_called()


@pytest.mark.asyncio
async def test_set_model_location_accepts_valid_url(monkeypatch):
    fake_client = AsyncMock()
    fake_client.put.return_value = _fake_response(json_value={"status": "ok"})
    monkeypatch.setattr(mcp_server, "http_client", fake_client)

    result = await mcp_server.handle_call_tool(
        "set_model_location",
        {"model_id": "model-1", "location": "https://huggingface.co/a/b"},
    )

    fake_client.put.assert_called_once()
    assert "updated successfully" in result.content[0].text


@pytest.mark.asyncio
async def test_unknown_tool_dispatch_returns_unknown_tool_text():
    result = await mcp_server.handle_call_tool("not_a_real_tool", {})
    assert result.content[0].text == "Unknown tool: not_a_real_tool"


@pytest.mark.asyncio
async def test_exception_inside_tool_handler_is_caught_and_returned_as_text(monkeypatch):
    async def boom(_arguments):
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(mcp_server, "get_model_card", boom)

    result = await mcp_server.handle_call_tool("get_model_card", {"model_id": "model-1"})

    assert "Error: unexpected failure" in result.content[0].text
