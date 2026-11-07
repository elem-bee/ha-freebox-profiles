# Freebox Profiles for Home Assistant

*[Version française](README.md)*

Home Assistant integration for the **profiles (parental control) of Freebox OS**, the operating system of the French ISP Free's boxes: see whether Internet is allowed or blocked for each profile, pause a profile (with or without a duration), return it to its planning, and automate all of this.

> Community project, **not affiliated with Free / Iliad**.

## Features

Each Freebox OS profile becomes a device in Home Assistant, with:

| Entity | Type | Purpose |
|---|---|---|
| Mode | Select | *Planning*, *Allowed* or *Blocked* (no time limit) |
| Internet access | Sensor | Actual state: allowed, blocked or web only |
| Planned access | Sensor | What the planning sets right now |
| Override end | Sensor (timestamp) | End of the pause or temporary allowance |
| Next planned change | Sensor (timestamp) | Next switch of the planning |
| Connected devices | Sensor | Number of reachable devices of the profile; details (name, connection, Wi-Fi band, signal) as attributes |
| Device connected | Event | Triggered when a device of the profile connects (name and MAC address as attributes) |

Two actions are available for automations:

- `freebox_profiles.set_override`: block or allow Internet, for a duration in minutes (or without limit);
- `freebox_profiles.clear_override`: return to the planning.

Profiles created later in Freebox OS are added automatically. Data is refreshed every 30 seconds.

## Compatibility

| Freebox | Status |
|---|---|
| Delta | API behaviour verified |
| Ultra, Pop, up-to-date Revolution | Not tested: the Profile API (Freebox OS API v8+) should be the same. Feedback welcome. |

Requires **Home Assistant 2025.2 or newer**, running **on the local network of the Freebox**.

If you try it on another model, please open a "Compatibility" issue, even if everything works.

## Installation

### Marketplace (Home Assistant 2026.11 and newer)

1. Open **Settings > Marketplace**.
2. Menu ⋮ > **Custom repositories**, add `https://github.com/elem-bee/ha-freebox-profiles` as **Integration**.
3. Search for **Freebox Profiles**, install it, then restart Home Assistant.

### HACS (Home Assistant 2025.2 to 2026.10)

Same steps in HACS: **Custom repositories**, type **Integration**, then install and restart.

### Manual

Copy `custom_components/freebox_profiles` into the `config/custom_components/` folder of Home Assistant and restart. Updates will not be offered automatically.

## Configuration

1. **Settings > Devices & services > Add integration > Freebox Profiles.**
2. Keep the default address (`mafreebox.freebox.fr`, port `443`) and submit.
3. **Accept the access request on the Freebox** when asked (front display of the box, or as your model requires). You have about 2 minutes.
4. **Grant the "Profiles" permission**: in Freebox OS, open **Freebox settings > Access management > Applications**, edit **"Home Assistant - Freebox Profiles"** and tick **Profiles** (parental control).

Without step 4, the integration raises an alert in **Settings > Repairs** and keeps retrying. The alert disappears once the permission is granted.

### Connection notifications

To get a notification on your phone each time a device of a profile connects: **Settings > Devices & services > Freebox Profiles > Configure**, then choose:

- **Phones to notify**: the phones with the Home Assistant Companion app;
- **Profiles**: the ones you care about (empty: all);
- **Minimum time offline** (5 minutes by default): a device must have been disconnected for at least this long for its reconnection to be reported. This avoids a notification each time a phone wakes up from sleep. Set 0 to be notified at every reconnection.

Devices already connected when Home Assistant starts, or added to a profile while connected, trigger nothing. Detection follows the refresh: the notification arrives within 30 seconds.

Each connection also triggers the *Device connected* entity of the profile and the `freebox_profiles_device_connected` event (`profile_id`, `profile_name`, `device_name`, `mac`), for your own automations.

## Automation examples

Block Internet for a profile at 10 pm, for 8 hours:

```yaml
automation:
  - alias: "Evening Internet cut"
    triggers:
      - trigger: time
        at: "22:00:00"
    actions:
      - action: freebox_profiles.set_override
        target:
          entity_id: select.teen_room_mode
        data:
          mode: denied
          duration: 480
```

Return to the planning:

```yaml
actions:
  - action: freebox_profiles.clear_override
    target:
      entity_id: select.teen_room_mode
```

Custom notification when a given device connects:

```yaml
triggers:
  - trigger: event
    event_type: freebox_profiles_device_connected
    event_data:
      mac: "AA:BB:CC:DD:EE:FF"
actions:
  - action: notify.mobile_app_my_phone
    data:
      message: "{{ trigger.event.data.device_name }} just connected."
```

Replace the entity ids with yours (they depend on your profile names and Home Assistant language).

## How it works

- The integration only talks to the Freebox **locally**, over HTTPS, validating the certificate with the root certificates published by Free.
- It registers as a Freebox OS application: you can revoke its access at any time in **Access management > Applications**.
- It uses the Freebox OS Profile API (`network_control`). To change a profile, it sends back the whole profile with its device list, as Freebox OS does, so a profile is never emptied.
- Plannings are still edited in Freebox OS; the integration handles overrides (pauses and temporary allowances).

## Troubleshooting

- **"Cannot reach the Freebox"**: check that Home Assistant is on the box local network. On a certificate error, retry with "Verify the Freebox certificate" unticked (not recommended long term).
- **"Permission missing" alert**: see step 4 of the configuration.
- **No request shows on the box**: add the integration again; a request expires after about 2 minutes.
- **Access revoked**: Home Assistant offers to re-authenticate; accept the request on the box again.
- **Debug logs**:

```yaml
logger:
  logs:
    custom_components.freebox_profiles: debug
```

**Diagnostics** (integration page > ⋮ > Download diagnostics) hide tokens, MAC addresses and names: you can attach them to an issue.

## Contributing

Issues and pull requests are welcome, especially compatibility reports for other Freebox models.

## License

MIT, see [LICENSE](LICENSE).
