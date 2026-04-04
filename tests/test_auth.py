"""Tests for Codex OAuth authentication."""

import base64
import json
import time
from unittest.mock import MagicMock, patch

import pytest

from openhunt.auth import (
    _decode_jwt_payload,
    _is_token_expired,
    get_valid_codex_token,
    refresh_access_token,
)
from openhunt.config import (
    get_codex_tokens,
    invalidate_config_cache,
    reset_codex_tokens,
    save_codex_tokens,
)


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    invalidate_config_cache()
    monkeypatch.setattr("openhunt.config.OPENHUNT_DIR", tmp_path)
    monkeypatch.setattr("openhunt.config.BROWSER_DIR", tmp_path / "browser")
    monkeypatch.setattr("openhunt.config.CONFIG_PATH", tmp_path / "config.toml")
    monkeypatch.setattr("openhunt.config.AUTH_PATH", tmp_path / "auth.json")


def _make_jwt(exp: int) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}.signature"


def test_decode_jwt_payload():
    token = _make_jwt(1234567890)
    assert _decode_jwt_payload(token)["exp"] == 1234567890


def test_decode_jwt_invalid():
    assert _decode_jwt_payload("not-a-jwt") == {}
    assert _decode_jwt_payload("a.b") == {}


def test_is_token_expired_true():
    token = _make_jwt(int(time.time()) - 10)
    assert _is_token_expired(token) is True


def test_is_token_expired_false():
    token = _make_jwt(int(time.time()) + 3600)
    assert _is_token_expired(token) is False


def test_is_token_expired_within_buffer():
    token = _make_jwt(int(time.time()) + 60)  # expires in 60s, buffer is 120s
    assert _is_token_expired(token) is True


def test_save_and_get_codex_tokens():
    save_codex_tokens("access123", "refresh456")
    tokens = get_codex_tokens()
    assert tokens is not None
    assert tokens["access_token"] == "access123"
    assert tokens["refresh_token"] == "refresh456"


def test_get_codex_tokens_empty():
    assert get_codex_tokens() is None


def test_reset_codex_tokens():
    save_codex_tokens("a", "b")
    reset_codex_tokens()
    assert get_codex_tokens() is None


def test_get_valid_token_returns_fresh(monkeypatch):
    token = _make_jwt(int(time.time()) + 3600)
    save_codex_tokens(token, "refresh")
    result = get_valid_codex_token()
    assert result == token


def test_get_valid_token_refreshes_expired(monkeypatch):
    expired = _make_jwt(int(time.time()) - 10)
    fresh = _make_jwt(int(time.time()) + 3600)
    save_codex_tokens(expired, "old_refresh")

    with patch("openhunt.auth.refresh_access_token") as mock_refresh:
        mock_refresh.return_value = {
            "access_token": fresh,
            "refresh_token": "new_refresh",
        }
        result = get_valid_codex_token()

    assert result == fresh
    tokens = get_codex_tokens()
    assert tokens["refresh_token"] == "new_refresh"


def test_get_valid_token_returns_none_on_refresh_failure(monkeypatch):
    expired = _make_jwt(int(time.time()) - 10)
    save_codex_tokens(expired, "refresh")

    with patch("openhunt.auth.refresh_access_token", side_effect=Exception("network")):
        result = get_valid_codex_token()

    assert result is None


def test_get_valid_token_returns_none_when_no_tokens():
    assert get_valid_codex_token() is None
