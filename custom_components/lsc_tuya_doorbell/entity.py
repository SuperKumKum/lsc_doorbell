"""Base entities for LSC Tuya Doorbell integration."""
import logging
from typing import Dict, Any
from datetime import datetime
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.restore_state import RestoreEntity
from .const import DOMAIN, CONF_DEVICE_ID, CONF_FIRMWARE_VERSION, CONF_NAME
from .dp_entities import DPDefinition, DPType

_LOGGER = logging.getLogger(__name__)

class TuyaDoorbellEntity(RestoreEntity, Entity):
    """Base class for all Tuya doorbell entities."""

    def __init__(self, hub, device_id, dp_definition: DPDefinition):
        """Initialize the entity."""
        self._hub = hub
        self._device_id = device_id
        self._dp_definition = dp_definition
        self._state = None
        self._attr_name = f"{dp_definition.name}"
        self._attr_unique_id = f"{device_id}_{dp_definition.id}"
        self._attr_icon = dp_definition.icon

        # Set up device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._hub.entry.data.get(CONF_NAME, f"LSC Doorbell {self._device_id[-4:]}"),
            manufacturer="LSC Smart Connect / Tuya",
            model=f"Video Doorbell {self._hub.entry.data.get(CONF_FIRMWARE_VERSION, 'Unknown')}",
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._hub._protocol is not None

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # Restore previous state
        last_state = await self.async_get_last_state()
        if last_state:
            try:
                # For boolean types, convert string state to boolean
                if self._dp_definition.dp_type == DPType.BOOLEAN:
                    self._state = last_state.state.lower() == 'on'
                    _LOGGER.debug(f"Restored boolean state for {self.entity_id}: {self._state}")
                # For numeric types, convert string state to number
                elif self._dp_definition.dp_type == DPType.INTEGER:
                    try:
                        self._state = int(last_state.state)
                        _LOGGER.debug(f"Restored integer state for {self.entity_id}: {self._state}")
                    except (ValueError, TypeError):
                        self._state = None
                # For other types, use as is
                else:
                    self._state = last_state.state
                    _LOGGER.debug(f"Restored state for {self.entity_id}: {self._state}")
            except Exception as e:
                _LOGGER.error(f"Error restoring state for {self.entity_id}: {e}")

        # Request current state from device as soon as we're added to HA
        # This ensures we have the latest data from the physical device
        async def request_current_state():
            # First try to request all status
            try:
                if self._hub._protocol is None:
                    _LOGGER.warning(f"Cannot request state for {self.entity_id} - no active connection")
                    return
                    
                _LOGGER.info(f"Requesting current state for {self.entity_id} (DP {self._dp_definition.id})")
                
                # First, try a direct query for our specific DP
                # This is the most reliable method for most devices
                dp_value = await self._hub._protocol.get_dp(self._dp_definition.id)
                if dp_value is not None:
                    _LOGGER.info(f"Got direct value for {self.entity_id}: {dp_value}")
                    # Important: Get the hub to handle this update so all entities get updated
                    await self._hub._handle_dps_update(self._dp_definition.id, dp_value)
                    return  # Success
                    
                # If direct query fails, try a full status request
                _LOGGER.debug(f"Direct query failed for {self.entity_id}, trying full status")
                status = await self._hub._protocol.status()
                if status and "dps" in status and self._dp_definition.id in status["dps"]:
                    dp_value = status["dps"][self._dp_definition.id]
                    _LOGGER.info(f"Got value from status for {self.entity_id}: {dp_value}")
                    # Let the hub handle the update
                    await self._hub._handle_dps_update(self._dp_definition.id, dp_value)
                    return  # Success
                    
                # If we get here, both methods failed
                _LOGGER.warning(f"Both direct query and status failed for {self.entity_id}")
                
                # For some entities (especially selects/enums), if we still don't have a value,
                # we might be dealing with a device that doesn't properly report status
                # In this case, try to get the status from the full device status request
                if self._dp_definition.dp_type == DPType.ENUM and self._state is None:
                    _LOGGER.info(f"Trying to detect available DPs for {self.entity_id}")
                    try:
                        dps = await self._hub._protocol.detect_available_dps()
                        if dps and self._dp_definition.id in dps:
                            dp_value = dps[self._dp_definition.id]
                            _LOGGER.info(f"Got value from available DPs for {self.entity_id}: {dp_value}")
                            await self._hub._handle_dps_update(self._dp_definition.id, dp_value)
                            return  # Success
                    except Exception as e:
                        _LOGGER.debug(f"Failed to detect available DPs: {e}")
                        
            except Exception as e:
                _LOGGER.error(f"Error requesting state for {self.entity_id}: {e}")
                
        # Schedule state request with small delay to avoid overwhelming the device
        # The delay is staggered based on the DP ID to avoid all entities requesting simultaneously
        import asyncio
        # Use the DP ID for staggering (convert to int if possible)
        try:
            dp_id_int = int(self._dp_definition.id)
            delay = 0.2 + (dp_id_int % 10) * 0.1  # 0.2s to 1.1s delay based on DP
        except (ValueError, TypeError):
            delay = 0.5  # Default delay
        
        _LOGGER.debug(f"Scheduling state request for {self.entity_id} with {delay}s delay")
        
        async def delayed_request():
            await asyncio.sleep(delay)
            await request_current_state()
            
        if self._hub._protocol is not None:
            self.hass.async_create_task(delayed_request())

        # Register callback to receive updates from the device
        self._hub.register_entity(self._dp_definition.id, self)

    async def async_will_remove_from_hass(self):
        """When entity is removed from hass."""
        # Unregister entity
        self._hub.unregister_entity(self._dp_definition.id, self)
        await super().async_will_remove_from_hass()

    def handle_update(self, value):
        """Handle state updates from the device."""
        _LOGGER.debug(f"Entity {self._attr_name} received update for DP {self._dp_definition.id}: {value}")

        # Decode base64 data if applicable
        if isinstance(value, str) and self._dp_definition.dp_type == DPType.RAW:
            try:
                # Try standard base64 decoding
                import base64
                import json
                
                # For display purposes, we don't want to show raw base64 strings
                is_likely_base64 = False
                # Check if the string looks like base64 (all valid chars and reasonable length)
                if len(value) > 10:
                    valid_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=')
                    if all(c in valid_chars for c in value):
                        is_likely_base64 = True
                
                if is_likely_base64:
                    _LOGGER.debug(f"Processing likely base64 string of length {len(value)}")
                    
                    # Add padding if needed
                    padded_value = value
                    if len(padded_value) % 4 != 0:
                        padded_value += "=" * (4 - len(padded_value) % 4)
                    
                    # Try different decoding approaches
                    decoded_value = None
                    
                    # Try standard base64
                    try:
                        decoded = base64.b64decode(padded_value).decode('utf-8')
                        # Try to parse as JSON
                        try:
                            json_data = json.loads(decoded)
                            _LOGGER.debug(f"Decoded base64 to JSON: {json_data}")
                            decoded_value = json_data
                        except json.JSONDecodeError:
                            # Not JSON, but we have a valid string
                            if len(decoded) < 1000:  # Don't use super long strings
                                _LOGGER.debug(f"Decoded base64 to string (len={len(decoded)})")
                                decoded_value = decoded
                    except Exception as e:
                        _LOGGER.debug(f"Standard base64 decode failed: {str(e)}")
                        
                        # Try URL-safe base64
                        try:
                            decoded = base64.urlsafe_b64decode(padded_value).decode('utf-8')
                            # Try to parse as JSON
                            try:
                                json_data = json.loads(decoded)
                                _LOGGER.debug(f"Decoded URL-safe base64 to JSON: {json_data}")
                                decoded_value = json_data
                            except json.JSONDecodeError:
                                # Not JSON, but we have a valid string
                                if len(decoded) < 1000:  # Don't use super long strings
                                    _LOGGER.debug(f"Decoded URL-safe base64 to string (len={len(decoded)})")
                                    decoded_value = decoded
                        except Exception as e2:
                            _LOGGER.debug(f"URL-safe base64 decode failed: {str(e2)}")
                    
                    # If we decoded successfully, use the decoded value
                    if decoded_value is not None:
                        _LOGGER.info(f"Successfully decoded base64 data for {self.entity_id}")
                        value = {"data": decoded_value}
                    else:
                        # For display purposes, don't show raw base64
                        _LOGGER.debug(f"Could not decode base64, using placeholder")
                        value = {"type": "encoded_data", "length": len(value)}
                else:
                    _LOGGER.debug(f"Value doesn't look like base64, using as-is")
            except Exception as e:
                _LOGGER.debug(f"Error processing base64: {str(e)}")

        # Special handling for "unknown" values
        if value == "unknown":
            _LOGGER.debug(f"Received 'unknown' value for {self._attr_name}, setting state to None")
            self._state = None

            # Reset select and number attributes as well
            if hasattr(self, '_attr_current_option'):
                self._attr_current_option = None
            if hasattr(self, '_attr_native_value'):
                self._attr_native_value = None

            # Update the entity state in Home Assistant and return
            self.async_write_ha_state()
            return

        # For some Tuya devices with momentary states, protect against rapid toggles
        # Only applies to binary sensors or where the value is boolean
        current_is_bool = isinstance(self._state, bool)
        new_is_bool = isinstance(value, bool)

        if current_is_bool and new_is_bool and self._state != value:
            # If we recently set this value manually through a service call,
            # don't let automatic updates override it for a short period
            current_time = datetime.now().timestamp()
            last_manual_update = getattr(self, '_last_manual_update', 0)

            # If manual update was less than 2 seconds ago, ignore contradicting automatic updates
            if current_time - last_manual_update < 2:
                _LOGGER.debug(f"Ignoring contradicting update for recently manually-set entity {self._attr_name}")
                return

        # Store the previous state for comparison
        previous_state = self._state
                
        # Update the internal state value - for boolean types, make sure we use strict True/False
        if self._dp_definition.dp_type == DPType.BOOLEAN:
            # Force value to be a boolean True/False
            if isinstance(value, bool):
                self._state = value
            elif isinstance(value, (int, float)):
                self._state = bool(value)
            elif isinstance(value, str):
                self._state = value.lower() in ('true', 'on', 'yes', '1')
            else:
                self._state = bool(value)
            _LOGGER.debug(f"Updated boolean state for {self._attr_name} to {self._state} (from {value})")
        else:
            # For non-boolean types, use the value directly
            self._state = value
            
        # Log state changes for easier debugging
        if previous_state != self._state:
            _LOGGER.info(f"State change for {self._attr_name}: {previous_state} -> {self._state}")

        # For select entities, also update current_option
        if hasattr(self, '_attr_current_option') and hasattr(self._dp_definition, 'options'):
            try:
                if value is not None and str(value) in self._dp_definition.options:
                    self._attr_current_option = self._dp_definition.options[str(value)]
                    _LOGGER.debug(f"Updated select option to: {self._attr_current_option}")
                else:
                    self._attr_current_option = None
            except (ValueError, TypeError):
                self._attr_current_option = None

        # For number entities, update the native value
        if hasattr(self, '_attr_native_value'):
            try:
                if value is not None and isinstance(value, (int, float, bool)):
                    self._attr_native_value = float(value)
                else:
                    self._attr_native_value = None
            except (ValueError, TypeError):
                # If conversion fails, set to None
                self._attr_native_value = None

        # Update the entity state in Home Assistant
        self.async_write_ha_state()

    async def async_refresh_state(self):
        """Refresh the state from the device."""
        if self._hub._protocol is None:
            _LOGGER.warning(f"Cannot refresh state for {self.entity_id}: no protocol")
            return False
            
        _LOGGER.info(f"Refreshing state for {self.entity_id} (DP {self._dp_definition.id})")
        
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

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return device specific state attributes."""
        attrs = {
            "dp_id": self._dp_definition.id,
            "dp_code": self._dp_definition.code,
            "device_id": self._device_id,
        }
        
        # Add raw value attribute for debugging, but clean up any base64/binary data
        # and redact any potentially sensitive information
        if self._state is not None:
            if self._dp_definition.dp_type == DPType.RAW and isinstance(self._state, (dict, list)):
                # For complex values, store them with a clean prefix
                attrs["decoded_data"] = True
                
                # If it's a dictionary with possible sensitive data, only show safe keys
                if isinstance(self._state, dict):
                    # Safe keys to include in attributes
                    safe_keys = ["type", "length", "timestamp", "count", "status", "version"]
                    for key in safe_keys:
                        if key in self._state:
                            attrs[f"data_{key}"] = self._state[key]
                    
                    # Add count of other keys
                    other_keys = [k for k in self._state if k not in safe_keys]
                    if other_keys:
                        attrs["additional_fields"] = len(other_keys)
                        
            elif self._dp_definition.dp_type == DPType.RAW and isinstance(self._state, str) and len(self._state) > 100:
                # For long raw strings, just note they're present
                attrs["raw_data_length"] = len(self._state)
                attrs["raw_data_type"] = str(type(self._state))
            elif "password" in self._dp_definition.code or "pwd" in self._dp_definition.code:
                # For security-related fields, don't show actual values
                attrs["value_protected"] = True
            else:
                # Otherwise store the value as-is
                attrs["raw_value"] = self._state
        
        return attrs