"""Sentinel Flash: finds every Sentinel Flash bridge on the network and shows its status.

One config entry holds all bridges. Bridges announce themselves with mDNS
(_sentinelflash._tcp, firmware 0.13.5 and later); each one found after the first
is added automatically. A bridge that goes away stays, shown as offline.
Read-only: the only request made to a bridge is GET /api/status.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import CARD_NAME, CARD_URL, CONF_BRIDGES, DOMAIN, SIGNAL_NEW_BRIDGE
from .coordinator import BridgeCoordinator
from .lovelace_resource import _collection, async_register_resource

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]
VERSION = "0.1.0"

type SentinelFlashConfigEntry = ConfigEntry[dict[str, BridgeCoordinator]]


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the bridges card and load it on every dashboard (as a dashboard
    resource, so the phone apps get the current copy)."""
    if hass.data.get(f"{DOMAIN}_card"):
        return
    hass.data[f"{DOMAIN}_card"] = True
    path = Path(__file__).parent / "www" / CARD_NAME
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(path), False)])
    url = f"{CARD_URL}?v={VERSION}"
    if _collection(hass) is not None:
        async_register_resource(hass, CARD_URL, url)
    else:
        add_extra_js_url(hass, url)
        add_extra_js_url(hass, url, es5=True)


@callback
def _track_device(hass: HomeAssistant, entry: ConfigEntry, coord: BridgeCoordinator) -> None:
    """Keep the device's firmware version, model and link current after updates."""
    def update() -> None:
        if not coord.data:
            return
        reg = dr.async_get(hass)
        dev = reg.async_get_device(identifiers={(DOMAIN, coord.bridge_id)})
        if dev is None:
            return
        board = (coord.data.get("board") or {}).get("type") or coord.bridge.get("hw")
        changes: dict[str, Any] = {}
        version = (coord.data.get("bridge") or {}).get("version")
        if version and dev.sw_version != version:
            changes["sw_version"] = version
        model = "Sentinel Flash Shift" if board == "shift" else "Sentinel Flash DevKit"
        if dev.model != model:
            changes["model"] = model
        if dev.configuration_url != coord.url + "/":
            changes["configuration_url"] = coord.url + "/"
        if changes:
            reg.async_update_device(dev.id, **changes)

    entry.async_on_unload(coord.async_add_listener(update))


async def _async_start_bridge(hass: HomeAssistant, entry: ConfigEntry, bridge: dict[str, Any]) -> BridgeCoordinator:
    coord = BridgeCoordinator(hass, entry, bridge)
    entry.runtime_data[coord.bridge_id] = coord
    # A bridge that is off right now must not stop the others: plain refresh, no
    # ConfigEntryNotReady. It shows as offline until it answers.
    await coord.async_refresh()
    _track_device(hass, entry, coord)
    return coord


async def async_setup_entry(hass: HomeAssistant, entry: SentinelFlashConfigEntry) -> bool:
    entry.runtime_data = {}
    for bridge in entry.data.get(CONF_BRIDGES, {}).values():
        await _async_start_bridge(hass, entry, bridge)
    await _async_register_card(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SentinelFlashConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(hass: HomeAssistant, entry: SentinelFlashConfigEntry,
                                           device: dr.DeviceEntry) -> bool:
    """Delete on a bridge's device page: forget the bridge. If it is still on the
    network and announcing itself, discovery adds it back."""
    ids = {i for d, i in device.identifiers if d == DOMAIN}
    bridges = {k: v for k, v in entry.data.get(CONF_BRIDGES, {}).items() if k not in ids}
    hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_BRIDGES: bridges})
    coords = getattr(entry, "runtime_data", None)
    if isinstance(coords, dict):
        for bid in ids:
            coords.pop(bid, None)
    return True


async def async_add_or_update_bridge(hass: HomeAssistant, entry: ConfigEntry, bridge: dict[str, Any]) -> str:
    """Record a bridge seen by discovery (or added by hand). Returns "added",
    "moved" (new address) or "known"."""
    bridges = dict(entry.data.get(CONF_BRIDGES, {}))
    # A bridge added by address before it ran discovery firmware is keyed by its name;
    # when it later announces itself, keep that record (and its entities).
    by_name = "name-" + "".join(c for c in bridge["name"].lower() if c.isalnum() or c == "-")
    if bridge["id"] not in bridges and by_name in bridges:
        bridge = {**bridge, "mac": bridge["id"], "id": by_name}
    old = bridges.get(bridge["id"])
    if old and old.get("host") == bridge["host"] and old.get("port") == bridge["port"]:
        return "known"
    merged = {**(old or {}), **bridge}
    if old:  # keep the name the bridge was first added with; HA shows the user's rename anyway
        merged["name"] = old.get("name", bridge["name"])
    bridges[bridge["id"]] = merged
    hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_BRIDGES: bridges})

    coords: dict[str, BridgeCoordinator] | None = getattr(entry, "runtime_data", None)
    if not isinstance(coords, dict):  # entry not loaded (disabled, or still starting)
        return "moved" if old else "added"
    if bridge["id"] in coords:
        coord = coords[bridge["id"]]
        coord.set_address(bridge["host"], bridge["port"])
        await coord.async_request_refresh()
        return "moved"
    coord = await _async_start_bridge(hass, entry, merged)
    async_dispatcher_send(hass, SIGNAL_NEW_BRIDGE.format(entry.entry_id), coord)
    return "added"
