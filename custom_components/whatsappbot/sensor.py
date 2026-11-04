"""Sensor platform for WABot Studio: one account's connection status."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed

from .api import WhatsAppBotApiError, WhatsAppBotClient
from .const import CONF_ACCOUNT_ID, CONF_ACCOUNT_LABEL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STATUS_ICONS = {
    "CONNECTED": "mdi:whatsapp",
    "CONNECTING": "mdi:progress-clock",
    "QR_REQUIRED": "mdi:qrcode",
    "DISCONNECTED": "mdi:close-network",
    "ERROR": "mdi:alert-circle",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    client: WhatsAppBotClient = hass.data[DOMAIN][entry.entry_id]
    account_id = entry.data[CONF_ACCOUNT_ID]

    async def _async_update() -> dict:
        try:
            return await client.get_account(account_id)
        except WhatsAppBotApiError as err:
            raise UpdateFailed(str(err)) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_{account_id}",
        update_method=_async_update,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    )
    await coordinator.async_config_entry_first_refresh()
    async_add_entities([WhatsAppBotStatusSensor(coordinator, entry)])


class WhatsAppBotStatusSensor(CoordinatorEntity[DataUpdateCoordinator], SensorEntity):
    """Connection status (CONNECTED/QR_REQUIRED/CONNECTING/DISCONNECTED/ERROR) of one account."""

    _attr_has_entity_name = True
    _attr_name = "Status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        account_id = entry.data[CONF_ACCOUNT_ID]
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account_id)},
            name=f"WABot Studio — {entry.data[CONF_ACCOUNT_LABEL]}",
            manufacturer="WABot Studio",
        )

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.get("status") if self.coordinator.data else None

    @property
    def icon(self) -> str:
        return STATUS_ICONS.get(self.native_value or "", "mdi:whatsapp")

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        return {"label": data.get("label"), "phone_hint": data.get("phoneHint")}
