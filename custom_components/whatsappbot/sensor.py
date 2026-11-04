"""Sensor platform for WABot Studio: connection status, and the latest message seen."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import CONF_ACCOUNT_ID, CONF_ACCOUNT_LABEL, DOMAIN
from .coordinator import WhatsAppBotMessagesCoordinator

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
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            WhatsAppBotStatusSensor(data.status_coordinator, entry),
            WhatsAppBotLastMessageSensor(data.messages_coordinator, entry),
        ]
    )


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


class WhatsAppBotLastMessageSensor(CoordinatorEntity[WhatsAppBotMessagesCoordinator], SensorEntity):
    """The most recent message (inbound or outbound) seen for this account.

    State is the message body (truncated to fit a sensor state's 255-char limit); the full
    picture — direction, contact, timestamp — is in the attributes. Automations that want to
    react the moment a new message arrives should use the whatsappbot_message_received event
    instead (fired once per new inbound message, with no polling delay beyond the coordinator's
    own interval); this entity is for dashboards and for conditions, not for triggers.
    """

    _attr_has_entity_name = True
    _attr_name = "Last message"
    _attr_icon = "mdi:message-text"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: WhatsAppBotMessagesCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        account_id = entry.data[CONF_ACCOUNT_ID]
        self._attr_unique_id = f"{entry.entry_id}_last_message"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, account_id)})

    @property
    def native_value(self) -> str | None:
        body = (self.coordinator.data or {}).get("body")
        return body[:255] if body else None

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        return {
            "direction": data.get("direction"),
            "contact_jid": data.get("contactJid"),
            "contact_name": data.get("contactName"),
            "created_at": data.get("createdAt"),
        }
