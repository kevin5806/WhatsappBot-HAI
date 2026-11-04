"""Constants for the WABot Studio integration."""

DOMAIN = "whatsappbot"

CONF_BASE_URL = "base_url"
CONF_ACCOUNT_ID = "account_id"
CONF_ACCOUNT_LABEL = "account_label"

DEFAULT_SCAN_INTERVAL = 60

# Fired for every new inbound message (never replayed on restart), so automations can trigger on
# an Event instead of polling a sensor's state themselves.
EVENT_MESSAGE_RECEIVED = "whatsappbot_message_received"
