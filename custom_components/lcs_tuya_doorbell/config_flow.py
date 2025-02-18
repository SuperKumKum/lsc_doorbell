from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol
from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_DEVICE_ID,
    CONF_LOCAL_KEY,
    CONF_HOST,
    CONF_PORT,
    DEFAULT_PORT,
    CONF_MAC,
    CONF_LAST_IP
)

class LcsTuyaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LCS Tuya Doorbell."""
    
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_DEVICE_ID): str,
                vol.Required(CONF_LOCAL_KEY): str,
                vol.Optional(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Optional(CONF_MAC): str,
            }),
            errors=errors
        )

    async def async_step_import(self, import_config) -> FlowResult:
        """Handle import from YAML."""
        return await self.async_step_user(import_config)
