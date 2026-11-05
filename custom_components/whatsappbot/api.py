"""Minimal async client for the WABot Studio REST API."""
from __future__ import annotations

import asyncio
import base64
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp

REQUEST_TIMEOUT = 10

TokenGetter = Callable[[], Awaitable[str]]


def static_token(access_token: str) -> TokenGetter:
    """Wraps a fixed access token (used during config_flow, before a refreshing OAuth2Session
    exists yet) in the same TokenGetter shape the runtime client uses."""

    async def _get() -> str:
        return access_token

    return _get


class WhatsAppBotApiError(Exception):
    """Raised for any failure talking to the WABot Studio API."""


class WhatsAppBotClient:
    """Thin wrapper around the bearer-token-authenticated REST API.

    Every route returns {"ok": true, "data": ...} or {"ok": false, "error": ...} — see
    WhatsappBot's lib/http.ts. This client unwraps that envelope and raises
    WhatsAppBotApiError on anything that isn't a clean "ok" response.

    Takes a TokenGetter rather than a fixed token so the caller controls refresh: the runtime
    client (__init__.py) passes one backed by HA's OAuth2Session (ensures the token is valid,
    refreshing it via the authorization server when needed, before every call).
    """

    def __init__(self, session: aiohttp.ClientSession, base_url: str, token: str | TokenGetter) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._get_token: TokenGetter = static_token(token) if isinstance(token, str) else token

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self._base_url}{path}"
        access_token = await self._get_token()
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                resp = await self._session.request(method, url, headers=headers, **kwargs)
                body = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise WhatsAppBotApiError(f"Cannot reach {url}: {err}") from err

        if not isinstance(body, dict):
            raise WhatsAppBotApiError(f"Unexpected response from {url}")
        if resp.status == 401:
            raise WhatsAppBotApiError("Access token rejected — re-authorize the integration")
        if not body.get("ok"):
            raise WhatsAppBotApiError(str(body.get("error") or f"HTTP {resp.status}"))
        return body.get("data")

    async def list_accounts(self) -> list[dict[str, Any]]:
        """GET /api/accounts — used right after authorizing to let the user pick an account."""
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

    async def send_media(
        self,
        account_id: str,
        target: str,
        image_bytes: bytes,
        mimetype: str,
        *,
        filename: str | None = None,
        caption: str | None = None,
    ) -> Any:
        """POST /api/accounts/{id}/messages/send-media — target is a contact or group JID."""
        payload: dict[str, Any] = {
            "contactJid": target,
            "mediaBase64": base64.b64encode(image_bytes).decode(),
            "mimetype": mimetype,
        }
        if filename:
            payload["filename"] = filename
        if caption:
            payload["caption"] = caption
        return await self._request(
            "POST",
            f"/api/accounts/{account_id}/messages/send-media",
            json=payload,
        )

    async def fetch_url_bytes(self, url: str) -> tuple[bytes, str]:
        """Downloads a URL (e.g. a Frigate snapshot/clip) and returns (content, content_type)."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                resp = await self._session.get(url)
                content = await resp.read()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise WhatsAppBotApiError(f"Cannot fetch {url}: {err}") from err
        if resp.status != 200:
            raise WhatsAppBotApiError(f"Fetching {url} returned HTTP {resp.status}")
        content_type = resp.content_type or "application/octet-stream"
        return content, content_type

    async def get_recent_messages(self, account_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """GET /api/accounts/{id}/messages/recent — newest first, across all contacts."""
        data = await self._request(
            "GET", f"/api/accounts/{account_id}/messages/recent", params={"limit": str(limit)}
        )
        return data if isinstance(data, list) else []

    async def get_matched_messages(self, account_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """GET /api/accounts/{id}/messages/recent?matchedOnly=true — inbound messages a rule
        (static, AI, or default) actually matched, most-recently-resolved first. Resolution can
        land well after the message arrived, since a block waits out its full reply delay first."""
        data = await self._request(
            "GET",
            f"/api/accounts/{account_id}/messages/recent",
            params={"limit": str(limit), "matchedOnly": "true"},
        )
        return data if isinstance(data, list) else []

    async def reconnect(self, account_id: str) -> Any:
        """POST /api/accounts/{id}/connect — queue a (re)connect job for an existing account."""
        return await self._request("POST", f"/api/accounts/{account_id}/connect")

    async def sync_contacts(self, account_id: str) -> Any:
        """POST /api/accounts/{id}/contacts/sync — queue a manual contact sync."""
        return await self._request("POST", f"/api/accounts/{account_id}/contacts/sync")

    async def update_reply_settings(
        self,
        account_id: str,
        *,
        reply_delay_minutes: int | None = None,
        ai_context_messages: int | None = None,
    ) -> dict[str, Any]:
        """PATCH /api/accounts/{id} — omitted fields keep their current value server-side."""
        payload: dict[str, int] = {}
        if reply_delay_minutes is not None:
            payload["replyDelayMinutes"] = reply_delay_minutes
        if ai_context_messages is not None:
            payload["aiContextMessages"] = ai_context_messages
        return await self._request("PATCH", f"/api/accounts/{account_id}", json=payload)
