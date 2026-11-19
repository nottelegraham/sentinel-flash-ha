"""Constants for the Sentinel Flash integration."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "sentinel_flash"
CONF_BRIDGES = "bridges"

SCAN_INTERVAL = timedelta(seconds=30)
REQUEST_TIMEOUT = 10
# Missed polls tolerated before a bridge counts as offline. A bridge restarting
# after a firmware update is gone for one poll; it shouldn't flash Offline for that.
MISSES_BEFORE_OFFLINE = 2

SIGNAL_NEW_BRIDGE = "sentinel_flash_new_bridge_{}"

CARD_NAME = "sentinel-flash-bridges-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_NAME}"

# Bridge USB device states (firmware bridge.h)
STATES = {0: "Nothing connected", 1: "Connected", 2: "Bootloader", 3: "Unknown USB device"}

# GHL product numbers (register 2), same table as the bridge's own page.
PRODUCTS = {
    20: "ProfiLux Mini", 21: "ProfiLux Light", 22: "ProfiLux Terra", 23: "ProfiLux 4",
    24: "ProfiLux Mini WiFi", 25: "ProfiLux Light WiFi", 26: "ProfiLux Terra WiFi",
    27: "ProfiLux 4e", 63: "ProfiLux 4.1",
    68: "ProfiLux Mini WiFi 2", 69: "ProfiLux Light WiFi 2", 70: "ProfiLux Terra WiFi 2",
    50: "GHL Doser 2", 51: "GHL Doser 2 Maxi", 52: "GHL Doser 2.2", 53: "GHL Doser 2.2 Maxi",
    54: "GHL Doser 2.2e", 56: "GHL Doser 2 (IL)", 57: "GHL Doser 2 Maxi (IL)",
    59: "GHL Doser 3", 60: "GHL Doser 3 Maxi", 61: "GHL Doser 3", 62: "GHL Doser 3",
    206: "GHL Doser 2/2.1 EXT", 208: "GHL Doser Maxi EXT", 213: "GHL Doser 2.2 EXT",
    214: "GHL Doser Maxi 2.2 EXT", 215: "GHL Doser 2.2e EXT",
    200: "Powerbar 6D-PAB", 201: "Powerbar 6D-PAB", 202: "Powerbar 6D-PAB",
    203: "Powerbar 5.1-PAB", 204: "Expansion Box", 205: "Expansion Box 2",
    207: "KH Director", 209: "SMS Module", 210: "Powerbar 6E-PAB", 211: "ION Director",
    212: "Versia Controller",
    223: "GHL Doser 3 EXT", 224: "GHL Doser 3 EXT", 225: "GHL Doser 3 EXT", 226: "GHL Doser 3 EXT",
    100: "Mitras LX 6000", 101: "Mitras LX 6100", 102: "Mitras LX 6100HV",
    103: "Mitras LX 6200HV", 106: "Mitras LX 6300", 107: "Mitras LX 6400",
    104: "Mitras LX 7006", 105: "Mitras LX 7206", 108: "Mitras LX 7004", 109: "Mitras LX 7204",
    110: "Mitras LX 7404", 111: "Mitras LX 7406", 112: "Mitras LX 7504", 113: "Mitras LX 7506",
    114: "Mitras LX 7006 IL", 115: "Mitras LX 7206 IL", 116: "Mitras LX 7406 IL",
    117: "Mitras LX 7506 IL",
}
