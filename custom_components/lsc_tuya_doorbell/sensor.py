from homeassistant.components.sensor import SensorEntity, RestoreEntity
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from .const import (
    DOMAIN,
    EVENT_BUTTON_PRESS,
    EVENT_MOTION_DETECT,
    ATTR_DEVICE_ID,
    ATTR_TIMESTAMP,
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_LAST_IP,
    CONF_NAME
)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensors from a config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id]
    device_id = config_entry.data[CONF_DEVICE_ID]
    
    sensors = [
        LscTuyaMotionSensor(hub, device_id),
        LscTuyaButtonSensor(hub, device_id),
        LscTuyaStatusSensor(hub, device_id)
    ]
    
    async_add_entities(sensors)

class LscTuyaMotionSensor(SensorEntity, RestoreEntity):
    """Representation of a Motion Detection Sensor."""
    
    # Class-level constants
    SENSOR_TYPE = "motion"
    
    def __init__(self, hub, device_id):
        self._hub = hub
        self._device_id = device_id
        self._state = None
        self._last_trigger = None
        # Link to device via device_info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._hub.entry.data.get(CONF_NAME, f"LSC Doorbell {self._device_id[-4:]}"),
            manufacturer="LSC Smart Connect / Tuya",
            # model="Video Doorbell", # Add model if known/consistent
            # sw_version=..., # Potentially add later if available
        )
        
    @property
    def name(self):
        return f"LSC Tuya {self.SENSOR_TYPE.title()} {self._device_id[-4:]}"
        
    @property
    def unique_id(self):
        return f"{self._device_id}_{self.SENSOR_TYPE}"
        
    @property
    def state(self):
        return self._state
        
    @property
    def extra_state_attributes(self):
        return {
            "last_triggered": self._last_trigger,
            "device_id": self._device_id
        }
        
    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await super().async_added_to_hass()
        
        # Restore previous state
        last_state = await self.async_get_last_state()
        if last_state:
            self._state = last_state.state
        else:
            self._state = "Idle"
        
        @callback
        def motion_handler(event):
            """Handle motion event."""
            # Check if the event is for this specific device
            if event.data.get(ATTR_DEVICE_ID) == self._device_id:
                self._state = "Detected"
                self._last_trigger = event.data[ATTR_TIMESTAMP]
                self.async_write_ha_state()
                
                # Reset after 10 seconds (increased from 2 seconds for better visibility)
                self.hass.loop.call_later(10, lambda: self._reset_state())

        # Register the event listener and ensure it's removed when the entity is removed
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_MOTION_DETECT, motion_handler)
        )
        
    def _reset_state(self):
        self._state = "Idle"
        self.async_write_ha_state()

class LscTuyaButtonSensor(SensorEntity, RestoreEntity):
    """Representation of a Doorbell Button Sensor."""
    
    # Define the sensor type
    SENSOR_TYPE = "button"
    
    def __init__(self, hub, device_id):
        self._hub = hub
        self._device_id = device_id
        self._state = None
        self._last_trigger = None
        # Link to device via device_info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._hub.entry.data.get(CONF_NAME, f"LSC Doorbell {self._device_id[-4:]}"),
            manufacturer="LSC Smart Connect / Tuya",
            # model="Video Doorbell", # Add model if known/consistent
            # sw_version=..., # Potentially add later if available
        )
        
    @property
    def name(self):
        return f"LSC Tuya {self.SENSOR_TYPE.title()} {self._device_id[-4:]}"
        
    @property
    def unique_id(self):
        return f"{self._device_id}_{self.SENSOR_TYPE}"
        
    @property
    def state(self):
        return self._state
        
    @property
    def extra_state_attributes(self):
        return {
            "last_triggered": self._last_trigger,
            "device_id": self._device_id
        }
        
    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await super().async_added_to_hass()
        
        # Restore previous state
        last_state = await self.async_get_last_state()
        if last_state:
            self._state = last_state.state
        else:
            self._state = "Idle"
        
        @callback
        def button_handler(event):
            """Handle button press event."""
            # Check if the event is for this specific device
            if event.data.get(ATTR_DEVICE_ID) == self._device_id:
                self._state = "Pressed"
                self._last_trigger = event.data[ATTR_TIMESTAMP]
                self.async_write_ha_state()
                
                # Reset after 10 seconds (increased from 2 seconds for better visibility)
                self.hass.loop.call_later(10, lambda: self._reset_state())

        # Register the event listener and ensure it's removed when the entity is removed
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_BUTTON_PRESS, button_handler)
        )
        
    def _reset_state(self):
        self._state = "Idle"
        self.async_write_ha_state()

class LscTuyaStatusSensor(SensorEntity):
    """Device status sensor showing connection info."""
    
    # Class-level constants
    SENSOR_TYPE = "status"
    
    def __init__(self, hub, device_id):
        self._hub = hub
        self._device_id = device_id
        self._attr_name = f"LSC Tuya {self.SENSOR_TYPE.title()} {device_id[-4:]}"
        self._attr_unique_id = f"{device_id}_{self.SENSOR_TYPE}"
        self._attr_icon = "mdi:connection"
        self._last_heartbeat = None
        # Link to device via device_info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._hub.entry.data.get(CONF_NAME, f"LSC Doorbell {device_id[-4:]}"),
            manufacturer="LSC Smart Connect / Tuya",
            # model="Video Doorbell", # Add model if known/consistent
            # sw_version=..., # Potentially add later if available
        )
        
    @property
    def state(self):
        return "Connected" if self._hub._protocol else "Disconnected"
    
    async def async_update(self):
        """Fetch latest heartbeat time when entity is updated."""
        self._last_heartbeat = self._hub.last_heartbeat
        
    @property
    def should_poll(self):
        """Return True if entity should be polled for state."""
        return True
        
    @property
    def extra_state_attributes(self):
        # Get current device IP (may have been rediscovered)
        host = self._hub.entry.data.get(CONF_HOST) or self._hub.entry.data.get(CONF_LAST_IP)
        
        # Get the latest heartbeat time - default to the cached value or Unknown
        last_heartbeat = self._hub.last_heartbeat or self._last_heartbeat or "Unknown"
        
        return {
            "ip_address": host if host else "Unknown",
            "last_heartbeat": last_heartbeat,
            "device_id": self._device_id,
            "connection_status": "Active" if self._hub._protocol else "Disconnected"
        }
