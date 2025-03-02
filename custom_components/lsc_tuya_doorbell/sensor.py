from homeassistant.components.sensor import SensorEntity, RestoreEntity
from homeassistant.core import callback
from .const import (
    DOMAIN,
    EVENT_BUTTON_PRESS,
    EVENT_MOTION_DETECT,
    ATTR_DEVICE_ID,
    ATTR_TIMESTAMP,
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_LAST_IP
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
    
    def __init__(self, hub, device_id):
        self._hub = hub
        self._device_id = device_id
        self._state = None
        self._last_trigger = None
        self.entity_id = f"sensor.lsc_tuya_motion_{device_id[-4:]}"
        
    @property
    def name(self):
        return f"LSC Tuya Motion {self._device_id[-4:]}"
        
    @property
    def unique_id(self):
        return f"{self._device_id}_motion"
        
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
            self._state = "Detected"
            self._last_trigger = event.data[ATTR_TIMESTAMP]
            self.async_write_ha_state()
            
            # Reset after 2 seconds
            self.hass.loop.call_later(2, lambda: self._reset_state())
            
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_MOTION_DETECT, motion_handler)
        )
        
    def _reset_state(self):
        self._state = "Idle"
        self.async_write_ha_state()

class LscTuyaButtonSensor(LscTuyaMotionSensor):
    """Representation of a Doorbell Button Sensor."""
    
    @property
    def name(self):
        return f"LSC Tuya Button {self._device_id[-4:]}"
        
    @property
    def unique_id(self):
        return f"{self._device_id}_button"
        
    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        
        @callback
        def button_handler(event):
            self._state = "Pressed"
            self._last_trigger = event.data[ATTR_TIMESTAMP]
            self.async_write_ha_state()
            
            # Reset after 2 seconds
            self.hass.loop.call_later(2, lambda: self._reset_state())
            
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_BUTTON_PRESS, button_handler)
        )

class LscTuyaStatusSensor(SensorEntity):
    """Device status sensor showing connection info."""
    
    def __init__(self, hub, device_id):
        self._hub = hub
        self._device_id = device_id
        self._attr_name = f"LSC Tuya Status {device_id[-4:]}"
        self._attr_unique_id = f"{device_id}_status"
        self._attr_icon = "mdi:connection"
        self.entity_id = f"sensor.lsc_tuya_status_{device_id[-4:]}"
        
    @property
    def state(self):
        return "Connected" if self._hub._protocol else "Disconnected"
        
    @property
    def extra_state_attributes(self):
        # Get current device IP (may have been rediscovered)
        host = self._hub.entry.data.get(CONF_HOST) or self._hub.entry.data.get(CONF_LAST_IP)
        
        return {
            "ip_address": host if host else "Unknown",
            "last_heartbeat": self._hub.last_heartbeat if self._hub.last_heartbeat else "Unknown",
            "device_id": self._device_id,
            "connection_status": "Active" if self._hub._protocol else "Disconnected"
        }
