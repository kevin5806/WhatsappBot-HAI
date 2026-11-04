# WABot Studio for Home Assistant

A custom [Home Assistant](https://www.home-assistant.io/) integration, distributed via
[HACS](https://hacs.xyz/) as a custom repository, that wraps the REST API of
[WABot Studio](https://github.com/kevin5806/WhatsappBot) — a self-hosted WhatsApp automation
platform.

Covers both directions: send a message and control reply timing from Home Assistant, and react
to incoming WhatsApp messages in an automation (an `Event` trigger, not just polling). No
rule/contact-list management from Home Assistant, no multi-account UI polish — that's still the
web app's job. WABot Studio's own "API actions" on rules (a rule can call an HA REST endpoint
directly) and HACS-side `rest_command`/`rest` sensors calling this same API remain available too,
for anything not covered below.

## Installation

1. In HACS, add this repository as a custom repository (category: Integration):
   `https://github.com/kevin5806/whatsappbot-hai`
2. Install "WABot Studio", then restart Home Assistant.
3. Settings → Devices & Services → Add Integration → "WABot Studio".
4. Enter your WABot Studio instance's base URL. You'll be sent to that instance's own
   login/authorize screen — no API token to create and copy by hand: this registers Home
   Assistant as an OAuth client on the fly (the same OAuth 2.1 flow the MCP connector uses) and
   gets a token after you log in and approve it.
5. If the authorization covers more than one WhatsApp account, pick which one this entry is for.
   Add the integration again, authorizing and picking a different account, to add a second one.

## What you get

Per account, this adds one device with:

- **`sensor.wabot_studio_<account>_status`** — the account's connection status
  (`CONNECTED`/`QR_REQUIRED`/`CONNECTING`/`DISCONNECTED`/`ERROR`), polled every 60s from the app's
  database (not a live WhatsApp round-trip, so it's always fast).
- **`binary_sensor.wabot_studio_<account>_connected`** — on/off version of the same status,
  easier to use in a condition or trigger than matching a string.
- **`sensor.wabot_studio_<account>_last_message`** — the most recent message (in either
  direction); `direction`, `contact_jid`, `contact_name` and `created_at` are in the attributes.
  Good for a dashboard or a condition — for a trigger, use the event below instead, since it
  fires immediately rather than waiting for this sensor's next poll.
- **`whatsappbot_message_received` event** — fired once for every new inbound message (never
  replayed for history already seen before Home Assistant started), with `account_id`,
  `account_label`, `contact_jid`, `contact_name`, `message` and `created_at`. Use it as an
  automation's trigger:

  ```yaml
  triggers:
    - trigger: event
      event_type: whatsappbot_message_received
      event_data:
        account_label: My account
  condition: "{{ 'apri il garage' in trigger.event.data.message | lower }}"
  action:
    - action: cover.open_cover
      target:
        entity_id: cover.garage
  ```

- **`number.wabot_studio_<account>_reply_delay`** and **`number.wabot_studio_<account>_ai_context_messages`**
  — the same reply-timing settings as the account page's "Reply timing & AI context" card,
  adjustable from an automation (e.g. shorten the delay while you're away from home).
- **`button.wabot_studio_<account>_reconnect`** — queues a (re)connect job; useful after a
  DISCONNECTED or ERROR status without deleting and recreating the account.
- **`button.wabot_studio_<account>_sync_contacts`** — queues a manual contact sync from WhatsApp.
- **`notify.<account>`** — send a WhatsApp message from an automation:

  ```yaml
  action: notify.send_message
  target:
    entity_id: notify.wabot_studio_my_account
  data:
    message: "The garage door was left open"
    target: "393331112222@s.whatsapp.net"
  ```

  `target` is required: a contact's JID (`<number>@s.whatsapp.net` or `<number>@c.us`) or a
  group's JID (`...@g.us`).

- **A Lovelace card** (`wabot-studio-card`) — status dot + a quick send form, no manual resource
  setup needed (registered automatically via `frontend.add_extra_js_url`). Add it as a
  "Manual" card in the dashboard editor:

  ```yaml
  type: custom:wabot-studio-card
  entity: sensor.wabot_studio_my_account_status
  notify_service: notify.wabot_studio_my_account
  title: WABot Studio # optional
  ```

  Replace `my_account` with the slug Home Assistant gave your account's entities (check
  Settings → Devices & Services → Entities, or the `notify.*` service listed under
  Developer Tools → Actions).

## Development

```bash
pip install -r requirements_test.txt  # if/when added
```

This repo is validated on every push via [hassfest](https://developers.home-assistant.io/docs/creating_integration_manifest/#hassfest)
and the [HACS action](https://github.com/hacs/action).

## License

[MIT](LICENSE)
