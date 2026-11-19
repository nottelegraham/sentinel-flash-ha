"""Sentinel Flash: finds every Sentinel Flash bridge on the network and shows its status.

One config entry holds all bridges. Bridges announce themselves with mDNS
(_sentinelflash._tcp, firmware 0.13.5 and later); each one found after the first
is added automatically. A bridge that goes away stays, shown as offline.
Read-only: the only request made to a bridge is GET /api/status.
"""
from __future__ import annotations

import logging
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
VERSION = "0.1.1"
_LOGGER = logging.getLogger(__name__)

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


def bridge_from_service(name: str, port: int | None, addresses: list[str],
                        properties: dict[Any, Any]) -> dict[str, Any] | None:
    """Bridge record from an mDNS _sentinelflash._tcp answer, or None if it isn't one."""
    props: dict[str, str] = {}
    for k, v in (properties or {}).items():
        if v is None:
            continue
        key = k.decode() if isinstance(k, bytes) else str(k)
        props[key.lower()] = v.decode(errors="replace") if isinstance(v, bytes) else str(v)
    bid = props.get("id", "").lower()
    if len(bid) != 12 or any(c not in "0123456789abcdef" for c in bid):
        return None
    ipv4 = [a for a in addresses if ":" not in a]
    if not ipv4:
        return None
    return {"id": bid, "host": ipv4[0], "port": int(port or 80),
            "name": name.split("._sentinelflash", 1)[0], "hw": props.get("hw", "")}


async def _async_watch_network(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Watch for _sentinelflash._tcp the whole time the integration runs, using
    Home Assistant's own mDNS listener. Every bridge seen is added (or its new
    address recorded) at once; no setup flow is involved, so nothing is lost
    when several bridges appear together."""
    from homeassistant.components import zeroconf as ha_zc
    from zeroconf import ServiceStateChange
    from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo

    aiozc = await ha_zc.async_get_async_instance(hass)
    stype = "_sentinelflash._tcp.local."

    async def resolve(name: str) -> None:
        info = AsyncServiceInfo(stype, name)
        if not await info.async_request(aiozc.zeroconf, 3000):
            return
        bridge = bridge_from_service(name, info.port, info.parsed_scoped_addresses(), info.properties)
        if bridge is not None:
            await async_add_or_update_bridge(hass, entry, bridge)

    def on_change(zeroconf, service_type: str, name: str, state_change: ServiceStateChange) -> None:
        if state_change in (ServiceStateChange.Added, ServiceStateChange.Updated):
            hass.loop.call_soon_threadsafe(
                lambda: entry.async_create_background_task(hass, resolve(name), f"{DOMAIN} resolve {name}"))

    browser = AsyncServiceBrowser(aiozc.zeroconf, [stype], handlers=[on_change])

    async def stop() -> None:
        await browser.async_cancel()

    entry.async_on_unload(stop)


async def async_setup_entry(hass: HomeAssistant, entry: SentinelFlashConfigEntry) -> bool:
    entry.runtime_data = {}
    for bridge in entry.data.get(CONF_BRIDGES, {}).values():
        await _async_start_bridge(hass, entry, bridge)
    await _async_register_card(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    try:
        await _async_watch_network(hass, entry)
    except Exception:  # noqa: BLE001 - discovery is a convenience; bridges already added keep working
        _LOGGER.exception("Could not start watching for Sentinel Flash bridges")
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
