"""Switch entities for LSC Tuya Doorbell."""
import logging
import asyncio
from datetime import datetime

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_DEVICE_ID, CONF_FIRMWARE_VERSION, CONF_NAME
from .entity import TuyaDoorbellEntity
from .dp_entities import DPType, DPCategory, get_dp_definitions

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, 
    config_entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up switches based on a config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id]
    device_id = config_entry.data[CONF_DEVICE_ID]
    firmware_version = config_entry.data.get(CONF_FIRMWARE_VERSION, "Version 4")
    
    # Get DP definitions based on firmware version
    dp_definitions = get_dp_definitions(firmware_version)
    
    entities = []
    
    # Add DP-based switches (boolean type and status & function category)
    for dp_id, dp_def in dp_definitions.items():
        if dp_def.dp_type == DPType.BOOLEAN and dp_def.category == DPCategory.STATUS_FUNCTION:
            entity = TuyaDoorbellSwitch(hub, device_id, dp_def)
            _LOGGER.info(f"Creating switch entity: {dp_def.name} (DP {dp_id})")
            entities.append(entity)
    
    if entities:
        async_add_entities(entities)


class TuyaDoorbellSwitch(TuyaDoorbellEntity, SwitchEntity):
    """Representation of a Tuya doorbell switch."""
    
    def __init__(self, hub, device_id, dp_definition):
        """Initialize the switch."""
        super().__init__(hub, device_id, dp_definition)
        
        # Set name to include entity type for better identification in automations
        self._attr_name = f"{self._attr_name} [Switch]"
        
        # Explicitly set entity_id to avoid Home Assistant's automatic name-based generation
        device_name = self._hub.entry.data.get(CONF_NAME, f"LSC Doorbell {device_id[-4:]}").lower().replace(" ", "_")
        self.entity_id = f"switch.{device_name}_{dp_definition.code}"
        
        # No momentary switches in this implementation
        
        # Set device class based on DP code
        if "indicator" in dp_definition.code or "light" in dp_definition.code:
            self._attr_device_class = SwitchDeviceClass.OUTLET
        else:
            self._attr_device_class = SwitchDeviceClass.SWITCH
            
        # This ensures the switch appears in the UI
        self._attr_entity_registry_enabled_default = True
        
        _LOGGER.info(f"Created switch entity: {self.entity_id} (DP {dp_definition.id})")
    
    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._state is True
    
    def handle_update(self, value):
        """Handle state updates from the device."""
        # Log the update
        _LOGGER.debug(f"Switch {self.entity_id} handling update: value={value}, _state={self._state}")
        
        # Check if this is a manual update that we just sent
        from datetime import datetime
        current_time = datetime.now().timestamp()
        last_manual_update = getattr(self, '_last_manual_update', 0)
        
        # Protect our manual switch changes for a few seconds to avoid race conditions
        if current_time - last_manual_update < 5:
            # For switches we recently changed manually, protect the state from automatic updates
            # This prevents the switch from appearing to "flicker" in the UI
            bool_value = None
            if isinstance(value, bool):
                bool_value = value
            elif isinstance(value, (int, float)):
                bool_value = bool(value)
            elif isinstance(value, str):
                bool_value = value.lower() in ('true', '1', 'yes', 'on')
            else:
                bool_value = bool(value)
                
            if bool_value is not None and bool_value != self._state:
                _LOGGER.debug(f"Ignoring contradicting update for recently changed switch {self.entity_id}: device:{bool_value} != manual:{self._state}")
                return
        
        # For normal updates (not overriding manual changes), update the base state normally
        super().handle_update(value)
        
        # For boolean types, ensure the state is properly set as a boolean
        if self._dp_definition.dp_type == DPType.BOOLEAN:
            # Convert to strict boolean value
            if isinstance(value, bool):
                bool_value = value
            elif isinstance(value, (int, float)):
                bool_value = bool(value)
            elif isinstance(value, str):
                bool_value = value.lower() in ('true', '1', 'yes', 'on')
            else:
                bool_value = bool(value)
                
            _LOGGER.debug(f"Converted value {value} to boolean {bool_value} for switch {self.entity_id}")
            
            # Store the strictly boolean value
            self._state = bool_value
    
    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        _LOGGER.debug(f"Turning ON switch {self.entity_id}")
        
        # Store the time of this manual update to prevent automatic overrides
        from datetime import datetime
        self._last_manual_update = datetime.now().timestamp()
        
        # First update local state for immediate feedback
        self._state = True
        if self.hass:
            self.hass.add_job(self.async_write_ha_state)
        
        # Then send the command
        try:
            success = await self._hub.set_dp(self._dp_definition.id, True)
            
            if not success:
                _LOGGER.warning(f"Failed to turn on {self.entity_id}")
                
        except Exception as e:
            _LOGGER.error(f"Error turning on {self.entity_id}: {str(e)}")
    
    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        _LOGGER.debug(f"Turning OFF switch {self.entity_id}")
        
        # Store the time of this manual update to prevent automatic overrides
        from datetime import datetime
        self._last_manual_update = datetime.now().timestamp()
        
        # First update local state for immediate feedback
        self._state = False
        if self.hass:
            self.hass.add_job(self.async_write_ha_state)
        
        # Then send the command 
        try:
            success = await self._hub.set_dp(self._dp_definition.id, False)
            
            if not success:
                _LOGGER.warning(f"Failed to turn off {self.entity_id}")
        except Exception as e:
            _LOGGER.error(f"Error turning off {self.entity_id}: {str(e)}")