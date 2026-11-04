"""Notify platform for WABot Studio.

Uses the classic BaseNotificationService, not the newer single-target NotifyEntity: every
message needs a target (a contact or group JID) chosen per call, which the entity-based notify
platform doesn't support. Set up via discovery from __init__.py's async_setup_entry, since the
notify domain's config-entry support is for the single-target entity model.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.notify import ATTR_TARGET, BaseNotificationService
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .api import WhatsAppBotApiError, WhatsAppBotClient
from .const import CONF_ACCOUNT_ID, DOMAIN


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> WhatsAppBotNotificationService | None:
    if discovery_info is None:
        return None
    client: WhatsAppBotClient = hass.data[DOMAIN][discovery_info["entry_id"]]
    return WhatsAppBotNotificationService(client, discovery_info[CONF_ACCOUNT_ID])


class WhatsAppBotNotificationService(BaseNotificationService):
    """Sends a WhatsApp message to the target (contact or group JID) given per call."""

    def __init__(self, client: WhatsAppBotClient, account_id: str) -> None:
        self._client = client
        self._account_id = account_id

    async def async_send_message(self, message: str, **kwargs: Any) -> None:
        targets = kwargs.get(ATTR_TARGET)
        if not targets:
            raise HomeAssistantError(
                "A target (contact or group JID) is required, e.g. target: '393331112222@s.whatsapp.net'"
            )
        target = targets[0] if isinstance(targets, list) else targets
        try:
            await self._client.send_message(self._account_id, target, message)
        except WhatsAppBotApiError as err:
            raise HomeAssistantError(f"Failed to send WhatsApp message: {err}") from err
