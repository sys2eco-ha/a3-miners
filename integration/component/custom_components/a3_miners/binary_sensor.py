"""Binary sensors for A3 Miners."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

BINARY_SENSORS = (
    ("reachable", "Reachable", BinarySensorDeviceClass.CONNECTIVITY),
    ("overheat", "Overheat", BinarySensorDeviceClass.PROBLEM),
    ("chain_fault", "Chain fault", BinarySensorDeviceClass.PROBLEM),
    ("not_hashing", "Not hashing", BinarySensorDeviceClass.PROBLEM),
    ("pool_down", "Pool down", BinarySensorDeviceClass.PROBLEM),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        A3BinarySensor(coordinator, entry.entry_id, slot, key, label, device_class)
        for slot in coordinator.miners
        for key, label, device_class in BINARY_SENSORS
    )


class A3BinarySensor(CoordinatorEntity, BinarySensorEntity):
    """One current A3 fault or reachability state."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry_id, slot, key, label, device_class):
        super().__init__(coordinator)
        self._slot = slot
        self._key = key
        self._attr_unique_id = f"{entry_id}_{slot}_{key}"
        self._attr_name = label
        self._attr_device_class = device_class

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
    def is_on(self):
        return bool(self.coordinator.data.get(self._slot, {}).get(self._key, False))
