import logging
from datetime import timedelta

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
import httpx

from .const import (
    DOMAIN,
    MANUFACTURER,
    PLATFORMS,
    CONF_URL,
    CONF_USERID,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
)
from .spc import SPCSession, SPCError


LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry):
    url = entry.data[CONF_URL]
    userid = entry.data[CONF_USERID]
    password = entry.data[CONF_PASSWORD]

    poll_seconds = entry.options.get(
        CONF_POLL_INTERVAL,
        entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
    )
    poll_interval = timedelta(seconds=int(poll_seconds))

    spc = SPCSession(url=url, userid=userid, password=password)
    await spc.login()

    async def update():
        try:
            return {
                "arm_state": await spc.get_arm_state(),
                "zones": {zone["zone_id"]: zone
                          for zone in await spc.get_zones()},
            }
        
        except SPCError as e:
            # Treat as hard failure. Show unavailable.
            raise UpdateFailed(str(e)) from e
        
        except (httpx.HTTPError, ValueError) as e:
            raise UpdateFailed(f"SPC communication error: {e!s}") from e

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        config_entry=entry,
        name="Vanderbilt SPC Web",
        update_interval=poll_interval,
        update_method=update,
        always_update=False,
    )
    await coordinator.async_config_entry_first_refresh()

    alarm_device_id = (DOMAIN, f"{spc.serial_number}-alarm")
    alarm_device_info = DeviceInfo({
        "identifiers": {alarm_device_id},
        "name": (spc.site or "SPC Panel"),
        "manufacturer": MANUFACTURER,
        "model": spc.model,
        "serial_number": spc.serial_number,
    })

    def get_zone_device_info(zone):
        return DeviceInfo({
            "identifiers": {(DOMAIN, f"{spc.serial_number}-zone{zone["zone_id"]}")},
            "name": f"Zone {zone["zone_id"]} {zone["zone_name"]}",
            "manufacturer": MANUFACTURER,
            "model": f"{spc.model} Zone",
            "via_device": alarm_device_id,
        })

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "spc": spc,
        "coordinator": coordinator,
        "alarm_device_info": alarm_device_info,
        "get_zone_device_info": get_zone_device_info,
        "unique_prefix": f"spc{spc.serial_number}",
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if data:
            await data["spc"].aclose()
    return unload_ok
