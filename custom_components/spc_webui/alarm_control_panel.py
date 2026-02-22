from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)

from .const import DOMAIN
from .spc import SPCError


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SPC alarm control panel entity from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]

    coordinator = data["coordinator"]
    spc = data["spc"]
    alarm_device_info = data["alarm_device_info"]
    unique_prefix = data["unique_prefix"]

    async_add_entities(
        [
            SPCAlarm(
                coordinator=coordinator,
                spc=spc,
                device_info=alarm_device_info,
                unique_prefix=unique_prefix,
            )
        ]
    )


class SPCAlarm(CoordinatorEntity, AlarmControlPanelEntity):
    """Alarm entity representing all SPC areas."""

    _attr_code_arm_required = False
    _attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY
    _attr_has_entity_name = True

    def __init__(self, coordinator, spc, device_info, unique_prefix):
        super().__init__(coordinator)
        self.spc = spc

        self._attr_name = "Alarm"
        self._attr_unique_id = f"{unique_prefix}-alarm"
        self._attr_device_info = device_info

    @property
    def alarm_state(self):
        arm_state = self.coordinator.data["arm_state"]
        return {
            "unset": AlarmControlPanelState.DISARMED,
            "fullset": AlarmControlPanelState.ARMED_AWAY,
        }.get(arm_state)

    async def _async_set_arm_state(self, arm_state):
        try:
            await self.spc.set_arm_state(arm_state)
        except SPCError as err:
            raise HomeAssistantError(str(err)) from err
        finally:
            await self.coordinator.async_request_refresh()

    async def async_alarm_disarm(self, code=None):
        await self._async_set_arm_state("unset")

    async def async_alarm_arm_away(self, code=None):
        await self._async_set_arm_state("fullset")
