import asyncio
import logging
import base64
import json
import binascii
import struct
import hashlib
import os
import time
from typing import Any, Union, Optional, Dict, List

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.storage import Store
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
    CONF_PROTOCOL_VERSION,
    CONF_FIRMWARE_VERSION,
    DEFAULT_PORT,
    DEFAULT_PROTOCOL_VERSION,
    DEFAULT_FIRMWARE_VERSION,
    DEFAULT_DPS_MAP,
    EVENT_BUTTON_PRESS,
    EVENT_MOTION_DETECT,
    EVENT_DEVICE_CONNECTED,
    EVENT_DEVICE_DISCONNECTED,
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
    
    # Register the device in the device registry
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.data[CONF_DEVICE_ID])},
        name=entry.data.get(CONF_NAME, f"LSC Doorbell {entry.data[CONF_DEVICE_ID][-4:]}"),
        manufacturer="LSC Smart Connect / Tuya",
        model=f"Video Doorbell {entry.data.get(CONF_FIRMWARE_VERSION, 'Unknown')}",
        sw_version=entry.data.get(CONF_FIRMWARE_VERSION, "Unknown"),
    )
        
    # Set up all platforms using the newer method
    await hass.config_entries.async_forward_entry_setups(
        entry, ["sensor", "binary_sensor", "switch", "select", "number"]
    )
    
    # Register update listener for config entry changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
        
    return True

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    _LOGGER.info("Reloading configuration for %s", entry.data.get(CONF_NAME, "LSC Doorbell"))
    
    try:
        # Check current entry state to avoid state conflicts
        from homeassistant.config_entries import ConfigEntryState
        
        if entry.state != ConfigEntryState.LOADED:
            _LOGGER.warning(
                "Cannot reload config entry %s because it is not loaded (state: %s)",
                entry.entry_id, entry.state
            )
            return
            
        # Get the existing hub
        hub = hass.data[DOMAIN].get(entry.entry_id)
        if hub:
            # Save cached data before unloading
            await hub._save_dps_hashes()
            
            # Close existing connections
            if hub._protocol:
                await hub._protocol.close()
                hub._protocol = None
        
        # Unload platforms
        try:
            _LOGGER.debug("Unloading platforms for entry %s", entry.entry_id)
            await hass.config_entries.async_unload_platforms(entry, ["sensor", "binary_sensor", "switch", "select", "number"])
        except Exception as unload_err:
            _LOGGER.warning("Error unloading platforms: %s", str(unload_err))
        
        # Remove the hub from data
        if entry.entry_id in hass.data[DOMAIN]:
            hass.data[DOMAIN].pop(entry.entry_id)
        
        # Wait briefly to ensure unload completes 
        await asyncio.sleep(1)
        
        # Check if the entry is now in a state ready to be set up
        if entry.state == ConfigEntryState.NOT_LOADED:
            # Reload the config entry
            _LOGGER.debug("Setting up entry %s after unload", entry.entry_id)
            reload_result = await hass.config_entries.async_setup(entry.entry_id)
            
            if reload_result:
                _LOGGER.info("Successfully reloaded configuration for %s", entry.data.get(CONF_NAME, "LSC Doorbell"))
            else:
                _LOGGER.error("Failed to reload configuration for %s", entry.data.get(CONF_NAME, "LSC Doorbell"))
        else:
            _LOGGER.warning(
                "Cannot set up entry %s because it is in state %s, not NOT_LOADED", 
                entry.entry_id, entry.state
            )
    except Exception as reload_err:
        _LOGGER.error("Error reloading configuration: %s", str(reload_err))

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    hub = hass.data[DOMAIN].pop(entry.entry_id)
    
    # Save DPS hashes to storage before unloading
    await hub._save_dps_hashes()
    
    if hub._protocol:
        await hub._protocol.close()
    
    # Unload all platforms
    return await hass.config_entries.async_unload_platforms(
        entry, ["sensor", "binary_sensor", "switch", "select", "number"]
    )

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
        
        # Import ConfigEntryState to check state
        from homeassistant.config_entries import ConfigEntryState
        
        # Get all current config entries for our domain
        current_entries = hass.config_entries.async_entries(DOMAIN)
        
        # Track which entries were unloaded
        unloaded_entries = []
        
        # Unload all entries
        for entry in current_entries:
            try:
                if entry.state == ConfigEntryState.LOADED:
                    _LOGGER.debug("Unloading config entry %s", entry.entry_id)
                    # Unload all platforms that might be in use
                    await hass.config_entries.async_unload_platforms(
                        entry, ["sensor", "binary_sensor", "switch", "select", "number"]
                    )
                    
                    # Remove hub from data
                    if entry.entry_id in hass.data[DOMAIN]:
                        hub = hass.data[DOMAIN].pop(entry.entry_id, None)
                        # Close any active connections
                        if hub and hasattr(hub, '_protocol') and hub._protocol:
                            try:
                                await hub._protocol.close()
                            except Exception as e:
                                _LOGGER.warning("Error closing protocol during reload: %s", str(e))
                    
                    unloaded_entries.append(entry.entry_id)
                else:
                    _LOGGER.warning("Skipping entry %s (state: %s)", entry.entry_id, entry.state)
            except Exception as e:
                _LOGGER.error("Error unloading entry %s: %s", entry.entry_id, str(e))
        
        # Wait briefly to ensure unload completes
        await asyncio.sleep(1)
        
        # Now set up entries that were successfully unloaded
        for entry_id in unloaded_entries:
            _LOGGER.debug("Setting up config entry %s", entry_id)
            try:
                await hass.config_entries.async_setup(entry_id)
            except Exception as setup_err:
                _LOGGER.error("Error setting up entry %s: %s", entry_id, str(setup_err))
        
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
        # Track last disconnect time to prevent reconnect storms
        self._last_disconnect_time = None
        
    def status_updated(self, status):
        """Device updated status."""
        _LOGGER.debug("Status updated: %s", status)
        
        # Process each datapoint in status
        for dp, value in status.items():
            self.hub.hass.async_create_task(self.hub._handle_dps_update(dp, value))
            
    def disconnected(self):
        """Device disconnected."""
        # Import here to avoid circular imports
        from datetime import datetime, timedelta
        
        # Check if we've disconnected too recently (prevent rapid reconnect cycle)
        now = datetime.now()
        if self._last_disconnect_time is not None:
            time_since_last = now - self._last_disconnect_time
            if time_since_last < timedelta(seconds=5):
                _LOGGER.warning("Multiple disconnects detected within 5 seconds. Increasing backoff.")
                # Double the reconnect delay to slow down reconnection attempts
                self.hub._reconnect_delay = min(self.hub._reconnect_delay * 2, self.hub._max_reconnect_delay)
        
        # Update the last disconnect time
        self._last_disconnect_time = now
        
        # Fire a disconnection event
        config = self.hub.entry.data
        self.hub.hass.bus.async_fire(
            EVENT_DEVICE_DISCONNECTED, 
            {
                ATTR_DEVICE_ID: config[CONF_DEVICE_ID],
                ATTR_TIMESTAMP: datetime.now().isoformat(),
                "name": config[CONF_NAME]
            }
        )
        
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
        self._heartbeat_timer = None
        self._listener = TuyaDoorbellListener(self)
        
        # Entity registration dictionary
        self._registered_entities = {}
        
        # Set up persistent storage for DPS hashes
        self._dps_hashes = {}
        self._storage = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}_dps_hashes")
        self._load_dps_hashes()
        
        # Initialize tracking variables for momentary switches
        self._dp_command_tracking = {}

    async def async_setup(self):
        """Set up the hub."""
        # Print information about firmware version and DPs
        firmware_version = self.entry.data.get(CONF_FIRMWARE_VERSION, DEFAULT_FIRMWARE_VERSION)
        from .dp_entities import get_dp_definitions
        
        # Log all available DPs for this firmware version
        dps = get_dp_definitions(firmware_version)
        _LOGGER.info(f"Setting up device with firmware {firmware_version}, {len(dps)} available DPs:")
        for dp_id, dp_def in dps.items():
            _LOGGER.info(f"  DP {dp_id}: {dp_def.name} ({dp_def.dp_type}, {dp_def.category})")
            
        # Connect to the device
        await self._async_connect()
        
        # Set up a periodic heartbeat check
        async def check_heartbeat(now=None):
            """Check if heartbeats are being received."""
            if self._protocol:
                # Try sending a heartbeat if it's been more than 60 seconds
                await self.heartbeat()
                
        self._heartbeat_timer = async_track_time_interval(
            self.hass, check_heartbeat, timedelta(seconds=60)
        )
                
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
            
            # Use the protocol version from config, defaulting to 3.3 if not specified
            version = config.get(CONF_PROTOCOL_VERSION, DEFAULT_PROTOCOL_VERSION)
            
            # Enable debug for more detailed logs
            enable_debug = True
            
            try:
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
                
                # Start heartbeat and record initial timestamp
                self._protocol.start_heartbeat()
                self.last_heartbeat = datetime.now().isoformat()
                
                # Fire a connection event
                self.hass.bus.async_fire(
                    EVENT_DEVICE_CONNECTED, 
                    {
                        ATTR_DEVICE_ID: config[CONF_DEVICE_ID],
                        ATTR_TIMESTAMP: datetime.now().isoformat(),
                        "host": host,
                        "name": config[CONF_NAME]
                    }
                )
                _LOGGER.info("Fired device connected event")
                
                # Update all sensors for this device
                device_id = config[CONF_DEVICE_ID]
                
                # Find and update all sensors related to this device
                for entity_id in self.hass.states.async_entity_ids("sensor"):
                    if entity_id.startswith("sensor.lsc_tuya_") and device_id[-4:] in entity_id:
                        _LOGGER.debug("Updating entity: %s", entity_id)
                        self.hass.async_create_task(
                            self.hass.services.async_call(
                                "homeassistant", "update_entity",
                                {"entity_id": entity_id},
                                blocking=False
                            )
                        )
            except Exception as e:
                _LOGGER.error("Error establishing connection: %s", str(e))
                self._protocol = None
                # Allow the exception to propagate so the reconnect mechanism can handle it
            
            # Try to get values for all DPs defined for this firmware version
            try:
                _LOGGER.info("Getting initial status for all defined DPs...")
                # Get available DPs for this firmware version
                firmware_version = self.entry.data.get(CONF_FIRMWARE_VERSION, DEFAULT_FIRMWARE_VERSION)
                from .dp_entities import get_dp_definitions
                dp_definitions = get_dp_definitions(firmware_version)
                
                # First try getting all status at once
                status = None
                try:
                    _LOGGER.debug("Getting full device status...")
                    status = await self._protocol.status()
                    _LOGGER.debug("Initial status response: %s", status)
                except Exception as e:
                    _LOGGER.warning("Failed to get full status: %s", str(e))
                
                # Update entities with values from status response
                if status:
                    for dp, value in status.items():
                        _LOGGER.info(f"Initial value for DP {dp}: {value}")
                        # Process the datapoint update
                        await self._handle_dps_update(dp, value)
                
                # For any DPs not in status, query them individually
                for dp_id in dp_definitions:
                    if status and dp_id in status:
                        # Already handled from status
                        continue
                        
                    try:
                        _LOGGER.debug(f"Querying individual DP {dp_id}...")
                        dp_value = await self._protocol.get_dp(dp_id)
                        if dp_value is not None:
                            _LOGGER.info(f"Got value for DP {dp_id}: {dp_value}")
                            await self._handle_dps_update(dp_id, dp_value)
                    except Exception as dp_err:
                        _LOGGER.debug(f"Could not query DP {dp_id}: {dp_err}")
                    
            except Exception as e:
                _LOGGER.warning("Failed to get initial DP values: %s", str(e))
                
            # Try to detect available datapoints if no status was retrieved
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

    def _load_dps_hashes(self):
        """Load DPS hashes from persistent storage."""
        async def _load_from_storage():
            try:
                data = await self._storage.async_load()
                if data:
                    self._dps_hashes = data
                    _LOGGER.debug("Loaded DPS hashes from storage: %s", self._dps_hashes)
                else:
                    self._dps_hashes = {}
                    _LOGGER.debug("No DPS hashes in storage, starting fresh")
            except Exception as e:
                _LOGGER.error("Error loading DPS hashes: %s", str(e))
                self._dps_hashes = {}
        
        # Schedule loading from storage
        self.hass.async_create_task(_load_from_storage())
    
    async def _save_dps_hashes(self):
        """Save DPS hashes to persistent storage."""
        await self._storage.async_save(self._dps_hashes)
        _LOGGER.debug("Saved DPS hashes to storage: %s", self._dps_hashes)
    
    def _calculate_hash(self, value: Any) -> str:
        """Calculate a consistent hash for any value."""
        # Convert value to a stable string representation for hashing
        if isinstance(value, dict) or isinstance(value, list):
            value_str = json.dumps(value, sort_keys=True)
        else:
            value_str = str(value)
        
        # Calculate hash using SHA-256
        hash_obj = hashlib.sha256(value_str.encode('utf-8'))
        return hash_obj.hexdigest()
        
    def _process_event_payload(self, value: Any) -> tuple[dict, str]:
        """Process event payload using multiple decoding strategies.
        
        Returns:
            tuple: (Decoded payload as dict, Format description string)
        """
        payload = None
        format_desc = "unknown"
        
        # Case 1: Already a dictionary
        if isinstance(value, dict):
            _LOGGER.debug("Payload is already a dictionary")
            return value, "direct_dict"
            
        # Case 2: Try to decode as base64 and parse as JSON
        if isinstance(value, str):
            try:
                # First try standard base64
                decoded = base64.b64decode(value).decode()
                _LOGGER.debug("Decoded standard base64 string: %s", decoded)
                payload = json.loads(decoded)
                return payload, "base64_json"
            except Exception as e:
                _LOGGER.debug("Standard base64 decode failed: %s", str(e))
                
                # Try with padding adjustments
                try:
                    # Add padding if needed
                    padded_value = value
                    while len(padded_value) % 4 != 0:
                        padded_value += "="
                    
                    decoded = base64.b64decode(padded_value).decode()
                    _LOGGER.debug("Decoded padded base64 string: %s", decoded)
                    payload = json.loads(decoded)
                    return payload, "padded_base64_json"
                except Exception as e2:
                    _LOGGER.debug("Padded base64 decode failed: %s", str(e2))
                    
                    # Try to decode as URL-safe base64
                    try:
                        decoded = base64.urlsafe_b64decode(value + "=" * (4 - len(value) % 4) % 4).decode()
                        _LOGGER.debug("Decoded URL-safe base64 string: %s", decoded)
                        payload = json.loads(decoded)
                        return payload, "urlsafe_base64_json"
                    except Exception as e3:
                        _LOGGER.debug("URL-safe base64 decode failed: %s", str(e3))
        
        # Case 3: Try to parse directly as JSON
        if isinstance(value, str):
            try:
                payload = json.loads(value)
                _LOGGER.debug("Parsed directly as JSON")
                return payload, "direct_json"
            except json.JSONDecodeError as e:
                _LOGGER.debug("Direct JSON parse failed: %s", str(e))
                
                # Try to fix common JSON issues
                try:
                    # Fix single quotes to double quotes
                    fixed_value = value.replace("'", '"')
                    payload = json.loads(fixed_value)
                    _LOGGER.debug("Parsed as fixed JSON (single quotes)")
                    return payload, "fixed_json_quotes"
                except json.JSONDecodeError:
                    _LOGGER.debug("Fixed JSON parse failed")
        
        # Case 4: Try to extract JSON from the string (sometimes surrounded by non-JSON text)
        if isinstance(value, str):
            try:
                # Look for JSON-like patterns
                import re
                json_pattern = r'(\{.*\}|\[.*\])'
                match = re.search(json_pattern, value)
                if match:
                    potential_json = match.group(1)
                    payload = json.loads(potential_json)
                    _LOGGER.debug("Extracted and parsed JSON substring")
                    return payload, "extracted_json"
            except Exception as e:
                _LOGGER.debug("JSON extraction failed: %s", str(e))
        
        # Case 5: Handle binary data
        if isinstance(value, bytes):
            try:
                # Try to decode as UTF-8
                decoded = value.decode('utf-8')
                _LOGGER.debug("Decoded bytes as UTF-8: %s", decoded)
                
                # Try to parse as JSON
                try:
                    payload = json.loads(decoded)
                    return payload, "bytes_utf8_json"
                except json.JSONDecodeError:
                    # Return as string
                    return {"string_value": decoded}, "bytes_utf8"
            except UnicodeDecodeError:
                # If not UTF-8, convert to hex for debugging
                hex_data = binascii.hexlify(value).decode('ascii')
                _LOGGER.debug("Converted binary data to hex: %s", hex_data)
                return {"hex_data": hex_data}, "bytes_hex"
        
        # Case 6: Boolean value (handle True or False)
        if isinstance(value, bool):
            return {"boolean_value": value}, "boolean"
            
        # Case 7: Numeric value
        if isinstance(value, (int, float)):
            return {"numeric_value": value}, "numeric"
            
        # Case 8: Process as string if all else fails but not None
        if value is not None:
            # Handle as string
            string_value = str(value)
            return {"string_value": string_value}, "string"
        
        # Final fallback - empty dict with raw value
        return {"raw_value": value}, "fallback"
        
    def _extract_image_url(self, payload: Any) -> Optional[str]:
        """Extract image URL from payload if available."""
        if not isinstance(payload, dict):
            return None
            
        try:
            _LOGGER.debug(f"Attempting to extract image URL from payload: {payload}")
            
            # Format 1: Tuya cloud storage format with bucket and files
            if "bucket" in payload and "files" in payload:
                bucket = payload.get("bucket", DEFAULT_BUCKET)
                if isinstance(payload["files"], list) and len(payload["files"]) > 0:
                    file_entry = payload["files"][0]
                    if isinstance(file_entry, list) and len(file_entry) > 0:
                        path = file_entry[0]
                        image_url = f"https://{bucket}.oss-us-west-1.aliyuncs.com{path}"
                        _LOGGER.info(f"Extracted image URL (Format 1): {image_url}")
                        return image_url
            
            # Format 2: Direct URL in 'url' field
            if "url" in payload and isinstance(payload["url"], str):
                url = payload["url"]
                if url.startswith(("http://", "https://")):
                    _LOGGER.info(f"Extracted image URL (Format 2): {url}")
                    return url
            
            # Format 3: URL in 'image_url' field
            if "image_url" in payload and isinstance(payload["image_url"], str):
                url = payload["image_url"]
                if url.startswith(("http://", "https://")):
                    _LOGGER.info(f"Extracted image URL (Format 3): {url}")
                    return url
            
            # Format 4: Cloud image with fileId and timeStamp
            if "fileId" in payload and "timeStamp" in payload:
                file_id = payload.get("fileId")
                time_stamp = payload.get("timeStamp")
                bucket = payload.get("bucket", DEFAULT_BUCKET)
                
                if file_id and time_stamp:
                    path = f"/tuya-doorbell/{file_id}_{time_stamp}.jpg"
                    image_url = f"https://{bucket}.oss-us-west-1.aliyuncs.com{path}"
                    _LOGGER.info(f"Extracted image URL (Format 4): {image_url}")
                    return image_url
            
            # Format 5: Looking for image path patterns in any string value
            for key, value in payload.items():
                if isinstance(value, str):
                    # Check if it looks like a URL
                    if value.startswith(("http://", "https://")):
                        _LOGGER.info(f"Extracted image URL (Format 5) from key '{key}': {value}")
                        return value
                    
                    # Check for path patterns that might be part of a URL
                    if value.startswith("/") and (
                        ".jpg" in value.lower() or 
                        ".jpeg" in value.lower() or 
                        ".png" in value.lower()
                    ):
                        # Construct full URL with default bucket
                        bucket = DEFAULT_BUCKET
                        image_url = f"https://{bucket}.oss-us-west-1.aliyuncs.com{value}"
                        _LOGGER.info(f"Constructed image URL (Format 5) from path '{value}': {image_url}")
                        return image_url
                        
            # Format 6: Nested objects
            for key, value in payload.items():
                if isinstance(value, dict):
                    nested_url = self._extract_image_url(value)
                    if nested_url:
                        _LOGGER.info(f"Extracted image URL (Format 6) from nested object '{key}': {nested_url}")
                        return nested_url
            
            _LOGGER.debug("No image URL found in payload")
            
        except Exception as ex:
            _LOGGER.error(f"Error extracting image URL: {ex}")
            _LOGGER.debug("Image URL extraction error details", exc_info=True)
            
        return None
    
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
        
        # Calculate hash of the new value
        current_hash = self._calculate_hash(value)
        previous_hash = self._dps_hashes.get(dp)
        
        # Check if we've seen this exact payload before
        if previous_hash == current_hash:
            _LOGGER.info("Ignoring duplicate update for DP %s (hash: %s)", dp, current_hash[:8])
            return
        
        # Update the hash for this DP
        self._dps_hashes[dp] = current_hash
        # Save the updated hashes
        self.hass.async_create_task(self._save_dps_hashes())
        
        # Update any entities registered for this DP
        if dp in self._registered_entities:
            for entity in self._registered_entities[dp]:
                # Check if this is a momentary control (special handling)
                is_momentary = False
                if hasattr(entity, '_is_momentary'):
                    is_momentary = entity._is_momentary
                
                # For momentary controls, add special handling to track/restore state
                if is_momentary:
                    _LOGGER.debug(f"Handling update for momentary control {entity.entity_id}: {value}")
                    # Let entity decide how to handle this update (may maintain virtual state)
                
                # Pass update to entity's handler
                if hasattr(entity, 'handle_update'):
                    entity.handle_update(value)

        try:
            if dp == button_dp:
                _LOGGER.debug("Processing button press event (DP %s)", dp)
                try:
                    _LOGGER.debug("Raw value before decoding: %s", value)
                    
                    # Process payload with enhanced handling of different formats
                    payload, decoded_format = self._process_event_payload(value)
                    _LOGGER.debug(f"Decoded button payload using {decoded_format}: {payload}")
                    
                    # Extract image URL if available
                    image_url = self._extract_image_url(payload)
                    
                    # Create event data
                    event_type = EVENT_BUTTON_PRESS
                    event_data = {
                        ATTR_DEVICE_ID: config[CONF_DEVICE_ID],
                        ATTR_IMAGE_DATA: payload,
                        ATTR_TIMESTAMP: datetime.now().isoformat(),
                        "decode_format": decoded_format
                    }
                    
                    # Add image URL to event data if available
                    if image_url:
                        event_data["image_url"] = image_url
                        _LOGGER.info(f"Adding doorbell image URL to event: {image_url}")
                except Exception as e:
                    _LOGGER.error("Error processing button payload: %s", str(e))
                    _LOGGER.debug("Button decode exception details", exc_info=True)
                    # Continue anyway to fire event with raw data
                    event_type = EVENT_BUTTON_PRESS
                    event_data = {
                        ATTR_DEVICE_ID: config[CONF_DEVICE_ID],
                        ATTR_IMAGE_DATA: {"raw_value": value},
                        ATTR_TIMESTAMP: datetime.now().isoformat(),
                        "decode_format": "error_fallback"
                    }
                    
            elif dp == motion_dp:
                _LOGGER.debug("Processing motion detection event (DP %s)", dp)
                try:
                    _LOGGER.debug("Raw value before decoding: %s", value)
                    
                    # Process payload with enhanced handling of different formats
                    payload, decoded_format = self._process_event_payload(value)
                    _LOGGER.debug(f"Decoded motion payload using {decoded_format}: {payload}")
                    
                    # Extract image URL if available
                    image_url = self._extract_image_url(payload)
                    
                    # Create event data
                    event_type = EVENT_MOTION_DETECT
                    event_data = {
                        ATTR_DEVICE_ID: config[CONF_DEVICE_ID],
                        ATTR_IMAGE_DATA: payload,
                        ATTR_TIMESTAMP: datetime.now().isoformat(),
                        "decode_format": decoded_format
                    }
                    
                    # Add image URL to event data if available
                    if image_url:
                        event_data["image_url"] = image_url
                        _LOGGER.info(f"Adding motion image URL to event: {image_url}")
                except Exception as e:
                    _LOGGER.error("Error processing motion payload: %s", str(e))
                    _LOGGER.debug("Motion decode exception details", exc_info=True)
                    # Continue anyway to fire event with raw data
                    event_type = EVENT_MOTION_DETECT
                    event_data = {
                        ATTR_DEVICE_ID: config[CONF_DEVICE_ID],
                        ATTR_IMAGE_DATA: {"raw_value": value},
                        ATTR_TIMESTAMP: datetime.now().isoformat(),
                        "decode_format": "error_fallback"
                    }
            else:
                _LOGGER.debug("DP %s not mapped to any known event (value: %s)", dp, value)

            if event_type:
                _LOGGER.info("Firing event %s with data: %s (hash: %s)", event_type, event_data, current_hash[:8])
                self.hass.bus.async_fire(event_type, event_data)
                _LOGGER.debug("Event fired successfully")

        except Exception as e:
            _LOGGER.error("Unexpected error handling DP %s: %s", dp, str(e))
            _LOGGER.debug("Handler error details", exc_info=True)

    async def _schedule_reconnect(self):
        """Schedule a reconnect with exponential backoff."""
        # Clear the protocol to ensure we know we're disconnected
        self._protocol = None
        
        # Calculate backoff delay with a random jitter to prevent reconnection storms
        import random
        jitter = random.uniform(0.8, 1.2)  # Add 20% randomness
        self._reconnect_delay = min(self._reconnect_delay * 2 * jitter, self._max_reconnect_delay)
        
        _LOGGER.info("Scheduling reconnect in %.1f seconds", self._reconnect_delay)
        
        # Schedule the reconnection
        async_call_later(self.hass, self._reconnect_delay, self._async_reconnect)
        _LOGGER.debug("Reconnect scheduled")

    async def _async_reconnect(self, _):
        """Reconnect to the device."""
        _LOGGER.info("Executing reconnection procedure")
        
        # Check if protocol already exists - might be a stale reconnect call
        if self._protocol is not None:
            _LOGGER.debug("Connection is already established, skipping reconnect")
            return
            
        try:        
            # Connect again
            _LOGGER.info("Attempting to reconnect to device")
            await self._async_connect()
            
            if self._protocol:
                _LOGGER.info("Reconnection successful")
                # Reset the reconnect delay on successful connection
                self._reconnect_delay = 10
                
                # Update entities to show connected state
                for entity_id in self.hass.states.async_entity_ids("sensor"):
                    if entity_id.startswith("sensor.lsc_tuya_") and entity_id.endswith("_connection_status"):
                        _LOGGER.debug("Requesting update for sensor %s", entity_id)
                        self.hass.async_create_task(
                            self.hass.services.async_call(
                                "homeassistant", "update_entity", 
                                {"entity_id": entity_id}, blocking=False
                            )
                        )
            else:
                _LOGGER.warning("Reconnection attempt failed, will retry later")
                # Schedule another reconnect attempt
                await self._schedule_reconnect()
        except Exception as e:
            _LOGGER.error("Error during reconnection attempt: %s", str(e))
            _LOGGER.debug("Reconnection error details", exc_info=True)
            # Schedule another reconnect attempt
            await self._schedule_reconnect()

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
                # Use the protocol version from config, defaulting to 3.3 if not specified
                protocol_version = config.get(CONF_PROTOCOL_VERSION, DEFAULT_PROTOCOL_VERSION)
                protocol = await connect(
                    ip,
                    device_id,
                    local_key,
                    protocol_version,  # Use configured version
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

    def register_entity(self, dp_id: str, entity):
        """Register an entity for DP updates."""
        if dp_id not in self._registered_entities:
            self._registered_entities[dp_id] = []
        if entity not in self._registered_entities[dp_id]:
            self._registered_entities[dp_id].append(entity)
            _LOGGER.debug("Registered entity for DP %s: %s", dp_id, entity.entity_id if hasattr(entity, 'entity_id') else entity)

    def unregister_entity(self, dp_id: str, entity):
        """Unregister an entity from DP updates."""
        if dp_id in self._registered_entities and entity in self._registered_entities[dp_id]:
            self._registered_entities[dp_id].remove(entity)
            _LOGGER.debug("Unregistered entity for DP %s: %s", dp_id, entity.entity_id if hasattr(entity, 'entity_id') else entity)

    async def set_dp(self, dp_id: str, value: Any) -> bool:
        """Set a datapoint value on the device."""
        if not self._protocol:
            _LOGGER.warning(f"Cannot set DP {dp_id}: No active connection")
            return False
        
        # Make sure dp_id is a string
        dp_id_str = str(dp_id)
        
        # Create a unique identifier for this update request for tracking
        import uuid
        update_id = str(uuid.uuid4())[:8]
        
        # Check if this DP is a momentary control by checking entity registry
        is_momentary = False
        if dp_id_str in self._registered_entities:
            for entity in self._registered_entities[dp_id_str]:
                if hasattr(entity, '_is_momentary') and entity._is_momentary:
                    is_momentary = True
                    _LOGGER.debug(f"[{update_id}] DP {dp_id} is registered as a momentary control")
                    break
        
        # Track commands for this DP to avoid duplicates
        dp_key = f"dp_{dp_id_str}"
        if dp_key not in self._dp_command_tracking:
            self._dp_command_tracking[dp_key] = {
                "last_value": None,
                "last_time": 0
            }
            
        # Check if this is a duplicate command (same value sent recently)
        tracking = self._dp_command_tracking[dp_key]
        current_time = time.time()
        if (tracking["last_value"] == value and 
            current_time - tracking["last_time"] < 5):
            _LOGGER.debug(f"[{update_id}] Skipping duplicate command for DP {dp_id}: {value} (sent {current_time - tracking['last_time']:.1f}s ago)")
            return True
            
        # Update tracking
        tracking["last_value"] = value
        tracking["last_time"] = current_time
        
        try:
            _LOGGER.info(f"[{update_id}] Setting DP {dp_id} to {value} for device {self.entry.data.get(CONF_DEVICE_ID)}")
            
            # Call the protocol's set_dp method with more detailed error handling
            result = await self._protocol.set_dp(value, dp_id_str)
            _LOGGER.info(f"[{update_id}] Set DP command sent, result: {result}")
            
            # For momentary controls, we don't need to verify since they'll revert immediately
            if is_momentary:
                _LOGGER.debug(f"[{update_id}] Not verifying momentary control since it will auto-revert")
                
                # Update entities with the requested value
                if dp_id_str in self._registered_entities:
                    for entity in self._registered_entities[dp_id_str]:
                        if hasattr(entity, 'handle_update'):
                            # For momentary entities, let the entity handle the update itself
                            # It will maintain its own virtual state
                            if hasattr(entity, '_is_momentary') and entity._is_momentary:
                                _LOGGER.debug(f"[{update_id}] Letting momentary entity manage its own state")
                                pass  # Entity will manage its own state via virtual state
                            else:
                                entity.handle_update(value)
                
                # Delay any status fetch to avoid a race condition where we might
                # catch the control in its "on" state before it reverts
                await asyncio.sleep(3.0)
                
                # Return success directly for momentary controls
                return result is not None
            
            # For non-momentary controls, verify the change
            verified = False
            max_retries = 3
            retry_count = 0
            
            while not verified and retry_count < max_retries:
                try:
                    # Wait a moment for the device to process the change
                    # Increasing wait time with each retry
                    await asyncio.sleep(0.5 + (retry_count * 0.5))
                    
                    # Get the updated status to verify the change
                    _LOGGER.debug(f"[{update_id}] Verifying DP update (attempt {retry_count+1}/{max_retries})")
                    status = await self._protocol.status()
                    
                    if status:
                        # Check if the status contains the DP directly, or in a dps dictionary
                        new_value = None
                        if dp_id_str in status:
                            new_value = status[dp_id_str]
                            _LOGGER.debug(f"[{update_id}] Found DP {dp_id_str} directly in status response: {new_value}")
                        elif "dps" in status and dp_id_str in status["dps"]:
                            new_value = status["dps"][dp_id_str]
                            _LOGGER.debug(f"[{update_id}] Found DP {dp_id_str} in dps dictionary: {new_value}")
                            
                        if new_value is not None:
                            _LOGGER.info(f"[{update_id}] Verified DP {dp_id} change: new value = {new_value}, requested = {value}")
                            
                            # Check if values match exactly or at least have the same type and similar values
                            # For example, 1 and True are considered equivalent in Tuya protocol
                            values_match = False
                            
                            # Direct match
                            if new_value == value:
                                values_match = True
                                _LOGGER.debug(f"[{update_id}] Value matched exactly: {value} ({type(value).__name__}) == {new_value} ({type(new_value).__name__})")
                            # Boolean equivalence - boolean True/False sent, device returned 1/0
                            elif isinstance(value, bool) and (new_value == 1 and value is True or new_value == 0 and value is False):
                                values_match = True
                                _LOGGER.debug(f"[{update_id}] Boolean-integer equivalence: sent {value} (bool), device returned {new_value} (likely int)")
                            # Integer/boolean equivalence in reverse - integer 1/0 sent, device returned True/False
                            elif (value == 1 and new_value is True) or (value == 0 and new_value is False):
                                values_match = True
                                _LOGGER.debug(f"[{update_id}] Integer-boolean equivalence: sent {value} (int), device returned {new_value} (bool)")
                                
                            if not values_match:
                                _LOGGER.warning(f"[{update_id}] Device reported different value after update: set {value} ({type(value)}), got {new_value} ({type(new_value)})")
                                retry_count += 1
                                # Use the device-reported value for now, we'll try again
                                actual_value = new_value
                            else:
                                verified = True
                                # When values match, use the device-reported value
                                actual_value = new_value
                        else:
                            _LOGGER.warning(f"[{update_id}] DP {dp_id} not found in status response: {status}")
                            retry_count += 1
                            actual_value = value  # Use requested value as fallback
                    else:
                        _LOGGER.warning(f"[{update_id}] Could not verify DP {dp_id} change - no status response")
                        retry_count += 1
                        actual_value = value  # Use requested value as fallback
                except Exception as verify_err:
                    _LOGGER.warning(f"[{update_id}] Failed to verify DP change: {verify_err}")
                    retry_count += 1
                    actual_value = value  # Use requested value as fallback
                    
            # Update entities with the actual value (verified or not)
            if dp_id_str in self._registered_entities:
                _LOGGER.debug(f"[{update_id}] Updating {len(self._registered_entities[dp_id_str])} registered entities with value: {actual_value}")
                for entity in self._registered_entities[dp_id_str]:
                    if hasattr(entity, 'handle_update'):
                        entity.handle_update(actual_value)
                        _LOGGER.debug(f"[{update_id}] Updated entity {entity.entity_id if hasattr(entity, 'entity_id') else entity}")
            
            # If verification failed after all retries, try to send the command again with a different approach
            if not verified and retry_count >= max_retries:
                _LOGGER.warning(f"[{update_id}] DP update verification failed after {max_retries} attempts, trying alternative method")
                try:
                    # Use set_dps instead of set_dp for a different command pathway
                    await self._protocol.set_dps({dp_id_str: value})
                    _LOGGER.info(f"[{update_id}] Sent alternative DP update command")
                    
                    # Wait for it to take effect
                    await asyncio.sleep(1.0)
                    
                    # Try one final verification
                    status = await self._protocol.status()
                    if status:
                        # Check if the status contains the DP directly, or in a dps dictionary
                        new_value = None
                        if dp_id_str in status:
                            new_value = status[dp_id_str]
                            _LOGGER.debug(f"[{update_id}] Found DP {dp_id_str} directly in status response: {new_value}")
                        elif "dps" in status and dp_id_str in status["dps"]:
                            new_value = status["dps"][dp_id_str]
                            _LOGGER.debug(f"[{update_id}] Found DP {dp_id_str} in dps dictionary: {new_value}")
                            
                        if new_value is not None:
                            # Check equivalence using same logic as above
                            values_match = False
                            if new_value == value:
                                values_match = True
                            elif isinstance(value, bool) and (new_value == 1 and value is True or new_value == 0 and value is False):
                                values_match = True
                            elif (value == 1 and new_value is True) or (value == 0 and new_value is False):
                                values_match = True
                                
                            if values_match:
                                _LOGGER.info(f"[{update_id}] Alternative method succeeded, DP {dp_id} now = {new_value}")
                                verified = True
                            else:
                                _LOGGER.warning(f"[{update_id}] Alternative method failed, final device value = {new_value} != {value}")
                                # Even if verification failed, consider it successful for momentary devices
                                # This prevents endless retries when the device intentionally reverts
                                _LOGGER.info(f"[{update_id}] Assuming command was processed despite different reported state")
                                verified = True
                                # Override the entity value to match what we tried to set
                                # The device might report a different state but we want the UI to match user intent
                                actual_value = value
                        else:
                            _LOGGER.warning(f"[{update_id}] DP {dp_id} not found in status response after alternative method")
                    else:
                        _LOGGER.warning(f"[{update_id}] Could not verify DP {dp_id} change after alternative method - no status response")
                except Exception as alt_err:
                    _LOGGER.warning(f"[{update_id}] Alternative update method failed: {alt_err}")
            
            # Return success if we either succeeded in verification or at least sent the command
            return verified or result is not None
            
        except Exception as e:
            _LOGGER.error(f"[{update_id}] Failed to set DP {dp_id}: {str(e)}")
            _LOGGER.debug(f"[{update_id}] Error details", exc_info=True)
            # Don't reconnect on every error, only if there's a connection issue
            if "connection" in str(e).lower() or "timeout" in str(e).lower():
                _LOGGER.info(f"[{update_id}] Detected connection issue, scheduling reconnect")
                self.hass.async_create_task(self._schedule_reconnect())
            return False

    async def heartbeat(self) -> bool:
        """Send heartbeat to device and update timestamp."""
        if not self._protocol:
            _LOGGER.warning("Cannot send heartbeat - no device connection")
            return False
            
        try:
            result = await self._protocol.heartbeat()
            # Update the heartbeat timestamp
            self.last_heartbeat = datetime.now().isoformat()
            _LOGGER.debug("Heartbeat result: %s, timestamp: %s", result, self.last_heartbeat)
            
            # Update the status sensor to reflect the new heartbeat time
            if DOMAIN in self.hass.data and self.entry.entry_id in self.hass.data[DOMAIN]:
                # Find and update all sensors for this device
                device_id = self.entry.data[CONF_DEVICE_ID]
                
                # Try to update all sensors that might exist for this device
                for entity_id in self.hass.states.async_entity_ids("sensor"):
                    if entity_id.startswith("sensor.lsc_tuya_") and device_id[-4:] in entity_id:
                        _LOGGER.debug("Requesting update for sensor %s", entity_id)
                        await self.hass.services.async_call(
                            "homeassistant", "update_entity", 
                            {"entity_id": entity_id}, blocking=False
                        )
            
            return True
        except Exception as e:
            _LOGGER.warning("Heartbeat failed: %s", str(e))
            _LOGGER.debug("Heartbeat exception details", exc_info=True)
            # Don't await here since we're in an async context
            self.hass.async_create_task(self._schedule_reconnect())
            return False