"""OAuth2 implementation for WABot Studio.

WABot Studio runs its own OAuth 2.1 authorization server per instance (the same one its MCP
connector uses): RFC7591 dynamic client registration, PKCE-only (no client secret), and a
browser consent screen reusing the instance's own login. So unlike most HA OAuth2 integrations,
there is no pre-shared client_id/secret to ask the user for — this implementation registers a
fresh client against the chosen instance the first time it's needed.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(40)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


class WhatsAppBotOAuth2Implementation(config_entry_oauth2_flow.AbstractOAuth2Implementation):
    """Registers a client via RFC7591 DCR and drives the authorization_code + PKCE exchange."""

    def __init__(self, hass: HomeAssistant, base_url: str) -> None:
        self.hass = hass
        self._base_url = base_url.rstrip("/")
        self._client_id: str | None = None
        self._code_verifier: str | None = None

    @property
    def name(self) -> str:
        return "WABot Studio"

    @property
    def domain(self) -> str:
        return DOMAIN

    @property
    def base_url(self) -> str:
        return self._base_url

    async def _ensure_client_id(self, redirect_uri: str) -> str:
        if self._client_id:
            return self._client_id
        session = async_get_clientsession(self.hass)
        async with session.post(
            f"{self._base_url}/api/oauth/register",
            json={"redirect_uris": [redirect_uri], "client_name": "Home Assistant"},
        ) as resp:
            body = await resp.json()
        self._client_id = body["client_id"]
        return self._client_id

    async def async_generate_authorize_url(self, flow_id: str) -> str:
        redirect_uri = config_entry_oauth2_flow.async_get_redirect_uri(self.hass)
        client_id = await self._ensure_client_id(redirect_uri)
        verifier, challenge = _pkce_pair()
        self._code_verifier = verifier
        return (
            f"{self._base_url}/oauth/authorize"
            f"?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}"
            f"&code_challenge={challenge}&code_challenge_method=S256&state={flow_id}"
        )

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        redirect_uri = config_entry_oauth2_flow.async_get_redirect_uri(self.hass)
        session = async_get_clientsession(self.hass)
        async with session.post(
            f"{self._base_url}/api/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": external_data["code"],
                "redirect_uri": redirect_uri,
                "client_id": self._client_id,
                "code_verifier": self._code_verifier,
            },
        ) as resp:
            token = await resp.json()
        if "access_token" not in token:
            raise ValueError(f"Token exchange failed: {token.get('error', token)}")
        return token

    async def _async_refresh_token(self, token: dict) -> dict:
        session = async_get_clientsession(self.hass)
        async with session.post(
            f"{self._base_url}/api/oauth/token",
            data={"grant_type": "refresh_token", "refresh_token": token["refresh_token"]},
        ) as resp:
            new_token = await resp.json()
        if "access_token" not in new_token:
            raise ValueError(f"Token refresh failed: {new_token.get('error', new_token)}")
        return {**token, **new_token}
