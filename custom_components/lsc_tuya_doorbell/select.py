"""Select entities for LSC Tuya Doorbell."""
from typing import Optional
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_DEVICE_ID, CONF_FIRMWARE_VERSION
from .entity import TuyaDoorbellEntity
from .dp_entities import DPType, DPCategory, get_dp_definitions

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up select entities based on a config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id]
    device_id = config_entry.data[CONF_DEVICE_ID]
    firmware_version = config_entry.data.get(CONF_FIRMWARE_VERSION, "Version 4")
    
    # Get DP definitions based on firmware version
    dp_definitions = get_dp_definitions(firmware_version)
    
    entities = []
    
    # Add DP-based select entities (enum type and status & function category)
    for dp_id, dp_def in dp_definitions.items():
        if dp_def.dp_type == DPType.ENUM and dp_def.category == DPCategory.STATUS_FUNCTION and dp_def.options:
            entity = TuyaDoorbellSelect(hub, device_id, dp_def)
            _LOGGER.info(f"Creating select entity: {dp_def.name} (DP {dp_id}) with options: {dp_def.options}")
            entities.append(entity)
    
    if entities:
        async_add_entities(entities)


class TuyaDoorbellSelect(TuyaDoorbellEntity, SelectEntity):
    """Representation of a Tuya doorbell select entity."""
    
    def __init__(self, hub, device_id, dp_definition):
        """Initialize the select entity."""
        super().__init__(hub, device_id, dp_definition)
        
        # Set up options for select entity
        self._attr_options = list(dp_definition.options.values())
        self._attr_current_option = None
        
        # Set initial value if available and valid
        if (self._state is not None and 
            self._state != "unknown" and 
            isinstance(self._state, (int, str, bool))):
            try:
                # Try with string conversion first
                if str(self._state) in dp_definition.options:
                    self._attr_current_option = dp_definition.options[str(self._state)]
                    _LOGGER.debug(f"Found option for value {self._state} -> {self._attr_current_option}")
                # Maybe it's a numeric value but stored as int
                elif isinstance(self._state, int) and str(self._state) in dp_definition.options:
                    self._attr_current_option = dp_definition.options[str(self._state)]
                    _LOGGER.debug(f"Found option for int value {self._state} -> {self._attr_current_option}")
                else:
                    _LOGGER.warning(f"Could not find option for value {self._state} in options: {dp_definition.options}")
            except (ValueError, TypeError) as e:
                _LOGGER.warning(f"Error setting initial value: {e}")
        
    @property
    def current_option(self) -> Optional[str]:
        """Return the current selected option."""
        if self._state is None or self._state == "unknown":
            return None
        
        # For numeric values, ensure we try with a proper string conversion    
        try:
            # Try to look up by string first
            state_str = str(self._state)
            if state_str in self._dp_definition.options:
                return self._dp_definition.options[state_str]
                
            # For integers that might be stored as actual int objects
            if isinstance(self._state, int):
                int_str = str(self._state)
                if int_str in self._dp_definition.options:
                    return self._dp_definition.options[int_str]
                
            # Try loose conversion for strings like "0" to 0
            if isinstance(self._state, str) and self._state.isdigit():
                int_key = str(int(self._state))
                if int_key in self._dp_definition.options:
                    return self._dp_definition.options[int_key]
                    
            # If we get here, we couldn't map the value
            _LOGGER.warning(f"Could not map state {self._state} to option in {self._dp_definition.options}")
            return None
        except (ValueError, TypeError) as e:
            _LOGGER.warning(f"Error converting state to option: {e}")
            return None
        
    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await super().async_added_to_hass()
        
        # Schedule a refresh of this entity's state after a brief delay
        # This helps ensure we have the latest state from the device
        async def delayed_refresh():
            import asyncio
            await asyncio.sleep(1)  # Small delay to avoid overwhelming the device
            await self.async_refresh_state()
            
        self.hass.async_create_task(delayed_refresh())
            
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        # Store the time of this manual update to prevent automatic overrides
        from datetime import datetime
        self._last_manual_update = datetime.now().timestamp()
        
        # Find the key for the selected option value
        key_found = None
        for key, value in self._dp_definition.options.items():
            if value == option:
                key_found = key
                break
                
        if key_found is None:
            _LOGGER.error(f"Could not find key for option {option} in {self._dp_definition.options}")
            return
            
        # Convert key to integer if possible (Tuya almost always uses integer enum values)
        try:
            int_key = int(key_found)
            _LOGGER.debug(f"Converted option key to integer: {key_found} -> {int_key}")
        except ValueError:
            # Keep as string if it can't be converted
            int_key = key_found
            _LOGGER.debug(f"Using non-integer key for option: {key_found}")
        
        # Update state immediately in UI for better responsiveness
        self._state = int_key  # Store raw value
        self._attr_current_option = option  # Store display value
        self.async_write_ha_state()
        
        # Log the device state before update
        _LOGGER.info(f"Setting {self.entity_id} ({self._dp_definition.code}) to {option} (raw value: {int_key})")
        
        # Send command to device
        success = await self._hub.set_dp(self._dp_definition.id, int_key)
        
        if success:
            _LOGGER.info(f"Select option for {self.entity_id} set successfully")
            # Schedule a refresh after a brief delay to verify
            async def delayed_refresh():
                import asyncio
                await asyncio.sleep(2)  # Wait 2 seconds before refreshing
                await self.async_refresh_state()
                
            self.hass.async_create_task(delayed_refresh())
        else:
            _LOGGER.warning(f"Failed to set option for {self.entity_id}")
            
            # Try again after a delay if it failed
            async def retry_set_option():
                import asyncio
                _LOGGER.info(f"Retrying setting {self.entity_id} to {option}")
                await asyncio.sleep(2)  # Wait before retry
                retry_success = await self._hub.set_dp(self._dp_definition.id, int_key)
                if retry_success:
                    _LOGGER.info(f"Retry successful for {self.entity_id}")
                    await asyncio.sleep(1)
                    await self.async_refresh_state()
                else:
                    _LOGGER.error(f"Retry also failed for {self.entity_id}")
                    
            self.hass.async_create_task(retry_set_option())