"""Config flow for WABot Studio."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WhatsAppBotApiError, WhatsAppBotClient
from .const import CONF_ACCOUNT_ID, CONF_ACCOUNT_LABEL, CONF_API_TOKEN, CONF_BASE_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BASE_URL): str,
        vol.Required(CONF_API_TOKEN): str,
    }
)


class WhatsAppBotConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WABot Studio.

    One config entry = one WhatsApp account, matching how the notify/sensor entities are
    scoped. Adding the integration again (with a different account chosen in step 2) is the
    supported way to add a second account.
    """

    VERSION = 1

    def __init__(self) -> None:
        self._base_url: str | None = None
        self._api_token: str | None = None
        self._accounts: list[dict[str, Any]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            base_url = user_input[CONF_BASE_URL].rstrip("/")
            api_token = user_input[CONF_API_TOKEN]
            session = async_get_clientsession(self.hass)
            client = WhatsAppBotClient(session, base_url, api_token)
            try:
                self._accounts = await client.list_accounts()
            except WhatsAppBotApiError as err:
                _LOGGER.debug("Validation failed for %s: %s", base_url, err)
                errors["base"] = "cannot_connect"
            else:
                if not self._accounts:
                    errors["base"] = "no_accounts"
                else:
                    self._base_url = base_url
                    self._api_token = api_token
                    if len(self._accounts) == 1:
                        return await self._finish(self._accounts[0])
                    return await self.async_step_account()

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors)

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
                CONF_BASE_URL: self._base_url,
                CONF_API_TOKEN: self._api_token,
                CONF_ACCOUNT_ID: account["id"],
                CONF_ACCOUNT_LABEL: account["label"],
            },
        )
