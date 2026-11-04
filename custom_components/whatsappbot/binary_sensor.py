"""Binary sensor platform for WABot Studio: a plain on/off view of the connection status,
easier to use in an automation's condition/trigger than matching the status sensor's string."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import CONF_ACCOUNT_ID, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WhatsAppBotConnectedBinarySensor(data.status_coordinator, entry)])


class WhatsAppBotConnectedBinarySensor(CoordinatorEntity[DataUpdateCoordinator], BinarySensorEntity):
    """On when the account's status is CONNECTED."""

    _attr_has_entity_name = True
    _attr_name = "Connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        account_id = entry.data[CONF_ACCOUNT_ID]
        self._attr_unique_id = f"{entry.entry_id}_connected"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, account_id)})

    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("status") == "CONNECTED"
