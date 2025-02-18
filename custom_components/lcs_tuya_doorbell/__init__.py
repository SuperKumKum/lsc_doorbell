import asyncio
import logging
import base64
import json
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, Event
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from datetime import timedelta

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
    ATTR_TIMESTAMP
)
from datetime import datetime

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
    hub = LcsTuyaHub(hass, entry)
    if not await hub.async_setup():
        return False

    hass.data[DOMAIN][entry.entry_id] = hub
    return True

class LcsTuyaHub:
    """Hub for LCS Tuya Doorbell communication."""
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        from .network import async_scan_network
        self._async_scan_network = async_scan_network
        self.hass = hass
        self.entry = entry
        self.device = None
        self._connect_task = None
        self._reconnect_delay = 10
        self._max_reconnect_delay = 300

    async def async_setup(self):
        """Set up the hub."""
        await self._async_connect()
        return True

    async def _async_connect(self):
        """Connect to the Tuya device with automatic IP rediscovery."""
        from tinytuya import Device

        config = self.entry.data
        host = config.get(CONF_HOST) or config.get(CONF_LAST_IP)
        
        # If no host or connection fails, try network scan
        if not host or not await self._test_connection(host, config[CONF_PORT]):
            _LOGGER.info("No valid IP, starting network scan...")
            host = await self._rediscover_ip()
            
            if not host:
                _LOGGER.error("Device rediscovery failed")
                self._schedule_reconnect()
                return
                
            # Update config with new IP
            self.hass.config_entries.async_update_entry(
                self.entry,
                data={**config, CONF_LAST_IP: host}
            )

        self.device = Device(
            dev_id=config[CONF_DEVICE_ID],
            address=host,
            local_key=config[CONF_LOCAL_KEY],
            port=config[CONF_PORT],
            version=3.3
        )

        try:
            await self.hass.async_add_executor_job(self.device.connect)
            _LOGGER.info("Connected to %s", config[CONF_NAME])
            self._reconnect_delay = 10
            self._start_listener()
            self._start_heartbeat()
        except Exception as e:
            _LOGGER.error("Connection failed: %s", str(e))
            self._schedule_reconnect()

    def _start_listener(self):
        """Start listening for device updates."""
        self.hass.async_add_executor_job(self._device_listener)

    def _device_listener(self):
        """Listen for device updates."""
        while True:
            try:
                data = self.device.receive()
                if data:
                    self.hass.add_job(self._process_data, data)
            except ConnectionError:
                _LOGGER.warning("Connection lost, scheduling reconnect")
                self.hass.add_job(self._schedule_reconnect)
                break
            except Exception as e:
                _LOGGER.error("Error in listener: %s", str(e))
                self.hass.add_job(self._schedule_reconnect)
                break

    async def _process_data(self, data: dict):
        """Process incoming data from device."""
        dps = data.get('dps', {})
        for dp, value in dps.items():
            await self._handle_dps_update(dp, value)

    async def _handle_dps_update(self, dp: str, value: Any):
        """Handle DPS update and fire events."""
        config = self.entry.data
        event_type = None
        event_data = {}

        try:
            if dp == str(config[CONF_DPS_MAP].get('button')):
                decoded = base64.b64decode(value).decode()
                payload = json.loads(decoded)
                event_type = EVENT_BUTTON_PRESS
                event_data = {
                    ATTR_DEVICE_ID: config[CONF_DEVICE_ID],
                    ATTR_IMAGE_DATA: payload,
                    ATTR_TIMESTAMP: datetime.now().isoformat()
                }
            elif dp == str(config[CONF_DPS_MAP].get('motion')):
                decoded = base64.b64decode(value).decode()
                payload = json.loads(decoded)
                event_type = EVENT_MOTION_DETECT
                event_data = {
                    ATTR_DEVICE_ID: config[CONF_DEVICE_ID],
                    ATTR_IMAGE_DATA: payload,
                    ATTR_TIMESTAMP: datetime.now().isoformat()
                }

            if event_type:
                self.hass.bus.async_fire(event_type, event_data)
                _LOGGER.debug("Fired event %s: %s", event_type, event_data)

        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            _LOGGER.error("Error decoding payload from DP %s: %s", dp, str(e))

    def _schedule_reconnect(self):
        """Schedule a reconnect with exponential backoff."""
        self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)
        _LOGGER.info("Scheduling reconnect in %s seconds", self._reconnect_delay)
        async_call_later(self.hass, self._reconnect_delay, self._async_reconnect)

    async def _async_reconnect(self, _):
        """Reconnect to the device."""
        await self._async_connect()

    async def _test_connection(self, host: str, port: int) -> bool:
        """Test if we can connect to the device."""
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=3
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception as e:
            _LOGGER.debug("Connection test failed for %s:%s: %s", host, port, str(e))
            return False

    async def _rediscover_ip(self) -> str:
        """Rediscover device IP using MAC address."""
        config = self.entry.data
        if not config.get(CONF_MAC):
            _LOGGER.warning("Cannot rediscover device without MAC address")
            return None

        _LOGGER.info("Starting network scan for MAC %s", config[CONF_MAC])
        devices = await self._async_scan_network(port=config[CONF_PORT])
        
        for ip, mac in devices:
            if mac.lower() == config[CONF_MAC].lower():
                _LOGGER.info("Found device at new IP: %s", ip)
                return ip
        
        _LOGGER.warning("Device not found in network scan")
        return None

    def _start_heartbeat(self):
        """Start periodic heartbeat monitoring."""
        from homeassistant.helpers.event import async_track_time_interval
        
        def _handle_heartbeat(_):
            """Handle heartbeat interval."""
            _LOGGER.debug("Sending heartbeat to device")
            try:
                self.device.heartbeat()
            except Exception as e:
                _LOGGER.warning("Heartbeat failed: %s", str(e))
        
        async_track_time_interval(
            self.hass,
            _handle_heartbeat,
            timedelta(seconds=60)
        )
