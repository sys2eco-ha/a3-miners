"""A3 Miners integration."""

from __future__ import annotations

import json
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONFIG_FILE, DOMAIN, PLATFORMS
from .coordinator import A3Coordinator


async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    """Set up A3 Miners from its configuration entry."""
    path = Path(hass.config.path(CONFIG_FILE))
    try:
        miners = json.loads(await hass.async_add_executor_job(path.read_text))
    except (OSError, json.JSONDecodeError) as err:
        raise ConfigEntryNotReady(f"Cannot load {path}: {err}") from err

    if not isinstance(miners, dict) or not miners:
        raise ConfigEntryNotReady(f"{path} must contain at least one miner")

    for slot, miner in miners.items():
        if not isinstance(miner, dict) or not isinstance(miner.get("host"), str):
            raise ConfigEntryNotReady(f"{path}: {slot} requires a host")
        miner.setdefault("name", slot.replace("_", " ").title())

    coordinator = A3Coordinator(hass, miners, entry.options.get("scan_interval", 10))
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Unload A3 Miners."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
