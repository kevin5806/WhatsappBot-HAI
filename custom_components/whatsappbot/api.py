"""Minimal async client for the WABot Studio REST API."""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

REQUEST_TIMEOUT = 10


class WhatsAppBotApiError(Exception):
    """Raised for any failure talking to the WABot Studio API."""


class WhatsAppBotClient:
    """Thin wrapper around the bearer-token-authenticated REST API.

    Every route returns {"ok": true, "data": ...} or {"ok": false, "error": ...} — see
    WhatsappBot's lib/http.ts. This client unwraps that envelope and raises
    WhatsAppBotApiError on anything that isn't a clean "ok" response.
    """

    def __init__(self, session: aiohttp.ClientSession, base_url: str, api_token: str) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_token}"}

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self._base_url}{path}"
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                resp = await self._session.request(method, url, headers=self._headers, **kwargs)
                body = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise WhatsAppBotApiError(f"Cannot reach {url}: {err}") from err

        if not isinstance(body, dict):
            raise WhatsAppBotApiError(f"Unexpected response from {url}")
        if resp.status == 401:
            raise WhatsAppBotApiError("Invalid or revoked API token")
        if not body.get("ok"):
            raise WhatsAppBotApiError(str(body.get("error") or f"HTTP {resp.status}"))
        return body.get("data")

    async def list_accounts(self) -> list[dict[str, Any]]:
        """GET /api/accounts — used to validate the token and let the user pick an account."""
        data = await self._request("GET", "/api/accounts")
        return data if isinstance(data, list) else []

    async def get_account(self, account_id: str) -> dict[str, Any]:
        """GET /api/accounts/{id} — DB-backed, so it's fast and safe to poll on an interval
        (unlike /status, which round-trips through the live WhatsApp client)."""
        return await self._request("GET", f"/api/accounts/{account_id}")

    async def send_message(self, account_id: str, target: str, message: str) -> Any:
        """POST /api/accounts/{id}/messages/send — target is a contact or group JID."""
        return await self._request(
            "POST",
            f"/api/accounts/{account_id}/messages/send",
            json={"contactJid": target, "body": message},
        )
