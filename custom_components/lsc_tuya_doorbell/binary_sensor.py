"""Binary sensor entities for LSC Tuya Doorbell."""
from typing import Any, Dict
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_DEVICE_ID,
    CONF_FIRMWARE_VERSION,
    EVENT_BUTTON_PRESS,
    EVENT_MOTION_DETECT,
    ATTR_DEVICE_ID,
    ATTR_TIMESTAMP,
)
from .entity import TuyaDoorbellEntity
from .dp_entities import DPDefinition, DPType, DPCategory, get_dp_definitions

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, 
    config_entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up binary sensors based on a config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id]
    device_id = config_entry.data[CONF_DEVICE_ID]
    firmware_version = config_entry.data.get(CONF_FIRMWARE_VERSION, "Version 4")
    
    entities = []
    
    # Get DP definitions based on firmware version
    dp_definitions = get_dp_definitions(firmware_version)
    
    # Add event-based sensor entities
    entities.extend([
        DoorbellMotionSensor(hub, device_id),
        DoorbellButtonSensor(hub, device_id),
    ])
    
    # Add DP-based binary sensors (type=BOOLEAN, status_only category)
    for dp_id, dp_def in dp_definitions.items():
        if dp_def.dp_type == DPType.BOOLEAN and dp_def.category == DPCategory.STATUS_ONLY:
            entity = TuyaDoorbellBinarySensor(hub, device_id, dp_def)
            _LOGGER.info(f"Creating binary sensor entity: {dp_def.name} (DP {dp_id})")
            entities.append(entity)
    
    if entities:
        async_add_entities(entities)

class TuyaDoorbellBinarySensor(TuyaDoorbellEntity, BinarySensorEntity):
    """Representation of a Tuya doorbell binary sensor."""
    
    def __init__(self, hub, device_id, dp_definition):
        """Initialize the binary sensor."""
        super().__init__(hub, device_id, dp_definition)
        
        # Set device class based on DP code
        if "motion" in dp_definition.code:
            self._attr_device_class = BinarySensorDeviceClass.MOTION
        elif "door" in dp_definition.code or "bell" in dp_definition.code:
            self._attr_device_class = BinarySensorDeviceClass.OCCUPANCY
            
        # Set appropriate icon based on state and type
        if self._state is True:
            self._attr_icon = self._get_icon_for_state(True)
        elif self._state is False:
            self._attr_icon = self._get_icon_for_state(False)
        
    def _get_icon_for_state(self, state):
        """Get the appropriate icon based on state and sensor type."""
        if "motion" in self._dp_definition.code:
            return "mdi:motion-sensor" if state else "mdi:motion-sensor-off"
        elif "door" in self._dp_definition.code or "bell" in self._dp_definition.code:
            return "mdi:bell-ring" if state else "mdi:bell"
        else:
            return "mdi:check-circle" if state else "mdi:circle-outline"
            
    def handle_update(self, value):
        """Handle state updates from the device."""
        super().handle_update(value)
        # Update icon based on new state
        if value is True or value is False:
            self._attr_icon = self._get_icon_for_state(value)
        
    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        if self._state == "unknown" or self._state is None:
            return None
        return self._state is True
        
class DoorbellMotionSensor(BinarySensorEntity):
    """Representation of a Motion Detection Sensor."""
    
    def __init__(self, hub, device_id):
        """Initialize the sensor."""
        self._hub = hub
        self._device_id = device_id
        self._attr_name = f"Motion Detection"
        self._attr_unique_id = f"{device_id}_motion_event"
        self._attr_device_class = BinarySensorDeviceClass.MOTION
        self._state = False
        self._last_trigger = None
        self._attr_entity_registry_enabled_default = True
        
        # Set up device info
        from homeassistant.helpers.entity import DeviceInfo
        from .const import DOMAIN, CONF_NAME
        
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
    
    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        if self._state == "unknown":
            return None
        return self._state
        
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return device specific state attributes."""
        return {
            "last_triggered": self._last_trigger,
            "device_id": self._device_id
        }
        
    async def async_added_to_hass(self):
        """When entity is added to hass."""
        @callback
        def motion_handler(event):
            """Handle motion event."""
            # Check if the event is for this specific device
            if event.data.get(ATTR_DEVICE_ID) == self._device_id:
                self._state = True
                self._last_trigger = event.data.get(ATTR_TIMESTAMP)
                self.async_write_ha_state()
                
                # Reset after 10 seconds
                self.hass.loop.call_later(10, lambda: self._reset_state())

        # Register the event listener and ensure it's removed when the entity is removed
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_MOTION_DETECT, motion_handler)
        )
        
    def _reset_state(self):
        """Reset the state to off."""
        self._state = False
        self.async_write_ha_state()

class DoorbellButtonSensor(BinarySensorEntity):
    """Representation of a Doorbell Button Sensor."""
    
    def __init__(self, hub, device_id):
        """Initialize the sensor."""
        self._hub = hub
        self._device_id = device_id
        self._attr_name = f"Doorbell Button"
        self._attr_unique_id = f"{device_id}_button_event"
        self._attr_device_class = BinarySensorDeviceClass.OCCUPANCY
        self._state = False
        self._last_trigger = None
        self._attr_entity_registry_enabled_default = True
        
        # Set up device info
        from homeassistant.helpers.entity import DeviceInfo
        from .const import DOMAIN, CONF_NAME
        
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
    
    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        if self._state == "unknown":
            return None
        return self._state
        
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return device specific state attributes."""
        return {
            "last_triggered": self._last_trigger,
            "device_id": self._device_id
        }
        
    async def async_added_to_hass(self):
        """When entity is added to hass."""
        @callback
        def button_handler(event):
            """Handle button press event."""
            # Check if the event is for this specific device
            if event.data.get(ATTR_DEVICE_ID) == self._device_id:
                self._state = True
                self._last_trigger = event.data.get(ATTR_TIMESTAMP)
                self.async_write_ha_state()
                
                # Reset after 10 seconds
                self.hass.loop.call_later(10, lambda: self._reset_state())

        # Register the event listener and ensure it's removed when the entity is removed
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_BUTTON_PRESS, button_handler)
        )
        
    def _reset_state(self):
        """Reset the state to off."""
        self._state = False
        self.async_write_ha_state()