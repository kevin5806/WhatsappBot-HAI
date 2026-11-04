"""Button platform for WABot Studio: one-shot actions useful from automations and dashboards —
kick a stuck/disconnected account back into connecting, or refresh the synced contact list."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import WhatsAppBotApiError, WhatsAppBotClient
from .const import CONF_ACCOUNT_ID, DOMAIN
from .exceptions import ha_error_from_api


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            WhatsAppBotReconnectButton(data.client, entry),
            WhatsAppBotSyncContactsButton(data.client, entry),
        ]
    )


class _WhatsAppBotButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, client: WhatsAppBotClient, entry: ConfigEntry) -> None:
        self._client = client
        self._account_id = entry.data[CONF_ACCOUNT_ID]
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, self._account_id)})


class WhatsAppBotReconnectButton(_WhatsAppBotButton):
    """Queues a (re)connect job — useful after a DISCONNECTED or ERROR status, without deleting
    and recreating the account."""

    _attr_name = "Reconnect"
    _attr_icon = "mdi:restart"

    def __init__(self, client: WhatsAppBotClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{entry.entry_id}_reconnect"

    async def async_press(self) -> None:
        try:
            await self._client.reconnect(self._account_id)
        except WhatsAppBotApiError as err:
            raise ha_error_from_api(err) from err


class WhatsAppBotSyncContactsButton(_WhatsAppBotButton):
    """Queues a manual contact sync from WhatsApp."""

    _attr_name = "Sync contacts"
    _attr_icon = "mdi:contacts"

    def __init__(self, client: WhatsAppBotClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{entry.entry_id}_sync_contacts"

    async def async_press(self) -> None:
        try:
            await self._client.sync_contacts(self._account_id)
        except WhatsAppBotApiError as err:
            raise ha_error_from_api(err) from err
