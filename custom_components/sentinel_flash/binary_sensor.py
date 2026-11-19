"""Online sensor: on while the bridge answers. Never unavailable, so automations
and the dashboard card can rely on it."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SentinelFlashConfigEntry
from .const import SIGNAL_NEW_BRIDGE
from .coordinator import BridgeCoordinator
from .entity import BridgeEntity


async def async_setup_entry(hass: HomeAssistant, entry: SentinelFlashConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities(OnlineSensor(c) for c in entry.runtime_data.values())

    @callback
    def new_bridge(coord: BridgeCoordinator) -> None:
        async_add_entities([OnlineSensor(coord)])

    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_NEW_BRIDGE.format(entry.entry_id), new_bridge))


class OnlineSensor(BridgeEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coord: BridgeCoordinator) -> None:
        super().__init__(coord, "online")

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.online

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return {"url": self.coordinator.url + "/"}
