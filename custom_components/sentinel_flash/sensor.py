"""Sensors per bridge: the GHL device on its USB port, the bridge firmware, and
(Shift only) the active USB port."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SentinelFlashConfigEntry
from .const import PRODUCTS, SIGNAL_NEW_BRIDGE, STATES
from .coordinator import BridgeCoordinator
from .entity import BridgeEntity


def _is_shift(coord: BridgeCoordinator) -> bool:
    board = ((coord.data or {}).get("board") or {}).get("type") or coord.bridge.get("hw")
    return board == "shift"


def _entities(coord: BridgeCoordinator) -> list[SensorEntity]:
    out: list[SensorEntity] = [ConnectedDeviceSensor(coord), FirmwareSensor(coord)]
    if _is_shift(coord):
        out.append(ActivePortSensor(coord))
    return out


async def async_setup_entry(hass: HomeAssistant, entry: SentinelFlashConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities(e for c in entry.runtime_data.values() for e in _entities(c))

    @callback
    def new_bridge(coord: BridgeCoordinator) -> None:
        async_add_entities(_entities(coord))

    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_NEW_BRIDGE.format(entry.entry_id), new_bridge))


def _fw(value: Any) -> str | None:
    """GHL register 0 is the firmware version x100 (123 -> 1.23)."""
    return f"{value / 100:.2f}" if isinstance(value, int) and value > 0 else None


class ConnectedDeviceSensor(BridgeEntity, SensorEntity):
    _attr_icon = "mdi:usb"

    def __init__(self, coord: BridgeCoordinator) -> None:
        super().__init__(coord, "connected_device")

    @property
    def native_value(self) -> str | None:
        dev = (self.coordinator.data or {}).get("device") or {}
        state = dev.get("state")
        if dev.get("connecting"):
            return "Connecting"
        if state == 1:
            product = dev.get("product")
            return PRODUCTS.get(product, f"GHL product {product}") if isinstance(product, int) and product >= 0 else "GHL device"
        return STATES.get(state, "Unknown")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        dev = (self.coordinator.data or {}).get("device") or {}
        attrs: dict[str, Any] = {"device_firmware": _fw(dev.get("firmware")),
                                 "product_number": dev.get("product"),
                                 "serial": dev.get("serial") or None}
        job = (self.coordinator.data or {}).get("job")
        if isinstance(job, dict):
            attrs["job_running"] = bool(job.get("running"))
        return attrs


class FirmwareSensor(BridgeEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:chip"

    def __init__(self, coord: BridgeCoordinator) -> None:
        super().__init__(coord, "firmware")

    @property
    def native_value(self) -> str | None:
        return ((self.coordinator.data or {}).get("bridge") or {}).get("version")


class ActivePortSensor(BridgeEntity, SensorEntity):
    _attr_icon = "mdi:swap-horizontal"

    def __init__(self, coord: BridgeCoordinator) -> None:
        super().__init__(coord, "active_port")

    @property
    def native_value(self) -> int | None:
        port = ((self.coordinator.data or {}).get("board") or {}).get("port")
        return port if isinstance(port, int) and port > 0 else None
