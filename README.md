# WABot Studio for Home Assistant

A custom [Home Assistant](https://www.home-assistant.io/) integration, distributed via
[HACS](https://hacs.xyz/) as a custom repository, that connects Home Assistant to your own
[WABot Studio](https://github.com/kevin5806/WhatsappBot) instance — a self-hosted WhatsApp
automation platform.

It covers both directions: send a WhatsApp message and tweak reply timing from Home Assistant,
and react to an incoming WhatsApp message in an automation (an `Event` trigger — no polling to
set up yourself). This README is what both the GitHub repo page and the HACS "repository" screen
show (HACS renders this same file), so everything you need is here in one place.

**Scope.** Rule and contact-list management stays in the web app on purpose — this integration is
for status, sending, reply timing and reacting to messages, not for re-building the app's UI
inside Home Assistant. For anything not covered below, WABot Studio's own "API actions" on rules
(a rule can call an HA REST endpoint directly) and HACS-side `rest_command`/`rest` sensors calling
the same API are still available.

## Requirements

- A running WABot Studio instance, reachable from your Home Assistant server, with at least one
  WhatsApp account already created in it.
- The WABot Studio **worker process** running — it's what actually talks to WhatsApp. The status
  sensor and the card's "send" button work without it, but **Reconnect**, **Sync contacts**, and
  sending a first message to a brand-new account need it. If a button call fails with "Worker is
  not running", that's your app's worker process, not this integration.
- Home Assistant 2024.1 or newer.

## Installing from HACS

1. Open **HACS** in the Home Assistant sidebar.
2. Click the **⋮** (three-dot) menu in the top right → **Custom repositories**.
3. Paste the repository URL, pick category **Integration**, and click **Add**:
   `https://github.com/kevin5806/whatsappbot-hai`
4. Close that dialog, then search for **"WABot Studio"** in HACS (now listed since you just added
   it as a custom repository) and open it.
5. Click **Download**, confirm the version, then **restart Home Assistant** — a brand-new
   integration's files aren't picked up until a restart.

## Adding the integration

6. Settings → **Devices & services** → **Add integration** → search **"WABot Studio"**.
7. Enter your WABot Studio instance's **base URL** (e.g. `https://whatsapp.example.com`) — this
   is the only thing you type in by hand.
8. You're sent to that instance's own login/authorize screen. There's no API token to create and
   copy manually: behind the scenes, Home Assistant registers itself as an OAuth client on the
   fly (the same OAuth 2.1 flow the app's MCP connector uses) the moment you continue. Log in if
   you aren't already, and approve the request.
9. If the account you logged in as owns more than one WhatsApp account, you're asked which one
   this entry is for. **Each integration entry is one WhatsApp account** — to add a second
   account, repeat from step 6 and pick a different one when asked (you'll go through the
   authorize screen again, but won't need to re-register the OAuth client).

Once set up, a device named **"WABot Studio — `<your account's label>`"** appears under that
integration entry, holding all the entities below.

## What you get, per account

| Entity | What it's for |
| --- | --- |
| `sensor.wabot_studio_<account>_status` | Raw connection status: `CONNECTED`, `QR_REQUIRED`, `CONNECTING`, `DISCONNECTED`, `ERROR`. Polled every 60s from the app's database — not a live WhatsApp round-trip, so it's always fast. |
| `binary_sensor.wabot_studio_<account>_connected` | The same status as plain on/off — easier to use in a trigger/condition than matching a string. |
| `sensor.wabot_studio_<account>_last_message` | The most recent message in either direction. `direction`, `contact_jid`, `contact_name` and `created_at` are in its attributes. Good for a dashboard or a condition; for a *trigger*, use the event below — it fires immediately instead of waiting for this sensor's next poll. |
| `number.wabot_studio_<account>_reply_delay` | Minutes the bot waits after the first unanswered message before it evaluates and replies to the whole burst. Same setting as the account page's "Reply timing & AI context" card — read **and write**. |
| `number.wabot_studio_<account>_ai_context_messages` | How many earlier messages of the chat are sent to the AI as context. Same card, read and write. |
| `button.wabot_studio_<account>_reconnect` | Queues a (re)connect job. Press it after a `DISCONNECTED`/`ERROR` status instead of deleting and recreating the account. |
| `button.wabot_studio_<account>_sync_contacts` | Queues a manual contact sync from WhatsApp. |
| `notify.wabot_studio_<account>` | Send a WhatsApp message (see below). |
| `whatsappbot_message_received` event | Fired once per **new** inbound message — see below. |
| `whatsappbot_rule_matched` event | Fired once a static/AI/default rule actually matched an inbound message — see below. |

The exact `<account>` slug is whatever Home Assistant made from your account's label — check
Settings → Devices & services → Entities (filter by the device) to see them precisely, or
Developer Tools → Actions to see the exact `notify.*` service name.

### Sending a message

```yaml
action: notify.send_message
target:
  entity_id: notify.wabot_studio_my_account
data:
  message: "The garage door was left open"
  target: "393331112222@s.whatsapp.net"
```

`target` is required, and accepts any of:
- a contact's JID (`<number>@s.whatsapp.net` or `<number>@c.us`) or a group's JID (`...@g.us`) —
  look these up from the account page in the app, or from a recent message's `contact_jid`
  attribute (see the last-message sensor above);
- a bare phone number;
- **a contact's stored name** (case-insensitive — an exact match wins, otherwise a single
  "contains" match), e.g. `target: "Luca"`. This is what makes a voice command like *"tell my
  assistant to WhatsApp Luca that I'm running late"* work without knowing anyone's JID — see
  the voice assistant example below. If the name matches nobody, or more than one contact, the
  call fails with a clear error instead of guessing.

### Reacting to an incoming message

`whatsappbot_message_received` fires for every new inbound message, with `account_id`,
`account_label`, `contact_jid`, `contact_name`, `message` and `created_at` in its data. It never
replays old history — the first poll after a Home Assistant restart only takes note of what
already exists, so you don't get a flood of events for messages you'd already seen.

```yaml
triggers:
  - trigger: event
    event_type: whatsappbot_message_received
    event_data:
      account_label: My account   # omit to match any account
condition: "{{ 'apri il garage' in trigger.event.data.message | lower }}"
action:
  - action: cover.open_cover
    target:
      entity_id: cover.garage
```

### Reacting to a rule match

`whatsappbot_message_received` fires on *every* new inbound message, matched or not. If instead
you want "run this automation when my AI/static rule actually recognized the message" — e.g. a
rule whose job is to respond to "apri il garage" style requests should also open the real
garage — use `whatsappbot_rule_matched` instead. It fires once a block's rules finish evaluating
(which can be minutes after the message arrived, since a block waits out its full reply delay
first), with `account_id`, `account_label`, `contact_jid`, `contact_name`, `message`, `rule_id`,
`rule_label`, `action_type` (`STATIC_REPLY` or `AI_REPLY`) and `processed_at`. Like
`whatsappbot_message_received`, it never replays old history on a Home Assistant restart.

```yaml
triggers:
  - trigger: event
    event_type: whatsappbot_rule_matched
condition: "{{ 'garage' in trigger.event.data.rule_label | lower }}"
action:
  - action: cover.open_cover
    target:
      entity_id: cover.garage
```

### A voice assistant that sends WhatsApp messages by name

Combine an automation's [sentence trigger](https://www.home-assistant.io/voice_control/custom_sentences/)
with `notify.send_message`'s by-name `target` (see "Sending a message" above) to make Assist (or
any voice satellite) handle *"manda un messaggio whatsapp a Luca dicendo sono in ritardo"*
without you writing any JID anywhere. Add this as an automation (Settings → Automations &
Scenes → Automations → Add automation → Edit in YAML), then say one of its sentences to Assist:

```yaml
alias: WhatsApp a qualcuno
triggers:
  - trigger: conversation
    command:
      - "manda un messaggio whatsapp a {name} dicendo {message}"
      - "scrivi su whatsapp a {name} {message}"
actions:
  - action: notify.send_message
    target:
      entity_id: notify.wabot_studio_my_account
    data:
      target: "{{ trigger.slots.name }}"
      message: "{{ trigger.slots.message }}"
```

### Adjusting reply timing from an automation

```yaml
# Reply instantly while you're home, go back to the normal 10-minute delay when you leave
triggers:
  - trigger: state
    entity_id: person.me
    to: "home"
action:
  - action: number.set_value
    target:
      entity_id: number.wabot_studio_my_account_reply_delay
    data:
      value: 0
```

### Recovering a stuck account

```yaml
triggers:
  - trigger: state
    entity_id: binary_sensor.wabot_studio_my_account_connected
    to: "off"
    for: "00:10:00"
action:
  - action: button.press
    target:
      entity_id: button.wabot_studio_my_account_reconnect
```

## The Lovelace card

Installing the integration also registers a card — `wabot-studio-card` — with a connection-status
dot and a quick send form. No manual resource setup needed; it's served and registered
automatically. Add it from the dashboard editor as a **Manual** card:

```yaml
type: custom:wabot-studio-card
entity: sensor.wabot_studio_my_account_status
notify_service: notify.wabot_studio_my_account
title: WABot Studio # optional
```

Replace `my_account` with your account's real entity slug (see "What you get" above for where to
find it).

## Troubleshooting

- **"Impossibile caricare il flusso di configurazione: 500 Internal Server Error" when adding the
  device.** Almost always the base URL: it must be reachable from the Home Assistant server
  itself (not just your browser), include the scheme (`https://...`), and have no trailing path.
- **"Invalid state. Is My Home Assistant configured..." on the authorize screen.** Means you're
  on an old version of this integration — update via HACS and restart.
- **A button call fails with "Worker is not running."** The WABot Studio worker process isn't
  up. Start it; the status sensor and card will keep working (they only read from the database),
  but Reconnect/Sync contacts need the worker to actually act.
- **Still seeing the old generated logo after updating.** HACS's "Redownload" doesn't always
  refresh cached brand images. Uninstall the integration in HACS, restart Home Assistant,
  reinstall, and restart again.
- **Two accounts, one `notify.notify` service.** Shouldn't happen from this version — each
  account gets its own `notify.wabot_studio_<account>` service. If you see a bare `notify.notify`,
  you're on an old version; update via HACS.

## Development

This repo is validated on every push via
[hassfest](https://developers.home-assistant.io/docs/creating_integration_manifest/#hassfest) and
the [HACS action](https://github.com/hacs/action).

## License

[MIT](LICENSE)
