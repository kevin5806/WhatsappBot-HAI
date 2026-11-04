"""Number platform for WABot Studio: reply timing settings, adjustable from an automation
(e.g. shorten the reply delay while you're away, lengthen it when you're home)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .api import WhatsAppBotApiError, WhatsAppBotClient
from .const import CONF_ACCOUNT_ID, DOMAIN
from .exceptions import ha_error_from_api


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            WhatsAppBotReplyDelayNumber(data.client, data.status_coordinator, entry),
            WhatsAppBotAiContextNumber(data.client, data.status_coordinator, entry),
        ]
    )


class _WhatsAppBotSettingNumber(CoordinatorEntity[DataUpdateCoordinator], NumberEntity):
    """Shared plumbing: read the account row the status coordinator already polls, write via a
    PATCH that only touches this one field, then ask the coordinator to refresh so the new value
    shows up right away instead of waiting for the next scheduled poll."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG
    _data_key: str

    def __init__(self, client: WhatsAppBotClient, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._client = client
        self._account_id = entry.data[CONF_ACCOUNT_ID]
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, self._account_id)})

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._data_key)


class WhatsAppBotReplyDelayNumber(_WhatsAppBotSettingNumber):
    """Minutes to wait after the first unanswered message before the bot evaluates and replies."""

    _attr_name = "Reply delay"
    _attr_icon = "mdi:clock-outline"
    _attr_native_min_value = 0
    _attr_native_max_value = 1440
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "min"
    _data_key = "replyDelayMinutes"

    def __init__(self, client: WhatsAppBotClient, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(client, coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_reply_delay_minutes"

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self._client.update_reply_settings(self._account_id, reply_delay_minutes=int(value))
        except WhatsAppBotApiError as err:
            raise ha_error_from_api(err) from err
        await self.coordinator.async_request_refresh()


class WhatsAppBotAiContextNumber(_WhatsAppBotSettingNumber):
    """How many earlier messages of the chat are sent to the AI as context along with a block."""

    _attr_name = "AI context messages"
    _attr_icon = "mdi:message-text-clock"
    _attr_native_min_value = 0
    _attr_native_max_value = 30
    _attr_native_step = 1
    _data_key = "aiContextMessages"

    def __init__(self, client: WhatsAppBotClient, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(client, coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_ai_context_messages"

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self._client.update_reply_settings(self._account_id, ai_context_messages=int(value))
        except WhatsAppBotApiError as err:
            raise ha_error_from_api(err) from err
        await self.coordinator.async_request_refresh()
