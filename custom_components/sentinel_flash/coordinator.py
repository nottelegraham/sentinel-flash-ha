"""One coordinator per bridge: polls GET /api/status (read-only)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import MISSES_BEFORE_OFFLINE, REQUEST_TIMEOUT, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class BridgeCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Status of one Sentinel Flash bridge."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, bridge: dict[str, Any]) -> None:
        super().__init__(
            hass, _LOGGER, config_entry=entry,
            name=f"Sentinel Flash {bridge['name']}", update_interval=SCAN_INTERVAL,
        )
        self.bridge = dict(bridge)
        self._session = async_get_clientsession(hass)
        self._misses = 0

    @property
    def bridge_id(self) -> str:
        return self.bridge["id"]

    @property
    def url(self) -> str:
        port = int(self.bridge.get("port") or 80)
        return f"http://{self.bridge['host']}" + ("" if port == 80 else f":{port}")

    @property
    def online(self) -> bool:
        return self.last_update_success and self.data is not None

    def set_address(self, host: str, port: int) -> bool:
        """New address from discovery. Returns True if it changed."""
        if host == self.bridge.get("host") and port == self.bridge.get("port"):
            return False
        self.bridge["host"], self.bridge["port"] = host, port
        return True

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                resp = await self._session.get(f"{self.url}/api/status")
                resp.raise_for_status()
                data = await resp.json(content_type=None)
            if not isinstance(data, dict) or "bridge" not in data or "device" not in data:
                raise ValueError("not a Sentinel Flash status answer")
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            self._misses += 1
            # Tolerate a short gap (a restart after an update) before reporting offline.
            if self.data is not None and self._misses < MISSES_BEFORE_OFFLINE:
                return self.data
            raise UpdateFailed(f"{self.bridge['name']} did not answer: {err}") from err
        self._misses = 0
        # The bridge log and PAB recovery data are large and not used here.
        data.pop("log", None)
        data.pop("pabRecovery", None)
        return data
