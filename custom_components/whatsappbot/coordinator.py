"""Coordinators for WABot Studio: account status (plain polling) and recent messages
(polling + new-inbound-message event detection, for automation triggers)."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WhatsAppBotApiError, WhatsAppBotClient
from .const import DOMAIN, EVENT_MESSAGE_RECEIVED

_LOGGER = logging.getLogger(__name__)

MESSAGES_SCAN_INTERVAL = 15
# Caps memory for accounts with a lot of traffic; only the most recent window is ever compared
# against anyway (get_recent_messages is called with a small limit).
MAX_SEEN_IDS = 200


class WhatsAppBotMessagesCoordinator(DataUpdateCoordinator[dict[str, Any] | None]):
    """Polls the account's recent messages and fires EVENT_MESSAGE_RECEIVED for each new inbound
    one, so automations can trigger on "Event" instead of polling a sensor's state themselves.

    The first refresh after (re)start only seeds the seen-ids set — it never fires events for
    messages that already existed, which would otherwise replay the whole recent history as
    "new" every time Home Assistant restarts.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: WhatsAppBotClient,
        account_id: str,
        account_label: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{account_id}_messages",
            update_interval=timedelta(seconds=MESSAGES_SCAN_INTERVAL),
        )
        self._client = client
        self._account_id = account_id
        self._account_label = account_label
        self._seen_ids: set[str] = set()
        self._seeded = False

    async def _async_update_data(self) -> dict[str, Any] | None:
        try:
            rows = await self._client.get_recent_messages(self._account_id, limit=10)
        except WhatsAppBotApiError as err:
            raise UpdateFailed(str(err)) from err

        if not rows:
            return self.data

        new_rows = [r for r in rows if r.get("id") not in self._seen_ids]
        self._seen_ids.update(r["id"] for r in rows if r.get("id"))
        if len(self._seen_ids) > MAX_SEEN_IDS:
            # Sets have no stable order; dropping down to the ids still in this page is enough
            # since nothing older can show up again.
            self._seen_ids = {r["id"] for r in rows if r.get("id")}

        if self._seeded:
            # Oldest-first, so a burst fires in the order the messages actually arrived.
            for row in reversed(new_rows):
                if row.get("direction") == "INBOUND":
                    self.hass.bus.async_fire(
                        EVENT_MESSAGE_RECEIVED,
                        {
                            "account_id": self._account_id,
                            "account_label": self._account_label,
                            "contact_jid": row.get("contactJid"),
                            "contact_name": row.get("contactName"),
                            "message": row.get("body"),
                            "created_at": row.get("createdAt"),
                        },
                    )
        self._seeded = True
        return rows[0]
