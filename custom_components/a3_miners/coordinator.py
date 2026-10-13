"""Polling and parsing for stock Antminer A3 miners."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from urllib.error import HTTPError, URLError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_PATH,
    CONF_HOST,
    CONF_MAC,
    DEFAULT_PASSWORD,
    DEFAULT_USERNAME,
    DOMAIN,
    MINERS,
    NETWORK_PATH,
    OVERHEAT_TEMPERATURE,
)

_LOGGER = logging.getLogger(__name__)

MAX_SCAN_HOSTS = 8192
SCAN_CONCURRENCY = 128
SCAN_TIMEOUT = 2

_RANGE_PATTERN = re.compile(r"^(?P<start>[^-\s]+)\s*-\s*(?P<end>[^-\s]+)$")


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


def _fetch(host: str, path: str, timeout: int = 5) -> str:
    url = f"http://{host}{path}"
    password_manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    password_manager.add_password(None, url, DEFAULT_USERNAME, DEFAULT_PASSWORD)
    opener = urllib.request.build_opener(
        urllib.request.HTTPDigestAuthHandler(password_manager)
    )
    with opener.open(url, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def read_mac(host: str) -> str:
    """Return the normalised MAC address reported by the miner at host."""
    mac = _value(_fetch(host, NETWORK_PATH), r'"macaddr":"([^"]+)"')
    if not mac:
        raise ValueError(f"No MAC address reported by {host}")
    return format_mac(mac)


async def async_read_mac(hass: HomeAssistant, host: str) -> str:
    """Read the MAC address of a miner without blocking the event loop."""
    return await hass.async_add_executor_job(read_mac, host)


class ReversedRange(ValueError):
    """The range starts after it ends."""


def parse_ranges(text: str) -> list[str]:
    """Return the requested ranges as normalised "start - end" strings."""
    ranges = []
    for part in text.split(","):
        value = part.strip()
        if not value:
            continue
        match = _RANGE_PATTERN.match(value)
        if not match:
            raise ValueError(value)
        try:
            start = ipaddress.IPv4Address(match["start"])
            end = ipaddress.IPv4Address(match["end"])
        except ipaddress.AddressValueError as err:
            raise ValueError(value) from err
        if start > end:
            raise ReversedRange(value)
        normalised = f"{start} - {end}"
        if normalised not in ranges:
            ranges.append(normalised)
    return ranges


def _range_bounds(value: str) -> tuple[ipaddress.IPv4Address, ipaddress.IPv4Address]:
    start, _, end = value.partition(" - ")
    return ipaddress.IPv4Address(start), ipaddress.IPv4Address(end)


def count_hosts(ranges) -> int:
    """Return how many addresses the ranges hold."""
    return sum(
        int(end) - int(start) + 1 for start, end in map(_range_bounds, ranges)
    )


def iter_hosts(ranges):
    """Yield every address inside the ranges."""
    for value in ranges:
        start, end = _range_bounds(value)
        for number in range(int(start), int(end) + 1):
            yield str(ipaddress.IPv4Address(number))


def _probe(host: str) -> tuple[str, str] | None:
    """Return the host and its MAC address, or None when nothing answers."""
    try:
        text = _fetch(host, NETWORK_PATH, SCAN_TIMEOUT)
    except (HTTPError, URLError, OSError, ValueError):
        return None
    mac = _value(text, r'"macaddr":"([^"]+)"')
    return (host, format_mac(mac)) if mac else None


async def async_scan(ranges, progress=None) -> dict[str, str]:
    """Probe every host in the ranges and map IP address to MAC address."""
    hosts = list(iter_hosts(ranges))
    if not hosts:
        return {}
    loop = asyncio.get_running_loop()
    executor = ThreadPoolExecutor(
        max_workers=SCAN_CONCURRENCY, thread_name_prefix="a3_scan"
    )
    found: dict[str, str] = {}
    done = 0
    try:
        futures = [loop.run_in_executor(executor, _probe, host) for host in hosts]
        for future in asyncio.as_completed(futures):
            result = await future
            done += 1
            if result is not None:
                host, mac = result
                found[host] = mac
            if progress is not None:
                progress(done, len(hosts))
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    return found


def poll_miner(host: str, mac: str | None = None) -> dict:
    data = _parse_status(_fetch(host, API_PATH))
    data["host"] = host
    if mac is None:
        try:
            mac = read_mac(host)
        except (HTTPError, URLError, OSError, ValueError):
            mac = None
    data["mac"] = mac
    data["reachable"] = True
    return data


class A3Coordinator(DataUpdateCoordinator):
    """Fetch every configured miner once per update."""

    def __init__(self, hass: HomeAssistant, entry, miners: dict, interval: int) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.entry = entry
        self.miners = miners
        self.macs = {
            slot: config[CONF_MAC]
            for slot, config in miners.items()
            if config.get(CONF_MAC)
        }

    async def _async_poll(self, slot: str, config: dict) -> tuple[str, dict]:
        host = config[CONF_HOST]
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
        data = dict(
            await asyncio.gather(
                *(self._async_poll(slot, config) for slot, config in self.miners.items())
            )
        )
        self._store_macs()
        return data

    def _store_macs(self) -> None:
        """Persist learned MAC addresses so they survive restarts."""
        stored = self.entry.data.get(MINERS) or {}
        miners = dict(stored)
        changed = False
        for slot, mac in self.macs.items():
            record = miners.get(slot)
            if record and mac and record.get(CONF_MAC) != mac:
                miners[slot] = {**record, CONF_MAC: mac}
                changed = True
        if not changed:
            return
        try:
            self.hass.config_entries.async_update_entry(
                self.entry, data={**self.entry.data, MINERS: miners}
            )
        except Exception:  # noqa: BLE001 - never break polling for a bookkeeping write
            _LOGGER.debug("Could not store learned MAC addresses", exc_info=True)
