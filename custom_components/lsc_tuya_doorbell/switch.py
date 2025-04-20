"""Switch entities for LSC Tuya Doorbell."""
from typing import Any
import logging
import asyncio
from datetime import datetime

from homeassistant.components.switch import SwitchEntity
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
        
        # Store whether this is a momentary switch
        self._is_momentary = getattr(dp_definition, 'momentary', False)
        
        # For momentary switches, we need to maintain a virtual state
        # Initialize as True if the device reports True, False otherwise
        self._virtual_state = self._state is True
        
        # How long the state should display as "on" after triggered (for momentary switches)
        self._momentary_duration = 5  # seconds
        self._momentary_timeout = None
        
        # Explicitly set icon based on state - for momentary switches, use virtual state
        if self._is_momentary:
            if self._virtual_state:
                self._attr_icon = "mdi:toggle-switch"
            else:
                self._attr_icon = "mdi:toggle-switch-off"
        else:
            if self._state is True:
                self._attr_icon = "mdi:toggle-switch"
            else:
                self._attr_icon = "mdi:toggle-switch-off"
    
    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await super().async_added_to_hass()
        
        # For momentary switches, try to restore virtual state from last known state
        if self._is_momentary:
            last_state = await self.async_get_last_state()
            if last_state and last_state.state:
                self._virtual_state = last_state.state.lower() == 'on'
                # Update icon based on restored virtual state
                self._attr_icon = "mdi:toggle-switch" if self._virtual_state else "mdi:toggle-switch-off"
                _LOGGER.debug(f"Restored momentary switch {self.entity_id} virtual state to {self._virtual_state}")

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        if self._state == "unknown" or self._state is None:
            return None
            
        # For momentary switches, return the virtual state
        if self._is_momentary:
            return self._virtual_state
            
        # For normal switches, return the actual state
        return self._state is True
        
    def handle_update(self, value):
        """Handle state updates from the device."""
        # Store current state before update for comparison
        previous_virtual_state = self._virtual_state if self._is_momentary else self._state
        
        # Call super to update the base state
        super().handle_update(value)
        
        # Log change in detail
        _LOGGER.debug(f"Switch {self.entity_id} handling update: value={value}, _state={self._state}")
        
        # Force the state to be a boolean True/False for boolean datapoints
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
        
        # Update icon and virtual state based on new state
        if self._is_momentary:
            # For momentary switches, we need to handle device updates carefully
            # If the device reports it's ON, we should reflect that in the virtual state
            # but only if we don't have a manual update in progress
            if value is True or (isinstance(value, (int, str)) and bool(value)):
                current_time = datetime.now().timestamp()
                last_manual_update = getattr(self, '_last_manual_update', 0)
                # If there's no recent manual update, update the virtual state
                if current_time - last_manual_update > 10:
                    _LOGGER.info(f"Momentary switch {self.entity_id} got ON update from device, updating virtual state")
                    self._virtual_state = True
                    self._attr_icon = "mdi:toggle-switch"
                    
                    # Schedule the auto-reset if it's not already scheduled
                    if self._momentary_timeout is None:
                        _LOGGER.debug(f"Scheduling auto-reset for momentary switch {self.entity_id}")
                        self.hass.create_task(self._schedule_momentary_reset())
            
            # Always keep icon in sync with virtual state
            self._attr_icon = "mdi:toggle-switch" if self._virtual_state else "mdi:toggle-switch-off"
        else:
            # Normal switches follow the device state directly
            if self._state is True:
                self._attr_icon = "mdi:toggle-switch"
            else:
                self._attr_icon = "mdi:toggle-switch-off"
        
        # Log the state change
        current_state = self._virtual_state if self._is_momentary else self._state
        if previous_virtual_state != current_state:
            _LOGGER.info(f"Switch {self.entity_id} changed from {previous_virtual_state} to {current_state}")
        
        # Write state to HA if changed
        self.async_write_ha_state()
                
    async def _reset_momentary_state(self, *_):
        """Reset momentary switch state after delay."""
        try:
            _LOGGER.debug(f"Resetting momentary switch {self.entity_id} to OFF state")
            self._virtual_state = False
            self._attr_icon = "mdi:toggle-switch-off"
            self.async_write_ha_state()
            self._momentary_timeout = None
        except Exception as e:
            _LOGGER.error(f"Error resetting momentary switch {self.entity_id}: {e}")
        
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        
        # Always use boolean values for switches
        _LOGGER.debug(f"Attempting to turn on {self.entity_id} with boolean True")
        
        if self._is_momentary:
            # For momentary switches, set the virtual state first
            _LOGGER.debug(f"Setting momentary switch {self.entity_id} virtual state to ON before sending command")
            self._virtual_state = True
            self._attr_icon = "mdi:toggle-switch"
            
            # Cancel any existing scheduled reset
            if self._momentary_timeout is not None:
                self._momentary_timeout.cancel()
                self._momentary_timeout = None
            
            # Update the UI immediately to show switch as ON
            self.async_write_ha_state()
            
            # Now send the command to the physical device
            success = await self._hub.set_dp(self._dp_definition.id, True)
            
            if success:
                # Record the time of this manual update to prevent automatic overrides
                _LOGGER.debug(f"Momentary switch {self.entity_id} command sent successfully")
                self._last_manual_update = datetime.now().timestamp()
                
                # Schedule reset of virtual state after delay
                _LOGGER.debug(f"Scheduling momentary switch reset in {self._momentary_duration} seconds")
                self._momentary_timeout = asyncio.create_task(
                    self._schedule_momentary_reset()
                )
            else:
                _LOGGER.warning(f"Failed to send command to momentary switch {self.entity_id}, keeping virtual state ON")
        else:
            # For regular switches, update state first then send command
            # This provides immediate UI feedback
            self._state = True
            self._attr_icon = "mdi:toggle-switch"
            # Update the UI immediately
            self.async_write_ha_state()
            
            # Record the time of this manual update to prevent automatic overrides
            self._last_manual_update = datetime.now().timestamp()
            
            # Send command to device
            success = await self._hub.set_dp(self._dp_definition.id, True)
            
            if success:
                _LOGGER.debug(f"Switch {self.entity_id} turned on successfully")
                # Refresh state after a brief delay to confirm
                self.hass.async_create_task(self._delayed_refresh())
            else:
                _LOGGER.warning(f"Failed to turn on switch {self.entity_id}, UI may be out of sync")
    
    async def _schedule_momentary_reset(self):
        """Schedule resetting the momentary switch after a delay."""
        try:
            await asyncio.sleep(self._momentary_duration)
            await self._reset_momentary_state()
        except asyncio.CancelledError:
            # Handle task cancellation gracefully
            _LOGGER.debug(f"Momentary reset task for {self.entity_id} cancelled")
            
    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await super().async_added_to_hass()
        
        # For momentary switches, try to restore virtual state from last known state
        if self._is_momentary:
            last_state = await self.async_get_last_state()
            if last_state and last_state.state:
                self._virtual_state = last_state.state.lower() == 'on'
                # Update icon based on restored virtual state
                self._attr_icon = "mdi:toggle-switch" if self._virtual_state else "mdi:toggle-switch-off"
                _LOGGER.debug(f"Restored momentary switch {self.entity_id} virtual state to {self._virtual_state}")
        
        # Schedule a refresh of the switch state after a brief delay
        # This helps ensure we have the latest state
        async def delayed_refresh():
            await asyncio.sleep(2)  # Wait 2 seconds to avoid startup race conditions
            await self.async_refresh_state()
            
        self.hass.async_create_task(delayed_refresh())

    async def async_will_remove_from_hass(self):
        """Clean up when entity is removed."""
        # Cancel any pending reset task
        if self._momentary_timeout is not None:
            self._momentary_timeout.cancel()
            self._momentary_timeout = None
            
        await super().async_will_remove_from_hass()
        
    async def async_refresh_state(self):
        """Refresh the state from the device."""
        if self._hub._protocol is None:
            _LOGGER.warning(f"Cannot refresh state for {self.entity_id}: no protocol")
            return
            
        _LOGGER.info(f"Manually refreshing state for {self.entity_id}")
        
        try:
            # Get current state directly from the device
            dp_value = await self._hub._protocol.get_dp(self._dp_definition.id)
            if dp_value is not None:
                _LOGGER.info(f"Refreshed state for {self.entity_id}: {dp_value}")
                # Use the hub to handle this update to ensure proper processing
                await self._hub._handle_dps_update(self._dp_definition.id, dp_value)
                return True
            else:
                _LOGGER.warning(f"Failed to refresh state for {self.entity_id}")
        except Exception as e:
            _LOGGER.error(f"Error refreshing state for {self.entity_id}: {e}")
            
        return False
        
    async def _delayed_refresh(self):
        """Refresh state after a brief delay."""
        await asyncio.sleep(2)  # Wait 2 seconds for device to process
        await self.async_refresh_state()
        
    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        attrs = super().extra_state_attributes
        if self._is_momentary:
            attrs["momentary"] = True
            attrs["momentary_duration"] = self._momentary_duration
        return attrs
            
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        
        if self._is_momentary:
            # For momentary switches, just reset the virtual state immediately
            _LOGGER.debug(f"Turning off momentary switch {self.entity_id} (virtual state only)")
            
            # Reset virtual state
            self._virtual_state = False
            self._attr_icon = "mdi:toggle-switch-off"
            
            # Cancel any pending reset task
            if self._momentary_timeout is not None:
                self._momentary_timeout.cancel()
                self._momentary_timeout = None
                
            # Update entity state
            self.async_write_ha_state()
            
            # Store this manual update time
            self._last_manual_update = datetime.now().timestamp()
            
            # No need to send an actual command to the device for momentary switches
            # since they auto-reset anyway and that would just trigger them
            return
            
        # For normal switches, actually send command to device
        # Always use boolean values for switches
        _LOGGER.debug(f"Attempting to turn off {self.entity_id} with boolean False")
        
        # Update state immediately for better UI responsiveness
        self._state = False
        self._attr_icon = "mdi:toggle-switch-off"
        self.async_write_ha_state()
        
        # Record the time of this manual update to prevent automatic overrides
        self._last_manual_update = datetime.now().timestamp()
        
        # Then send the command to the device
        success = await self._hub.set_dp(self._dp_definition.id, False)
            
        if success:
            _LOGGER.debug(f"Switch {self.entity_id} turned off successfully")
            # Refresh state after a brief delay to confirm
            self.hass.async_create_task(self._delayed_refresh())
        else:
            _LOGGER.warning(f"Failed to turn off switch {self.entity_id} - UI may be out of sync with device")