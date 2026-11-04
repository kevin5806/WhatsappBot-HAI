"""The WABot Studio integration."""
from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow, discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WhatsAppBotClient
from .const import CONF_ACCOUNT_ID, CONF_ACCOUNT_LABEL, CONF_BASE_URL, DOMAIN
from .oauth2 import WhatsAppBotOAuth2Implementation

# notify has no config-entry-based unload hook of its own (it's still the classic
# BaseNotificationService platform, set up via discovery below), so removing the integration
# requires restarting Home Assistant to fully drop the registered notify service.
PLATFORMS: list[Platform] = [Platform.SENSOR]

CARD_URL_PATH = "/wabot_studio/wabot-studio-card.js"
_DATA_CARD_REGISTERED = "card_registered"


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
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client

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
