"""Config flow for WABot Studio — OAuth 2.1 via the instance's own authorization server.

No API token to create and paste: the user only gives the instance's base URL, then
authorizes Home Assistant in their browser (the same flow the MCP connector uses), and a
client is registered on the fly via RFC7591 dynamic client registration — no pre-shared
client_id/secret, so this skips HA's "Application Credentials" picker entirely and drives
the auth step directly with a single, freshly-built implementation.
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WhatsAppBotApiError, WhatsAppBotClient
from .const import CONF_ACCOUNT_ID, CONF_ACCOUNT_LABEL, CONF_BASE_URL, DOMAIN
from .oauth2 import WhatsAppBotOAuth2Implementation

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_BASE_URL): str})


class WhatsAppBotConfigFlow(config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN):
    """One config entry = one WhatsApp account, matching how notify/sensor are scoped. Adding
    the integration again (picking a different account in the final step) adds a second one."""

    DOMAIN = DOMAIN
    VERSION = 1

    def __init__(self) -> None:
        super().__init__()
        self._base_url: str | None = None
        self._accounts: list[dict[str, Any]] = []
        self._oauth_data: dict[str, Any] | None = None

    @property
    def logger(self) -> logging.Logger:
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        return {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._base_url = user_input[CONF_BASE_URL].rstrip("/")
            self.flow_impl = WhatsAppBotOAuth2Implementation(self.hass, self._base_url)
            return await self.async_step_auth()
        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA)

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Called by the OAuth2 helper once the token exchange succeeds. Not finished yet —
        still need to know which WhatsApp account this entry is for."""
        session = async_get_clientsession(self.hass)
        client = WhatsAppBotClient(session, self._base_url, data["token"]["access_token"])
        try:
            self._accounts = await client.list_accounts()
        except WhatsAppBotApiError as err:
            _LOGGER.debug("Could not list accounts for %s: %s", self._base_url, err)
            return self.async_abort(reason="cannot_connect")
        if not self._accounts:
            return self.async_abort(reason="no_accounts")

        self._oauth_data = data
        if len(self._accounts) == 1:
            return await self._finish(self._accounts[0])
        return await self.async_step_account()

    async def async_step_account(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        accounts_by_id = {account["id"]: account for account in self._accounts}
        if user_input is not None:
            return await self._finish(accounts_by_id[user_input[CONF_ACCOUNT_ID]])

        schema = vol.Schema(
            {
                vol.Required(CONF_ACCOUNT_ID): vol.In(
                    {account["id"]: f'{account["label"]} ({account["status"]})' for account in self._accounts}
                )
            }
        )
        return self.async_show_form(step_id="account", data_schema=schema)

    async def _finish(self, account: dict[str, Any]) -> FlowResult:
        await self.async_set_unique_id(f"{self._base_url}:{account['id']}")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"WABot Studio — {account['label']}",
            data={
                **self._oauth_data,
                CONF_BASE_URL: self._base_url,
                CONF_ACCOUNT_ID: account["id"],
                CONF_ACCOUNT_LABEL: account["label"],
            },
        )
