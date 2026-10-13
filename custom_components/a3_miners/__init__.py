"""A3 Miners integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_HOST,
    CONF_IP_CHANGED,
    CONF_MAC,
    CONF_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MINERS,
    PLATFORMS,
)
from .coordinator import A3Coordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up A3 Miners from its configuration entry."""
    miners = {}
    for slot, record in (entry.data.get(MINERS) or {}).items():
        if not isinstance(record, dict) or not isinstance(record.get(CONF_HOST), str):
            _LOGGER.warning("Ignoring miner %s: no host configured", slot)
            continue
        miners[slot] = {
            CONF_NAME: record.get(CONF_NAME) or slot,
            CONF_HOST: record[CONF_HOST],
            CONF_MAC: record.get(CONF_MAC),
            CONF_IP_CHANGED: record.get(CONF_IP_CHANGED, False),
        }

    coordinator = A3Coordinator(hass, entry, miners, DEFAULT_SCAN_INTERVAL)
    if miners:
        await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload A3 Miners."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
