# WABot Studio for Home Assistant

A custom [Home Assistant](https://www.home-assistant.io/) integration, distributed via
[HACS](https://hacs.xyz/) as a custom repository, that wraps the REST API of
[WABot Studio](https://github.com/kevin5806/WhatsappBot) — a self-hosted WhatsApp automation
platform.

Scoped down on purpose for v1: send a message and see connection status. No inbound message
events, no rule/contact-list management from Home Assistant, no multi-account UI polish. The
other direction (WhatsApp → Home Assistant, e.g. triggering an automation on a specific message)
is already possible today without any of this, via WABot Studio's own "API actions" on rules (a
rule can call an HA REST endpoint directly) and HACS-side `rest_command`/`rest` sensors calling
this same API.

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

- **`sensor.wabot_studio_<account>_status`** — the account's connection status
  (`CONNECTED`/`QR_REQUIRED`/`CONNECTING`/`DISCONNECTED`/`ERROR`), polled every 60s from the app's
  database (not a live WhatsApp round-trip, so it's always fast).
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
