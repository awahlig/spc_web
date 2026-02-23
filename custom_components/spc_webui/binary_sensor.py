from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)

from .const import DOMAIN


ACTUATED_NAME = {
    "alarm": "Motion",
    "entry/exit": "Contact",
    "entry/exit 2": "Contact",
    "fire": "Fire",
    "technical": "Fault",
}


ACTUATED_DEVCLASS = {
    "alarm": BinarySensorDeviceClass.MOTION,
    "entry/exit": BinarySensorDeviceClass.OPENING,
    "entry/exit 2": BinarySensorDeviceClass.OPENING,
    "fire": BinarySensorDeviceClass.SMOKE,
    "technical": BinarySensorDeviceClass.PROBLEM,
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SPC binary sensor entities from a config entry."""

    data = hass.data[DOMAIN][entry.entry_id]

    coordinator = data["coordinator"]
    get_zone_device_info = data["get_zone_device_info"]
    unique_prefix = data["unique_prefix"]

    for zone in coordinator.data["zones"].values():
        device_info = get_zone_device_info(zone)
        async_add_entities([
            SPCZoneActuated(
                coordinator=coordinator,
                device_info=device_info,
                unique_prefix=unique_prefix,
                zone=zone,
            ),
            SPCZoneTamper(
                coordinator=coordinator,
                device_info=device_info,
                unique_prefix=unique_prefix,
                zone=zone,
            ),
        ])


class SPCZoneActuated(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor indicating whether the SPC zone is actuated."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, device_info, unique_prefix, zone):
        super().__init__(coordinator)

        zone_id = zone["zone_id"]
        zone_type = zone["zone_type"]

        self._zone_id = zone_id
        self._attr_name = ACTUATED_NAME.get(zone_type, "Actuated")
        self._attr_device_class = ACTUATED_DEVCLASS.get(zone_type)
        self._attr_unique_id = f"{unique_prefix}-zone{zone_id}-actuated"
        self._attr_device_info = device_info

    @property
    def is_on(self):
        zone = self.coordinator.data["zones"].get(self._zone_id)
        if zone:
            return (zone["status"] == "actuated")
        return False


class SPCZoneTamper(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor indicating whether the SPC zone is in a tamper state."""

    _attr_has_entity_name = True
    _attr_name = "Tamper"
    _attr_device_class = BinarySensorDeviceClass.TAMPER

    def __init__(self, coordinator, device_info, unique_prefix, zone):
        super().__init__(coordinator)

        zone_id = zone["zone_id"]

        self._zone_id = zone_id
        self._attr_unique_id = f"{unique_prefix}-zone{zone_id}-tamper"
        self._attr_device_info = device_info

    @property
    def is_on(self):
        zone = self.coordinator.data["zones"].get(self._zone_id)
        if zone:
            return (zone["status"] == "tamper")
        return False
