import asyncio
import logging
import base64
import json
import binascii
import struct
from typing import Any, Union, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from datetime import timedelta, datetime

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_LOCAL_KEY,
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_PORT,
    CONF_MAC,
    CONF_LAST_IP,
    CONF_DPS_MAP,
    DEFAULT_PORT,
    DEFAULT_DPS_MAP,
    EVENT_BUTTON_PRESS,
    EVENT_MOTION_DETECT,
    ATTR_DEVICE_ID,
    ATTR_IMAGE_DATA,
    ATTR_TIMESTAMP,
    SERVICE_GET_IMAGE_URL,
    DEFAULT_BUCKET
)

import voluptuous as vol

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required('devices'): vol.All(
            cv.ensure_list,
            [{
                vol.Required(CONF_NAME): cv.string,
                vol.Required(CONF_DEVICE_ID): cv.string,
                vol.Required(CONF_LOCAL_KEY): cv.string,
                vol.Optional(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_DPS_MAP, default=DEFAULT_DPS_MAP): dict,
                vol.Optional(CONF_MAC): cv.string,
                vol.Optional(CONF_LAST_IP): cv.string,
            }]
        )
    })
}, extra=vol.ALLOW_EXTRA)

# Create a named logger for this component
_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the component from YAML."""
    conf = config.get(DOMAIN)
    if not conf:
        return True

    for device_config in conf['devices']:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={'source': 'import'},
                data=device_config
            )
        )

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hub = LscTuyaHub(hass, entry)
    if not await hub.async_setup():
        return False

    hass.data[DOMAIN][entry.entry_id] = hub
        
    # Register services
    await async_register_services(hass)
        
    # Set up sensor platform using the newer method
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
        
    return True

async def async_register_services(hass: HomeAssistant):
    """Register custom services."""
    async def handle_get_image_url(call):
        """Handle get_image_url service call."""
        path = call.data.get("path")
        bucket = call.data.get("bucket", DEFAULT_BUCKET)
        return {"url": f"https://{bucket}.oss-us-west-1.aliyuncs.com{path}"}

    async def handle_reload(call):
        """Handle reload service call."""
        _LOGGER.info("Reloading LSC Tuya Doorbell integration")
        
        # Get all current config entries for our domain
        current_entries = hass.config_entries.async_entries(DOMAIN)
        
        # Unload all entries
        for entry in current_entries:
            _LOGGER.debug("Unloading config entry %s", entry.entry_id)
            await hass.config_entries.async_unload_platforms(entry, ["sensor"])
            hass.data[DOMAIN].pop(entry.entry_id, None)
        
        # Now set up all entries again
        for entry in current_entries:
            _LOGGER.debug("Setting up config entry %s", entry.entry_id)
            hass.async_create_task(
                hass.config_entries.async_setup(entry.entry_id)
            )
        
        _LOGGER.info("Successfully reloaded integration")

    # Register service for getting image URLs
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_IMAGE_URL,
        handle_get_image_url
    )
    
    # Register reload service
    hass.services.async_register(
        DOMAIN,
        "reload",
        handle_reload
    )

class TuyaDoorbellListener:
    """Listener for doorbell events."""
    
    def __init__(self, hub):
        """Initialize the listener."""
        self.hub = hub
        
    def status_updated(self, status):
        """Device updated status."""
        _LOGGER.debug("Status updated: %s", status)
        
        # Process each datapoint in status
        for dp, value in status.items():
            self.hub.hass.async_create_task(self.hub._handle_dps_update(dp, value))
            
    def disconnected(self):
        """Device disconnected."""
        _LOGGER.warning("Disconnected from device, scheduling reconnect")
        self.hub.hass.async_create_task(self.hub._schedule_reconnect())

class LscTuyaHub:
    """Hub for LSC Tuya Doorbell communication."""
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        from .network import async_scan_network
        self._async_scan_network = async_scan_network
        self.hass = hass
        self.entry = entry
        self.device = None
        self._protocol = None
        self._reconnect_delay = 10
        self._max_reconnect_delay = 300
        self.last_heartbeat = None
        self._listener = TuyaDoorbellListener(self)

    async def async_setup(self):
        """Set up the hub."""
        await self._async_connect()
        return True

    async def _async_connect(self):
        """Connect to the Tuya device with automatic IP rediscovery."""
        from .pytuya import connect

        config = self.entry.data
        host = config.get(CONF_HOST) or config.get(CONF_LAST_IP)
        port = config.get(CONF_PORT, DEFAULT_PORT)
        
        _LOGGER.debug(
            "Connecting to device %s (ID: %s) at %s:%s with key %s...",
            config.get(CONF_NAME),
            config.get(CONF_DEVICE_ID),
            host,
            port,
            config.get(CONF_LOCAL_KEY)[:5] + "..." if config.get(CONF_LOCAL_KEY) else None
        )
        
        # If no host or connection fails, try network scan
        if not host or not await self._test_connection(host, port):
            _LOGGER.info("No valid IP, starting network scan...")
            host = await self._rediscover_ip()
            
            if not host:
                _LOGGER.error("Device rediscovery failed")
                self.hass.async_create_task(self._schedule_reconnect())
                return
                
            # Update config with new IP
            _LOGGER.info("Found device at new IP: %s, updating configuration", host)
            
            # Store both the original host value (might be a subnet) and the last discovered IP
            updated_config = {**config, CONF_LAST_IP: host}
            
            # Update the config entry with the new data
            self.hass.config_entries.async_update_entry(
                self.entry,
                data=updated_config
            )

        try:
            # Connect to the device using PyTuya
            _LOGGER.debug("Connecting to device at %s:%s with PyTuya", host, port)
            
            # Use protocol version 3.3 which seems to work with most Tuya devices
            # including doorbells
            version = "3.3"
            
            # Enable debug for more detailed logs
            enable_debug = True
            
            self._protocol = await connect(
                host,
                config[CONF_DEVICE_ID],
                config[CONF_LOCAL_KEY],
                version,
                enable_debug,
                self._listener,
                port=port,
                timeout=10
            )
            
            _LOGGER.info("Connected to %s using PyTuya", config[CONF_NAME])
            self._reconnect_delay = 10
            
            # Start heartbeat
            self._protocol.start_heartbeat()
            
            # Try to get initial status
            status = None
            try:
                _LOGGER.debug("Getting initial device status...")
                status = await self._protocol.status()
                _LOGGER.debug("Initial status: %s", status)
            except Exception as e:
                _LOGGER.warning("Failed to get initial status: %s", str(e))
                
            # Try to detect available datapoints if no status
            if not status:
                try:
                    _LOGGER.debug("Trying to detect available datapoints...")
                    dps = await self._protocol.detect_available_dps()
                    _LOGGER.debug("Detected datapoints: %s", dps)
                except Exception as e:
                    _LOGGER.warning("Failed to detect datapoints: %s", str(e))
            
        except Exception as e:
            _LOGGER.error("Connection failed: %s", str(e))
            _LOGGER.debug("Connection error details", exc_info=True)
            # Schedule reconnect without awaiting since we're in an async function
            self.hass.async_create_task(self._schedule_reconnect())

    async def _handle_dps_update(self, dp: str, value: Any):
        """Handle DPS update and fire events."""
        config = self.entry.data
        event_type = None
        event_data = {}
        
        _LOGGER.debug("Handling DPS update for DP %s with value type %s", dp, type(value))
        
        # Get expected DPs from config - make sure they're strings
        dps_map = config.get(CONF_DPS_MAP, DEFAULT_DPS_MAP)
        button_dp = str(dps_map.get('button', "185"))
        motion_dp = str(dps_map.get('motion', "115"))
        
        _LOGGER.debug("Expected DPs - Button: %s, Motion: %s", button_dp, motion_dp)

        try:
            if dp == button_dp:
                _LOGGER.debug("Processing button press event (DP %s)", dp)
                try:
                    _LOGGER.debug("Raw value before decoding: %s", value)
                    
                    # Try to handle various payload formats
                    payload = None
                    
                    # Try to decode as base64
                    try:
                        if isinstance(value, str):
                            decoded = base64.b64decode(value).decode()
                            _LOGGER.debug("Decoded string: %s", decoded)
                            payload = json.loads(decoded)
                    except Exception as decode_err:
                        _LOGGER.debug("Base64 decode failed: %s", str(decode_err))
                        
                        # Try to parse as direct JSON
                        if isinstance(value, str):
                            try:
                                payload = json.loads(value)
                                _LOGGER.debug("Parsed as direct JSON")
                            except json.JSONDecodeError:
                                pass
                    
                    # If we still don't have a payload, use the raw value
                    if payload is None:
                        _LOGGER.debug("Using raw value as payload")
                        payload = {"raw_value": value}
                        
                    _LOGGER.debug("Final payload: %s", payload)
                    
                    event_type = EVENT_BUTTON_PRESS
                    event_data = {
                        ATTR_DEVICE_ID: config[CONF_DEVICE_ID],
                        ATTR_IMAGE_DATA: payload,
                        ATTR_TIMESTAMP: datetime.now().isoformat()
                    }
                except Exception as e:
                    _LOGGER.error("Error processing button payload: %s", str(e))
                    _LOGGER.debug("Button decode exception details", exc_info=True)
                    # Continue anyway to fire event with raw data
                    event_type = EVENT_BUTTON_PRESS
                    event_data = {
                        ATTR_DEVICE_ID: config[CONF_DEVICE_ID],
                        ATTR_IMAGE_DATA: {"raw_value": value},
                        ATTR_TIMESTAMP: datetime.now().isoformat()
                    }
                    
            elif dp == motion_dp:
                _LOGGER.debug("Processing motion detection event (DP %s)", dp)
                try:
                    _LOGGER.debug("Raw value before decoding: %s", value)
                    
                    # Try to handle various payload formats
                    payload = None
                    
                    # Try to decode as base64
                    try:
                        if isinstance(value, str):
                            decoded = base64.b64decode(value).decode()
                            _LOGGER.debug("Decoded string: %s", decoded)
                            payload = json.loads(decoded)
                    except Exception as decode_err:
                        _LOGGER.debug("Base64 decode failed: %s", str(decode_err))
                        
                        # Try to parse as direct JSON
                        if isinstance(value, str):
                            try:
                                payload = json.loads(value)
                                _LOGGER.debug("Parsed as direct JSON")
                            except json.JSONDecodeError:
                                pass
                    
                    # If we still don't have a payload, use the raw value
                    if payload is None:
                        _LOGGER.debug("Using raw value as payload")
                        payload = {"raw_value": value}
                        
                    _LOGGER.debug("Final payload: %s", payload)
                    
                    event_type = EVENT_MOTION_DETECT
                    event_data = {
                        ATTR_DEVICE_ID: config[CONF_DEVICE_ID],
                        ATTR_IMAGE_DATA: payload,
                        ATTR_TIMESTAMP: datetime.now().isoformat()
                    }
                except Exception as e:
                    _LOGGER.error("Error processing motion payload: %s", str(e))
                    _LOGGER.debug("Motion decode exception details", exc_info=True)
                    # Continue anyway to fire event with raw data
                    event_type = EVENT_MOTION_DETECT
                    event_data = {
                        ATTR_DEVICE_ID: config[CONF_DEVICE_ID],
                        ATTR_IMAGE_DATA: {"raw_value": value},
                        ATTR_TIMESTAMP: datetime.now().isoformat()
                    }
            else:
                _LOGGER.debug("DP %s not mapped to any known event (value: %s)", dp, value)

            if event_type:
                _LOGGER.info("Firing event %s with data: %s", event_type, event_data)
                self.hass.bus.async_fire(event_type, event_data)
                _LOGGER.debug("Event fired successfully")

        except Exception as e:
            _LOGGER.error("Unexpected error handling DP %s: %s", dp, str(e))
            _LOGGER.debug("Handler error details", exc_info=True)

    async def _schedule_reconnect(self):
        """Schedule a reconnect with exponential backoff."""
        self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)
        _LOGGER.info("Scheduling reconnect in %s seconds", self._reconnect_delay)
        async_call_later(self.hass, self._reconnect_delay, self._async_reconnect)
        _LOGGER.debug("Reconnect scheduled, protocol status: %s", 
                     "Valid" if self._protocol else "None")

    async def _async_reconnect(self, _):
        """Reconnect to the device."""
        _LOGGER.debug("Executing reconnection procedure")
        
        # Close existing connection if it exists
        if self._protocol is not None:
            try:
                await self._protocol.close()
            except Exception as e:
                _LOGGER.debug("Error closing connection: %s", str(e))
                
        # Connect again
        await self._async_connect()

    async def _test_connection(self, host: str, port: int) -> bool:
        """Test if we can connect to the device."""
        if not host:
            _LOGGER.debug("No host provided for connection test")
            return False
            
        _LOGGER.debug("Testing connection to %s:%s", host, port)
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=3
            )
            writer.close()
            await writer.wait_closed()
            _LOGGER.debug("Connection test successful for %s:%s", host, port)
            return True
        except Exception as e:
            _LOGGER.debug("Connection test failed for %s:%s: %s", host, port, str(e))
            return False

    async def _rediscover_ip(self) -> Optional[str]:
        """Rediscover device using ID and key."""
        config = self.entry.data
        device_id = config[CONF_DEVICE_ID]
        local_key = config[CONF_LOCAL_KEY]
        port = config.get(CONF_PORT, DEFAULT_PORT)
        
        _LOGGER.info("Starting network scan for device ID %s", device_id)
        
        # Scan the network for devices with the port open
        devices = await self._async_scan_network(port=port)
        
        if not devices:
            _LOGGER.warning("No devices found with port %s open during rediscovery", port)
            return None
            
        _LOGGER.info("Found %d device(s) with port %s open, trying to connect to each", len(devices), port)
        
        # Try to connect to each device with our credentials
        for ip, _ in devices:
            _LOGGER.debug("Trying to connect to %s with provided credentials", ip)
            try:
                from .pytuya import connect
                
                # Try to connect and get status
                protocol = await connect(
                    ip,
                    device_id,
                    local_key,
                    "3.3",  # Version
                    False,  # Debug
                    None,   # No listener for validation
                    port=port,
                    timeout=5
                )
                
                try:
                    # Try to get status
                    status = await protocol.status()
                    
                    # If we got a valid status, this is our device
                    if status is not None:
                        _LOGGER.info("Found device at new IP: %s (matched by credentials)", ip)
                        await protocol.close()
                        return ip
                except Exception:
                    _LOGGER.debug("Failed to get status from %s", ip)
                
                await protocol.close()
            except Exception as e:
                _LOGGER.debug("Failed to connect to %s: %s", ip, str(e))
        
        _LOGGER.error("Device not found in network scan")
        return None

    async def heartbeat(self) -> bool:
        """Send heartbeat to device and update timestamp."""
        if not self._protocol:
            _LOGGER.warning("Cannot send heartbeat - no device connection")
            return False
            
        try:
            result = await self._protocol.heartbeat()
            self.last_heartbeat = datetime.now().isoformat()
            _LOGGER.debug("Heartbeat result: %s", result)
            return True
        except Exception as e:
            _LOGGER.warning("Heartbeat failed: %s", str(e))
            _LOGGER.debug("Heartbeat exception details", exc_info=True)
            # Don't await here since we're in an async context
            self.hass.async_create_task(self._schedule_reconnect())
            return False
