# Sentinel Flash for Home Assistant

Finds every [Sentinel Flash](https://flash.ttsentinel.com) bridge on your network and shows its status in Home Assistant. Read-only: the only request it makes to a bridge is `GET /api/status`.

## What you get

- **Automatic discovery.** Bridges on firmware 0.13.5 or later announce themselves (mDNS `_sentinelflash._tcp`). The first one found asks once, "Set up Sentinel Flash?"; every bridge after that is added on its own. A bridge that changes IP address is followed.
- **One device per bridge**, with:
  - **Online**: on while the bridge answers. One missed poll is tolerated (a restart after an update), so it turns off after about a minute without an answer. This entity is never unavailable.
  - **Connected device**: the GHL device on the bridge's USB port (for example *ProfiLux Mini WiFi*), with its firmware and serial as attributes.
  - **Active port**: Shift only.
  - **Bridge firmware**: diagnostic.
- **Bridges card**: one tile per bridge, drawn from the integration itself, so new bridges appear without editing the dashboard. Online bridges first, offline ones dimmed with how long they've been gone. **Open** opens the bridge's page, which needs your phone or computer on the home network. **Details** opens the device page. It uses a light theme and works on a phone and a computer.

Bridges that go away are kept and shown as offline, never deleted. To remove one, delete its device in Home Assistant.

## Install

1. HACS → Integrations → ⋮ → Custom repositories → add this repository as an *Integration*, then install **Sentinel Flash**. Restart Home Assistant.
2. Settings → Devices & services: your bridges show up as **Discovered: Sentinel Flash**. Click **Add** once.
3. Add the card to any dashboard:

```yaml
type: custom:sentinel-flash-bridges-card
title: Sentinel Flash        # optional
show_offline: true           # optional
```

The card file is served by the integration and registered as a dashboard resource automatically.

### Bridges on older firmware

Before 0.13.5 a bridge doesn't announce itself. Add it by address from the setup form, or later with **Configure** on the Sentinel Flash entry. When the bridge is updated to 0.13.5, discovery takes over the same record.

## License

PolyForm Noncommercial 1.0.0. Selling this software, or any part of it, requires written permission from TelegrahamTested. See [LICENSE](LICENSE).
