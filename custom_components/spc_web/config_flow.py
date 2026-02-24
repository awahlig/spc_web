import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_URL,
    CONF_USERID,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
)
from .spc import SPCSession, SPCLoginError


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_USERID): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.Coerce(int),
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.Coerce(int),
    }
)


class SPCConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle user setup of the integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            url = user_input[CONF_URL]
            userid = user_input[CONF_USERID]
            password = user_input[CONF_PASSWORD]
            poll_interval = user_input.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)

            spc = SPCSession(url=url, userid=userid, password=password)
            try:
                await spc.login()
            except SPCLoginError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"
            finally:
                await spc.aclose()

            if not errors:
                await self.async_set_unique_id(spc.serial_number)

                return self.async_create_entry(
                    title=url,
                    data={
                        CONF_URL: url,
                        CONF_USERID: userid,
                        CONF_PASSWORD: password,
                        CONF_POLL_INTERVAL: poll_interval,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SPCOptionsFlow()


class SPCOptionsFlow(config_entries.OptionsFlowWithReload):
    """Options flow to tweak polling interval after setup."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
