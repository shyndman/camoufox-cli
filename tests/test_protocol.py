"""Tests for JSON-line protocol."""

from camoufox_cli.models import ErrorResponse, OkResponse
from camoufox_cli.protocol import (
    error_response,
    ok_response,
    parse_command,
    serialize_response,
)


class TestParseCommand:
    def test_basic(self):
        result = parse_command('{"action": "open", "params": {"url": "https://example.com"}}')
        assert result == {"action": "open", "params": {"url": "https://example.com"}}

    def test_with_whitespace(self):
        result = parse_command('  {"action": "close"}  \n')
        assert result == {"action": "close"}

    def test_unicode(self):
        result = parse_command('{"action": "fill", "params": {"text": "你好"}}')
        assert result["params"]["text"] == "你好"

    def test_invalid_json(self):
        import pytest
        with pytest.raises(Exception):
            parse_command("not json")


class TestSerializeResponse:
    def test_basic(self):
        result = serialize_response(OkResponse(id="r1"))
        assert result == b'{"id":"r1","success":true}\n'

    def test_unicode(self):
        result = serialize_response(ok_response("r1", {"title": "腾讯网"}))
        assert "腾讯网" in result.decode("utf-8")
        assert b"\\u" not in result  # non-ascii preserved

    def test_ends_with_newline(self):
        result = serialize_response(OkResponse(id="r1"))
        assert result.endswith(b"\n")


class TestOkResponse:
    def test_without_data(self):
        resp = ok_response("r1")
        assert isinstance(resp, OkResponse)
        assert resp.id == "r1"
        assert resp.success is True
        assert resp.data is None

    def test_with_data(self):
        resp = ok_response("r1", {"url": "https://example.com"})
        assert resp.data is not None
        assert resp.data.url == "https://example.com"

    def test_with_none_data(self):
        resp = ok_response("r1", None)
        assert resp.data is None


class TestErrorResponse:
    def test_basic(self):
        resp = error_response("r1", "something went wrong")
        assert isinstance(resp, ErrorResponse)
        assert resp.id == "r1"
        assert resp.success is False
        assert resp.error == "something went wrong"

    def test_preserves_id(self):
        resp = error_response("abc123", "err")
        assert resp.id == "abc123"
