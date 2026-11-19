"""Discovery, auto-add, entities and offline handling against a real HA test instance."""
from datetime import timedelta
from ipaddress import ip_address
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

try:
    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
except ImportError:
    from homeassistant.components.zeroconf import ZeroconfServiceInfo

import custom_components.sentinel_flash  # noqa: F401  (so patch() can find it)

DOMAIN = "sentinel_flash"


def status(host, version="0.13.5", board=None, product=24, state=1):
    return {"bridge": {"name": "GHL Bridge", "host": host, "version": version, "slot": "ota_0", "uptime": 5},
            "wifi": {"connected": True}, "device": {"state": state, "product": product, "firmware": 123,
            "serial": 4242, "connecting": False}, "job": {"running": False}, "log": ["x"] * 50,
            "board": board or {"type": "devkit"}}


def zc(name, ip, mid, hw="devkit"):
    return ZeroconfServiceInfo(ip_address=ip_address(ip), ip_addresses=[ip_address(ip)], port=80,
                               hostname=f"{name}.local.", type="_sentinelflash._tcp.local.",
                               name=f"{name}._sentinelflash._tcp.local.",
                               properties={"id": mid, "fw": "0.13.5", "hw": hw, "api": "/api/status"})


async def _patch_noresource(hass):
    pass


async def test_discovery_then_auto_add(hass, aioclient_mock):
    aioclient_mock.get("http://192.168.1.50/api/status", json=status("ghl-bridge-test"))
    aioclient_mock.get("http://192.168.1.51/api/status",
                       json=status("ghl-bridge-test-01-06e0", board={"type": "shift", "port": 2}, product=51))
    with patch("custom_components.sentinel_flash._async_register_card"):
        r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF},
                                                      data=zc("ghl-bridge-test", "192.168.1.50", "0a1b2c3d4e5f"))
        assert r["type"] is FlowResultType.FORM and r["step_id"] == "zeroconf_confirm"
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {})
        assert r["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()

        assert hass.states.get("binary_sensor.ghl_bridge_test_online").state == "on"
        assert hass.states.get("sensor.ghl_bridge_test_connected_device").state == "ProfiLux Mini WiFi"
        assert hass.states.get("sensor.ghl_bridge_test_connected_device").attributes["device_firmware"] == "1.23"
        assert hass.states.get("sensor.ghl_bridge_test_bridge_firmware").state == "0.13.5"
        assert hass.states.get("sensor.ghl_bridge_test_active_port") is None  # DevKit

        # Second bridge: no question, added to the same entry.
        r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF},
                                                      data=zc("ghl-bridge-test-01-06e0", "192.168.1.51", "aabbccdd06e0", "shift"))
        assert r["type"] is FlowResultType.ABORT and r["reason"] == "already_configured"
        await hass.async_block_till_done()
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1
        assert hass.states.get("binary_sensor.ghl_bridge_test_01_06e0_online").state == "on"
        assert hass.states.get("sensor.ghl_bridge_test_01_06e0_connected_device").state == "GHL Doser 2 Maxi"
        assert hass.states.get("sensor.ghl_bridge_test_01_06e0_active_port").state == "2"

        # Same bridge rediscovered at a new address: record moves, nothing duplicated.
        aioclient_mock.get("http://192.168.1.77/api/status", json=status("ghl-bridge-test"))
        await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF},
                                                  data=zc("ghl-bridge-test", "192.168.1.77", "0a1b2c3d4e5f"))
        await hass.async_block_till_done()
        entry = hass.config_entries.async_entries(DOMAIN)[0]
        assert entry.data["bridges"]["0a1b2c3d4e5f"]["host"] == "192.168.1.77"
        assert len(entry.data["bridges"]) == 2


async def test_offline_after_two_misses(hass, aioclient_mock):
    aioclient_mock.get("http://192.168.1.50/api/status", json=status("ghl-bridge-test"))
    with patch("custom_components.sentinel_flash._async_register_card"):
        r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF},
                                                      data=zc("ghl-bridge-test", "192.168.1.50", "0a1b2c3d4e5f"))
        await hass.config_entries.flow.async_configure(r["flow_id"], {})
        await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.ghl_bridge_test_online").state == "on"
    aioclient_mock.clear_requests()
    aioclient_mock.get("http://192.168.1.50/api/status", exc=TimeoutError())
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.ghl_bridge_test_online").state == "on"  # one miss tolerated
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=62))
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.ghl_bridge_test_online").state == "off"
    assert hass.states.get("sensor.ghl_bridge_test_connected_device").state == "unavailable"


async def test_offline_bridge_does_not_block_setup(hass, aioclient_mock):
    aioclient_mock.get("http://192.168.1.50/api/status", exc=TimeoutError())
    with patch("custom_components.sentinel_flash._async_register_card"):
        r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF},
                                                      data=zc("ghl-bridge-test", "192.168.1.50", "0a1b2c3d4e5f"))
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {})
        await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert hass.states.get("binary_sensor.ghl_bridge_test_online").state == "off"


async def test_manual_add_old_firmware_then_discovery_merges(hass, aioclient_mock):
    aioclient_mock.get("http://ghl-bridge-1a2b.local/api/status", json=status("ghl-bridge-1a2b", version="0.13.4"))
    with patch("custom_components.sentinel_flash._async_register_card"):
        r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"host": "ghl-bridge-1a2b.local"})
        assert r["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        assert hass.states.get("sensor.ghl_bridge_1a2b_bridge_firmware").state == "0.13.4"
        aioclient_mock.get("http://192.168.1.60/api/status", json=status("ghl-bridge-1a2b"))
        await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF},
                                                  data=zc("ghl-bridge-1a2b", "192.168.1.60", "001122331a2b"))
        await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert list(entry.data["bridges"]) == ["name-ghl-bridge-1a2b"]
    assert entry.data["bridges"]["name-ghl-bridge-1a2b"]["host"] == "192.168.1.60"


async def test_bad_announcement_ignored(hass):
    info = zc("x", "192.168.1.9", "nothex")
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=info)
    assert r["type"] is FlowResultType.ABORT and r["reason"] == "not_sentinel_flash"


async def test_delete_device_forgets_bridge(hass, aioclient_mock):
    from homeassistant.helpers import device_registry as dr
    from custom_components.sentinel_flash import async_remove_config_entry_device
    aioclient_mock.get("http://192.168.1.50/api/status", json=status("ghl-bridge-test"))
    with patch("custom_components.sentinel_flash._async_register_card"):
        r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF},
                                                      data=zc("ghl-bridge-test", "192.168.1.50", "0a1b2c3d4e5f"))
        await hass.config_entries.flow.async_configure(r["flow_id"], {})
        await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    dev = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "0a1b2c3d4e5f")})
    assert await async_remove_config_entry_device(hass, entry, dev)
    assert entry.data["bridges"] == {}


async def test_options_add_by_address(hass, aioclient_mock):
    aioclient_mock.get("http://192.168.1.50/api/status", json=status("ghl-bridge-test"))
    aioclient_mock.get("http://ghl-bridge-1a2b.local/api/status", json=status("ghl-bridge-1a2b", version="0.13.4"))
    with patch("custom_components.sentinel_flash._async_register_card"):
        r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF},
                                                      data=zc("ghl-bridge-test", "192.168.1.50", "0a1b2c3d4e5f"))
        await hass.config_entries.flow.async_configure(r["flow_id"], {})
        await hass.async_block_till_done()
        entry = hass.config_entries.async_entries(DOMAIN)[0]
        aioclient_mock.get("http://nope.invalid/api/status", exc=TimeoutError())
        r = await hass.config_entries.options.async_init(entry.entry_id)
        r = await hass.config_entries.options.async_configure(r["flow_id"], {"host": "nope.invalid"})
        assert r["errors"] == {"host": "cannot_connect"}
        r = await hass.config_entries.options.async_configure(r["flow_id"], {"host": "ghl-bridge-1a2b.local"})
        assert r["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.ghl_bridge_1a2b_online").state == "on"
    assert len(entry.data["bridges"]) == 2
