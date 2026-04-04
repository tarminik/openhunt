"""OAuth 2.0 authentication for OpenAI Codex."""

import base64
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import click
import httpx

CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
CODEX_AUTH_URL = "https://auth.openai.com/authorize"
CODEX_TOKEN_URL = "https://auth.openai.com/oauth/token"
CODEX_AUDIENCE = "https://api.openai.com/v1"
CODEX_SCOPES = "openid profile email offline_access"
REDIRECT_PORT = 18539
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"
TOKEN_EXPIRY_BUFFER = 120  # refresh 2 minutes before expiry


def _decode_jwt_payload(token: str) -> dict:
    """Decode JWT payload without verification (for expiry check only)."""
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1]
    # Fix base64 padding
    payload += "=" * (4 - len(payload) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


def _is_token_expired(access_token: str) -> bool:
    """Check if JWT access token is expired or about to expire."""
    import time

    payload = _decode_jwt_payload(access_token)
    exp = payload.get("exp")
    if not exp:
        return True
    return time.time() > (exp - TOKEN_EXPIRY_BUFFER)


def _exchange_code(code: str, code_verifier: str) -> dict:
    """Exchange authorization code for tokens."""
    response = httpx.post(
        CODEX_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": CODEX_CLIENT_ID,
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": code_verifier,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def refresh_access_token(refresh_token: str) -> dict:
    """Refresh the access token using a refresh token.

    Returns dict with access_token and refresh_token.
    Raises httpx.HTTPStatusError on failure.
    """
    response = httpx.post(
        CODEX_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": CODEX_CLIENT_ID,
            "refresh_token": refresh_token,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def _generate_pkce() -> tuple[str, str]:
    """Generate PKCE code verifier and challenge."""
    import hashlib
    import secrets

    verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def codex_login() -> bool:
    """Run the full OAuth login flow for Codex. Returns True on success."""
    from openhunt.config import save_codex_tokens

    code_verifier, code_challenge = _generate_pkce()
    state = base64.urlsafe_b64encode(__import__("os").urandom(16)).decode()

    auth_params = urlencode({
        "response_type": "code",
        "client_id": CODEX_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": CODEX_SCOPES,
        "audience": CODEX_AUDIENCE,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    })
    auth_url = f"{CODEX_AUTH_URL}?{auth_params}"

    result = {"code": None, "error": None}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            params = parse_qs(urlparse(self.path).query)
            if params.get("state", [None])[0] != state:
                result["error"] = "State mismatch"
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"State mismatch. Try again.")
                return
            if "error" in params:
                result["error"] = params["error"][0]
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f"Error: {params['error'][0]}".encode())
                return
            result["code"] = params.get("code", [None])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write("Авторизация успешна! Можно закрыть эту вкладку.".encode())

        def log_message(self, format, *args):
            pass  # suppress HTTP logs

    try:
        server = HTTPServer(("localhost", REDIRECT_PORT), CallbackHandler)
    except OSError as e:
        click.echo(f"Не удалось запустить OAuth-сервер на порту {REDIRECT_PORT}: {e}")
        return False
    server.timeout = 120

    click.echo("Открываю браузер для авторизации в OpenAI...")
    if not webbrowser.open(auth_url):
        click.echo("Не удалось открыть браузер автоматически.")
    click.echo(f"Если браузер не открылся, перейдите по ссылке:\n{auth_url}\n")
    click.echo("Ожидаю авторизацию...")

    # Wait for single callback
    server.handle_request()
    server.server_close()

    if result["error"]:
        click.echo(f"Ошибка авторизации: {result['error']}")
        return False

    if not result["code"]:
        click.echo("Не получен код авторизации.")
        return False

    try:
        tokens = _exchange_code(result["code"], code_verifier)
    except httpx.HTTPStatusError as e:
        click.echo(f"Ошибка обмена кода: {e.response.status_code} {e.response.text}")
        return False

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    if not access_token or not refresh_token:
        click.echo("Не получены токены от OpenAI.")
        return False

    save_codex_tokens(access_token, refresh_token)
    click.echo("Авторизация в Codex успешна.")
    return True


def get_valid_codex_token() -> str | None:
    """Return a valid Codex access token, refreshing if needed."""
    from openhunt.config import get_codex_tokens, save_codex_tokens

    tokens = get_codex_tokens()
    if not tokens:
        return None

    access_token = tokens["access_token"]
    if not _is_token_expired(access_token):
        return access_token

    # Token expired — try to refresh
    try:
        new_tokens = refresh_access_token(tokens["refresh_token"])
    except Exception as e:
        click.echo(f"  ! Codex: ошибка обновления токена: {e}")
        return None

    new_access = new_tokens.get("access_token")
    new_refresh = new_tokens.get("refresh_token", tokens["refresh_token"])
    if not new_access:
        return None

    save_codex_tokens(new_access, new_refresh)
    return new_access
