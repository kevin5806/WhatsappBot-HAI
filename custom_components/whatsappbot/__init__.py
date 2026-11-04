"""The WABot Studio integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow, discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WhatsAppBotApiError, WhatsAppBotClient
from .const import CONF_ACCOUNT_ID, CONF_ACCOUNT_LABEL, CONF_BASE_URL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import WhatsAppBotMessagesCoordinator
from .oauth2 import WhatsAppBotOAuth2Implementation

# notify has no config-entry-based unload hook of its own (it's still the classic
# BaseNotificationService platform, set up via discovery below), so removing the integration
# requires restarting Home Assistant to fully drop the registered notify service.
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.NUMBER, Platform.BUTTON]

_LOGGER = logging.getLogger(__name__)

CARD_URL_PATH = "/wabot_studio/wabot-studio-card.js"
_DATA_CARD_REGISTERED = "card_registered"


@dataclass
class WhatsAppBotData:
    """Everything a platform file needs for one config entry (one account)."""

    client: WhatsAppBotClient
    status_coordinator: DataUpdateCoordinator
    messages_coordinator: WhatsAppBotMessagesCoordinator


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve and register the Lovelace card once, regardless of account count."""
    if hass.data.setdefault(DOMAIN, {}).get(_DATA_CARD_REGISTERED):
        return
    hass.data[DOMAIN][_DATA_CARD_REGISTERED] = True
    www_dir = Path(__file__).parent / "www"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL_PATH, str(www_dir / "wabot-studio-card.js"), cache_headers=False)]
    )
    add_extra_js_url(hass, CARD_URL_PATH)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    implementation = WhatsAppBotOAuth2Implementation(hass, entry.data[CONF_BASE_URL])
    oauth_session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    async def _get_access_token() -> str:
        await oauth_session.async_ensure_token_valid()
        return oauth_session.token["access_token"]

    session = async_get_clientsession(hass)
    client = WhatsAppBotClient(session, entry.data[CONF_BASE_URL], _get_access_token)
    account_id = entry.data[CONF_ACCOUNT_ID]

    async def _async_update_status() -> dict:
        try:
            return await client.get_account(account_id)
        except WhatsAppBotApiError as err:
            raise UpdateFailed(str(err)) from err

    status_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_{account_id}_status",
        update_method=_async_update_status,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    )
    await status_coordinator.async_config_entry_first_refresh()

    messages_coordinator = WhatsAppBotMessagesCoordinator(
        hass, client, account_id, entry.data[CONF_ACCOUNT_LABEL]
    )
    await messages_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = WhatsAppBotData(
        client=client, status_coordinator=status_coordinator, messages_coordinator=messages_coordinator
    )

    await _async_register_card(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {
                "entry_id": entry.entry_id,
                CONF_ACCOUNT_ID: entry.data[CONF_ACCOUNT_ID],
                # Without this, every account's notify service collides on the generic
                # "notify.notify" name (homeassistant.components.notify.legacy falls back to
                # SERVICE_NOTIFY when CONF_NAME is absent from discovery_info).
                CONF_NAME: f"wabot_studio_{entry.data[CONF_ACCOUNT_LABEL]}",
            },
            {},
        )
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
