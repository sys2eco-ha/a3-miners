"""Sensors for A3 Miners."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

SENSORS = (
    ("hashrate", "Hashrate", "GH/s", None, SensorStateClass.MEASUREMENT),
    ("hashrate_average", "Hashrate average", "GH/s", None, SensorStateClass.MEASUREMENT),
    ("pcb_temperature", "PCB temperature", "°C", SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    ("chip_temperature", "Chip temperature", "°C", SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    ("fan1", "Fan 1", "rpm", None, SensorStateClass.MEASUREMENT),
    ("fan2", "Fan 2", "rpm", None, SensorStateClass.MEASUREMENT),
    ("frequency", "Frequency", "MHz", None, SensorStateClass.MEASUREMENT),
    ("uptime", "Uptime", "s", SensorDeviceClass.DURATION, None),
    ("hardware_errors", "Hardware errors", None, None, SensorStateClass.TOTAL_INCREASING),
    ("asic_ok", "ASIC ok", None, None, SensorStateClass.MEASUREMENT),
    ("asic_bad", "ASIC bad", None, None, SensorStateClass.MEASUREMENT),
    ("pool_url", "Pool URL", None, None, None),
    ("pool_worker", "Pool worker", None, None, None),
    ("pool_status", "Pool status", None, None, None),
    ("pool_difficulty", "Pool difficulty", None, None, SensorStateClass.MEASUREMENT),
    ("last_share", "Last share", None, None, None),
    ("accepted", "Accepted", None, None, SensorStateClass.TOTAL_INCREASING),
    ("rejected", "Rejected", None, None, SensorStateClass.TOTAL_INCREASING),
    ("stale", "Stale", None, None, SensorStateClass.TOTAL_INCREASING),
    ("discarded", "Discarded", None, None, SensorStateClass.TOTAL_INCREASING),
    ("mac", "MAC address", None, None, None),
    ("host", "Host", None, None, None),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        A3Sensor(coordinator, entry.entry_id, slot, key, label, unit, device_class, state_class)
        for slot in coordinator.miners
        for key, label, unit, device_class, state_class in SENSORS
    )


class A3Sensor(CoordinatorEntity, SensorEntity):
    """One current A3 field."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry_id, slot, key, label, unit, device_class, state_class):
        super().__init__(coordinator)
        self._slot = slot
        self._key = key
        self._attr_unique_id = f"{entry_id}_{slot}_{key}"
        self._attr_translation_key = None
        self._attr_name = label
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class

    @property
    def device_info(self):
        config = self.coordinator.miners[self._slot]
        data = self.coordinator.data.get(self._slot, {})
        return DeviceInfo(
            identifiers={(DOMAIN, self._slot)},
            name=config["name"],
            manufacturer="Bitmain",
            model="Antminer A3",
            serial_number=data.get("mac"),
            configuration_url=f"http://{data.get('host', config['host'])}",
        )

    @property
    def available(self):
        return super().available and self.coordinator.data.get(self._slot, {}).get("reachable", False)

    @property
    def native_value(self):
        return self.coordinator.data[self._slot].get(self._key)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data[self._slot]
        return {"host": data.get("host"), "mac": data.get("mac")}
