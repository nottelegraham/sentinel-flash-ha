"""Config flow: one entry for all bridges.

The first bridge found asks once ("Set up Sentinel Flash?"). After that, every
bridge discovery adds or updates that bridge in the existing entry and ends
without asking. Bridges on firmware older than 0.13.5 don't announce
themselves; add those by address (setup form, or Configure on the entry).
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

try:
    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
except ImportError:  # HA before 2025.1
    from homeassistant.components.zeroconf import ZeroconfServiceInfo

from .const import CONF_BRIDGES, DOMAIN, REQUEST_TIMEOUT

TITLE = "Sentinel Flash"
_ID = re.compile(r"[0-9a-f]{12}")
_HOST = re.compile(r"[A-Za-z0-9.\-]{1,253}(:[0-9]{1,5})?")


def _bridge_from_zeroconf(info: ZeroconfServiceInfo) -> dict[str, Any] | None:
    props = {str(k).lower(): str(v) for k, v in (info.properties or {}).items() if v is not None}
    bid = props.get("id", "").lower()
    if not _ID.fullmatch(bid):
        return None
    name = info.name.split("._sentinelflash", 1)[0] or (info.hostname or "").split(".")[0]
    return {"id": bid, "host": str(info.ip_address), "port": int(info.port or 80),
            "name": name, "hw": props.get("hw", "")}


async def _probe(hass: HomeAssistant, address: str) -> dict[str, Any] | None:
    """Ask a bridge typed by hand for its status; build a bridge record from it."""
    host, _, port = address.partition(":")
    port_n = int(port) if port else 80
    url = f"http://{host}" + ("" if port_n == 80 else f":{port_n}") + "/api/status"
    try:
        async with asyncio.timeout(REQUEST_TIMEOUT):
            resp = await async_get_clientsession(hass).get(url)
            resp.raise_for_status()
            data = await resp.json(content_type=None)
        bridge = data["bridge"]
        dev = data["device"]
    except (aiohttp.ClientError, TimeoutError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(bridge, dict) or not isinstance(dev, dict) or "version" not in bridge:
        return None
    name = str(bridge.get("host") or host.split(".")[0])
    # Old firmware has no MAC in /api/status; the bridge name is unique per bridge
    # (ghl-bridge-<MAC end> by default), so it keys the record until discovery
    # supplies the MAC.
    bid = "name-" + re.sub(r"[^a-z0-9-]", "", name.lower())
    board = (data.get("board") or {}).get("type", "")
    return {"id": bid, "host": host, "port": port_n, "name": name, "hw": board}


class SentinelFlashConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._bridge: dict[str, Any] | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return AddBridgeOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        errors: dict[str, str] = {}
        if user_input is not None:
            bridges: dict[str, Any] = {}
            address = user_input.get(CONF_HOST, "").strip()
            if address:
                bridge = await _probe(self.hass, address) if _HOST.fullmatch(address) else None
                if bridge is None:
                    errors[CONF_HOST] = "cannot_connect"
                else:
                    bridges[bridge["id"]] = bridge
            if not errors:
                return self.async_create_entry(title=TITLE, data={CONF_BRIDGES: bridges})
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Optional(CONF_HOST, default=""): str}),
            errors=errors,
        )

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        bridge = _bridge_from_zeroconf(discovery_info)
        if bridge is None:
            return self.async_abort(reason="not_sentinel_flash")
        entries = self._async_current_entries(include_ignore=False)
        if entries:
            from . import async_add_or_update_bridge  # noqa: PLC0415
            await async_add_or_update_bridge(self.hass, entries[0], bridge)
            return self.async_abort(reason="already_configured")
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()  # also honors "Ignore"
        self._bridge = bridge
        self.context["title_placeholders"] = {"name": bridge["name"]}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if self._bridge is None:
            return self.async_abort(reason="not_sentinel_flash")
        if user_input is not None:
            return self.async_create_entry(title=TITLE, data={CONF_BRIDGES: {self._bridge["id"]: self._bridge}})
        self._set_confirm_only()
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": self._bridge["name"]},
        )


class AddBridgeOptionsFlow(OptionsFlow):
    """Configure → add a bridge by address (for firmware without discovery)."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            address = user_input.get(CONF_HOST, "").strip()
            bridge = await _probe(self.hass, address) if _HOST.fullmatch(address) else None
            if bridge is None:
                errors[CONF_HOST] = "cannot_connect"
            else:
                from . import async_add_or_update_bridge  # noqa: PLC0415
                await async_add_or_update_bridge(self.hass, self.config_entry, bridge)
                return self.async_create_entry(data=dict(self.config_entry.options))
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )
