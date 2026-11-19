"""Base entity: one HA device per bridge."""
from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo, format_mac
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BridgeCoordinator


class BridgeEntity(CoordinatorEntity[BridgeCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coord: BridgeCoordinator, key: str) -> None:
        super().__init__(coord)
        self._attr_unique_id = f"{coord.bridge_id}_{key}"
        self._attr_translation_key = key
        mac = coord.bridge.get("mac") or coord.bridge_id
        board = ((coord.data or {}).get("board") or {}).get("type") or coord.bridge.get("hw")
        info = DeviceInfo(
            identifiers={(DOMAIN, coord.bridge_id)},
            name=coord.bridge["name"],
            manufacturer="TelegrahamTested",
            model="Sentinel Flash Shift" if board == "shift" else "Sentinel Flash DevKit",
            sw_version=((coord.data or {}).get("bridge") or {}).get("version"),
            configuration_url=coord.url + "/",
        )
        if len(mac) == 12 and all(c in "0123456789abcdef" for c in mac):
            info["connections"] = {(CONNECTION_NETWORK_MAC, format_mac(mac))}
        self._attr_device_info = info

    @property
    def available(self) -> bool:
        return self.coordinator.online
