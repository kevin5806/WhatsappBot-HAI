"""Shared error translation: the API client's own exception isn't one Home Assistant's frontend
knows how to surface nicely on a failed service/number/button call, so entities wrap it."""
from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError

from .api import WhatsAppBotApiError


def ha_error_from_api(err: WhatsAppBotApiError) -> HomeAssistantError:
    return HomeAssistantError(str(err))
