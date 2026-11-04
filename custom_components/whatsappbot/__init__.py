"""The WABot Studio integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WhatsAppBotClient
from .const import CONF_ACCOUNT_ID, CONF_API_TOKEN, CONF_BASE_URL, DOMAIN

# notify has no config-entry-based unload hook of its own (it's still the classic
# BaseNotificationService platform, set up via discovery below), so removing the integration
# requires restarting Home Assistant to fully drop the registered notify service.
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    client = WhatsAppBotClient(session, entry.data[CONF_BASE_URL], entry.data[CONF_API_TOKEN])
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {"entry_id": entry.entry_id, CONF_ACCOUNT_ID: entry.data[CONF_ACCOUNT_ID]},
            {},
        )
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
