"""Polling and parsing for stock Antminer A3 miners."""

from __future__ import annotations

import asyncio
import logging
import re
import urllib.request

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_PATH,
    DEFAULT_PASSWORD,
    DEFAULT_USERNAME,
    DOMAIN,
    NETWORK_PATH,
    OVERHEAT_TEMPERATURE,
)


def _value(text: str, pattern: str, cast=str):
    match = re.search(pattern, text)
    if not match:
        return None
    try:
        return cast(match.group(1).strip())
    except ValueError:
        return None


def _pool_value(block: str, key: str, cast=str):
    return _value(block, rf"(?:^|,){re.escape(key)}=([^,|]*)", cast)


def _parse_status(text: str) -> dict:
    pool_match = re.search(r"POOL=0,(.*?)(?:\|POOL=1|\Z)", text, re.S)
    pool = pool_match.group(1) if pool_match else ""
    asic_status = "".join(re.findall(r"chain_acs[123]=([^,]*)", text))
    chip_temperatures = [int(item) for item in re.findall(r"temp2_[123]=([0-9]+)", text)]

    data = {
        "hashrate": _value(text, r"GHS 5s=([0-9.]+)", float),
        "hashrate_average": _value(text, r"GHS av=([0-9.]+)", float),
        "pcb_temperature": _value(text, r"temp_max=([0-9]+)", int),
        "chip_temperature": max(chip_temperatures) if chip_temperatures else None,
        "fan1": _value(text, r"fan1=([0-9]+)", int),
        "fan2": _value(text, r"fan2=([0-9]+)", int),
        "frequency": _value(text, r"frequency=([0-9]+)", int),
        "uptime": _value(text, r"Elapsed=([0-9]+)", int),
        "hardware_errors": _value(text, r"Hardware Errors=([0-9]+)", int),
        "asic_ok": asic_status.count("o"),
        "asic_bad": asic_status.count("x"),
        "pool_url": _pool_value(pool, "URL"),
        "pool_worker": _pool_value(pool, "User"),
        "pool_status": _pool_value(pool, "Status"),
        "pool_difficulty": _pool_value(pool, "Diff", float),
        "last_share": _pool_value(pool, "Last Share Time"),
        "accepted": _pool_value(pool, "Accepted", int),
        "rejected": _pool_value(pool, "Rejected", int),
        "stale": _pool_value(pool, "Stale", int),
        "discarded": _pool_value(pool, "Discarded", int),
    }
    data["overheat"] = bool(
        data["pcb_temperature"] is not None
        and data["pcb_temperature"] >= OVERHEAT_TEMPERATURE
    )
    data["chain_fault"] = data["asic_bad"] > 0
    data["not_hashing"] = (data["hashrate"] or 0) < 1
    data["pool_down"] = data["pool_status"] != "Alive"
    return data


def _fetch(host: str, path: str) -> str:
    url = f"http://{host}{path}"
    password_manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    password_manager.add_password(None, url, DEFAULT_USERNAME, DEFAULT_PASSWORD)
    opener = urllib.request.build_opener(
        urllib.request.HTTPDigestAuthHandler(password_manager)
    )
    with opener.open(url, timeout=5) as response:
        return response.read().decode("utf-8", "replace")


def poll_miner(host: str, mac: str | None = None) -> dict:
    data = _parse_status(_fetch(host, API_PATH))
    data["host"] = host
    if mac is None:
        try:
            network = _fetch(host, NETWORK_PATH)
            mac = _value(network, r'"macaddr":"([^"]+)"')
        except (HTTPError, URLError, OSError):
            mac = None
    data["mac"] = mac
    data["reachable"] = True
    return data


class A3Coordinator(DataUpdateCoordinator):
    """Fetch every configured miner once per update."""

    def __init__(self, hass, miners: dict, interval: int) -> None:
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.miners = miners
        self.macs = {}

    async def _async_poll(self, slot: str, config: dict) -> tuple[str, dict]:
        host = config["host"]
        try:
            result = await self.hass.async_add_executor_job(
                poll_miner, host, self.macs.get(slot)
            )
            if result.get("mac"):
                self.macs[slot] = result["mac"]
            return slot, result
        except (HTTPError, URLError, OSError, ValueError) as err:
            return slot, {
                "host": host,
                "reachable": False,
                "error": type(err).__name__,
                "overheat": False,
                "chain_fault": False,
                "not_hashing": True,
                "pool_down": True,
            }

    async def _async_update_data(self) -> dict:
        if not self.miners:
            raise UpdateFailed("No miners configured")
        return dict(await asyncio.gather(
            *(self._async_poll(slot, config) for slot, config in self.miners.items())
        ))
