from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
)

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SPC sensor entities from a config entry."""

    data = hass.data[DOMAIN][entry.entry_id]

    coordinator = data["coordinator"]
    get_zone_device_info = data["get_zone_device_info"]
    unique_prefix = data["unique_prefix"]

    for zone in coordinator.data["zones"].values():
        device_info = get_zone_device_info(zone)
        async_add_entities([
            SPCZoneInput(
                coordinator=coordinator,
                device_info=device_info,
                unique_prefix=unique_prefix,
                zone=zone,
            ),
            SPCZoneStatus(
                coordinator=coordinator,
                device_info=device_info,
                unique_prefix=unique_prefix,
                zone=zone,
            ),
        ])


class SPCZoneInput(CoordinatorEntity, SensorEntity):
    """Enum sensor representing SPC input state."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_has_entity_name = True
    _attr_translation_key = "zone_input"

    # XXX possibly incomplete, see pyspcwebgw.const.ZoneInput
    _attr_options = [
        "closed",       # CLOSED
        "open",         # OPEN
        "short",        # SHORT
        "discon",       # DISCONNECTED
                        # PIRMASKED
                        # DC_SUBSTITUTION
                        # SENSOR_MISSING
        "offline",      # OFFLINE
    ]

    def __init__(self, coordinator, device_info, unique_prefix, zone):
        super().__init__(coordinator)

        zone_id = zone["zone_id"]

        self._zone_id = zone_id
        self._attr_name = "Input"
        self._attr_unique_id = f"{unique_prefix}-zone{zone_id}-input"
        self._attr_device_info = device_info

    @property
    def native_value(self):
        zone = self.coordinator.data["zones"].get(self._zone_id)
        if zone:
            return zone["input"]


class SPCZoneStatus(CoordinatorEntity, SensorEntity):
    """Enum sensor representing SPC zone status."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_has_entity_name = True
    _attr_translation_key = "zone_status"

    # XXX possibly incomplete, see pyspcwebgw.const.ZoneStatus
    _attr_options = [
        "normal",           # OK
        "inhibit",          # INHIBIT
                            # ISOLATE
                            # SOAK
        "tamper",           # TAMPER
        "actuated",         # ALARM
                            # OK_NOT_RECENT
                            # TROUBLE
    ]

    def __init__(self, coordinator, device_info, unique_prefix, zone):
        super().__init__(coordinator)

        zone_id = zone["zone_id"]

        self._zone_id = zone_id
        self._attr_name = "Status"
        self._attr_unique_id = f"{unique_prefix}-zone{zone_id}-status"
        self._attr_device_info = device_info

    @property
    def native_value(self):
        zone = self.coordinator.data["zones"].get(self._zone_id)
        if zone:
            return zone["status"]
