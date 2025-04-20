"""Sensor entities for LSC Tuya Doorbell."""
import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_HOST,
    CONF_FIRMWARE_VERSION,
    EVENT_BUTTON_PRESS,
    EVENT_MOTION_DETECT,
    ATTR_DEVICE_ID,
    ATTR_TIMESTAMP,
)
from .entity import TuyaDoorbellEntity
from .dp_entities import DPType, DPCategory, get_dp_definitions

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, 
    config_entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors based on a config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id]
    device_id = config_entry.data[CONF_DEVICE_ID]
    firmware_version = config_entry.data.get(CONF_FIRMWARE_VERSION, "Version 4")
    
    entities = []
    
    # Add connection status sensor
    entities.append(LscTuyaStatusSensor(hub, device_id))
    
    # Get DP definitions based on firmware version
    dp_definitions = get_dp_definitions(firmware_version)
    
    # Excluded items
    excluded_codes = [
        "chime_ring_volume",   # DP 157 - Chime Volume - should be a control only
        "basic_device_volume", # DP 160 - Device Volume - should be a control only
        "sd_format",           # DP 111 - Format SD Card - should be a control only
        "motion_switch",       # DP 134 - Motion Detection - should be a switch only
        "sd_status",           # DP 110 - SD Card Status - control related
        "sd_format_state",     # DP 117 - SD Format State - control related
    ]
    
    # Add DP-based sensors - but exclude specified ones
    for dp_id, dp_def in dp_definitions.items():
        # Skip if in excluded list
        if dp_def.code in excluded_codes:
            _LOGGER.info(f"Skipping sensor creation for {dp_def.name} (DP {dp_id}) - excluded")
            continue
            
        if dp_def.dp_type in [DPType.STRING, DPType.INTEGER, DPType.RAW]:
            # Only status_only items go to sensor
            if dp_def.dp_type != DPType.RAW or dp_def.category == DPCategory.STATUS_ONLY:
                entity = TuyaDoorbellSensor(hub, device_id, dp_def)
                _LOGGER.info(f"Creating sensor entity: {dp_def.name} (DP {dp_id})")
                entities.append(entity)
    
    # Add enum sensors - these are read-only values - but exclude specified ones
    for dp_id, dp_def in dp_definitions.items():
        # Skip if in excluded list
        if dp_def.code in excluded_codes:
            continue
            
        if dp_def.dp_type == DPType.ENUM and dp_def.category == DPCategory.STATUS_ONLY:
            entity = TuyaDoorbellSensor(hub, device_id, dp_def)
            _LOGGER.info(f"Creating enum sensor entity: {dp_def.name} (DP {dp_id})")
            entities.append(entity)
    
    if entities:
        async_add_entities(entities)


class TuyaDoorbellSensor(TuyaDoorbellEntity, SensorEntity):
    """Representation of a Tuya doorbell sensor."""
    
    def __init__(self, hub, device_id, dp_definition):
        """Initialize the sensor."""
        super().__init__(hub, device_id, dp_definition)
        
        # Set device class based on DP code
        if "volume" in dp_definition.code:
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_native_unit_of_measurement = "%"
            
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
        
    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self._state is None or self._state == "unknown":
            return None
            
        # For enum types, map the state to the enum value if options exist
        if self._dp_definition.dp_type == DPType.ENUM and self._dp_definition.options:
            return self._dp_definition.options.get(str(self._state), self._state)
            
        # For numeric types with measurement state class, ensure it can be converted to a number
        if hasattr(self, '_attr_state_class') and self._attr_state_class == SensorStateClass.MEASUREMENT:
            try:
                # Try to convert to float, return None if not possible
                return float(self._state)
            except (ValueError, TypeError):
                return None
        
        # For RAW data, return a better formatted representation
        if self._dp_definition.dp_type == DPType.RAW:
            if isinstance(self._state, dict) and "data" in self._state:
                # If we've decoded base64 to something presentable, show that
                return str(self._state["data"])
            elif isinstance(self._state, dict) and "type" in self._state and self._state["type"] == "encoded_data":
                # If it's encoded data that we can't display well, show a placeholder
                return f"Encoded data ({self._state.get('length', 'unknown')} bytes)"
            elif isinstance(self._state, str) and len(self._state) > 100:
                # Long string, probably encoded data, show a placeholder
                return f"Binary data ({len(self._state)} bytes)"
            
        # Default case
        return self._state
        
    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        attrs = super().extra_state_attributes
        
        # Remove raw_value if present, as it's not needed for sensors
        if "raw_value" in attrs:
            del attrs["raw_value"]
        
        # For RAW types, add additional attributes for better debugging
        if self._dp_definition.dp_type == DPType.RAW:
            if isinstance(self._state, dict) and "data" in self._state:
                attrs["decoded_data"] = True
                if isinstance(self._state["data"], dict):
                    # Only include safe, non-sensitive keys
                    safe_keys = ["type", "timestamp", "count", "status", "version"]
                    for key in safe_keys:
                        if key in self._state["data"] and isinstance(self._state["data"][key], (str, int, float, bool)):
                            attrs[f"data_{key}"] = self._state["data"][key]
                    
                    # Indicate there are additional fields without showing them
                    all_keys = self._state["data"].keys()
                    other_keys = [k for k in all_keys if k not in safe_keys]
                    if other_keys:
                        attrs["additional_fields"] = len(other_keys)
            elif isinstance(self._state, dict) and "type" in self._state:
                attrs["encoded"] = True
                attrs["data_length"] = self._state.get("length", 0)
        
        # For specific sensitive entity types, remove additional attributes
        sensitive_codes = ["password", "pwd", "onvif", "account", "user", "ip_addr"]
        if any(code in self._dp_definition.code for code in sensitive_codes):
            # Keep only basic entity info, remove any potentially sensitive data
            return {
                "dp_id": self._dp_definition.id,
                "dp_code": self._dp_definition.code,
                "device_id": self._device_id,
                "value_protected": True
            }
                
        return attrs


class LscTuyaStatusSensor(SensorEntity):
    """Device status sensor showing connection info."""
    
    def __init__(self, hub, device_id):
        """Initialize the status sensor."""
        self._hub = hub
        self._device_id = device_id
        
        # Get device name from config entry
        device_name = self._hub.entry.data.get(CONF_NAME, f"LSC Doorbell {device_id[-4:]}")
        
        # Set entity name to include device name
        self._attr_name = f"{device_name} Connection Status"
        self._attr_unique_id = f"{device_id}_connection_status"
        
        # Home Assistant will automatically create the entity_id based on the device_name
        # and entity class, which will result in sensor.device_name_entity_name format
        
        self._attr_icon = "mdi:connection"
        self._last_heartbeat = None
        
        # Store the latest event data
        self._last_doorbell_time = None
        self._last_motion_time = None
        self._event_counters = {
            "doorbell": 0,
            "motion": 0
        }
        
        # Set up device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._hub.entry.data.get(CONF_NAME, f"LSC Doorbell {self._device_id[-4:]}"),
            manufacturer="LSC Smart Connect / Tuya",
            model=f"Video Doorbell {self._hub.entry.data.get(CONF_FIRMWARE_VERSION, 'Unknown')}",
        )
        
        # Get device name for device-specific events
        device_name = hub.entry.data.get(CONF_NAME, f"LSC Doorbell {device_id[-4:]}").lower().replace(" ", "_")
        
        # Set up event listeners for device-specific events only
        device_button_event = f"{EVENT_BUTTON_PRESS}_{device_name}"
        device_motion_event = f"{EVENT_MOTION_DETECT}_{device_name}"
        
        # Listen only to this device's specific events
        hub.hass.bus.async_listen(device_button_event, self._handle_doorbell_event)
        hub.hass.bus.async_listen(device_motion_event, self._handle_motion_event)
    
    @property
    def native_value(self):
        """Return the state of the sensor."""
        return "Connected" if self._hub._protocol else "Disconnected"
    
    def _handle_doorbell_event(self, event):
        """Handle doorbell event."""
        # Since we're now listening only to device-specific events, we don't need to check the device ID
        # Increment the counter
        self._event_counters["doorbell"] += 1
        
        # Store timestamp
        self._last_doorbell_time = event.data.get(ATTR_TIMESTAMP, "Unknown")
        
        # Extract image URL if available
        if "image_url" in event.data:
            self._attr_extra_state_attributes["last_doorbell_image"] = event.data["image_url"]
            self._attr_extra_state_attributes["doorbell_image_url"] = event.data["image_url"]
            
        # Update the entity state to reflect new data - using event loop to avoid thread safety issues
        if self.hass:
            self.hass.add_job(self.async_write_ha_state)
    
    def _handle_motion_event(self, event):
        """Handle motion event."""
        # Since we're now listening only to device-specific events, we don't need to check the device ID
        # Increment the counter
        self._event_counters["motion"] += 1
        
        # Store timestamp
        self._last_motion_time = event.data.get(ATTR_TIMESTAMP, "Unknown")
        
        # Extract image URL if available
        if "image_url" in event.data:
            self._attr_extra_state_attributes["last_motion_image"] = event.data["image_url"]
            self._attr_extra_state_attributes["motion_image_url"] = event.data["image_url"]
            
        # Update the entity state to reflect new data - using event loop to avoid thread safety issues
        if self.hass:
            self.hass.add_job(self.async_write_ha_state)
            
    async def async_update(self):
        """Fetch latest heartbeat time when entity is updated."""
        self._last_heartbeat = self._hub.last_heartbeat
        
    @property
    def should_poll(self):
        """Return True if entity should be polled for state."""
        return True
        
    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        # Get current device IP
        host = self._hub.entry.data.get(CONF_HOST)
        
        # Get the latest heartbeat time
        last_heartbeat = self._hub.last_heartbeat or self._last_heartbeat or "Unknown"
        
        # Base attributes
        attrs = {
            "ip_address": host if host else "Unknown",
            "last_heartbeat": last_heartbeat,
            "device_id": self._device_id,
            "doorbell_count": self._event_counters["doorbell"],
            "motion_count": self._event_counters["motion"],
        }
        
        # Include last event times
        if self._last_doorbell_time:
            attrs["last_doorbell_time"] = self._last_doorbell_time
            
        if self._last_motion_time:
            attrs["last_motion_time"] = self._last_motion_time
        
        # We're removing all image URL attributes as requested
            
        return attrs