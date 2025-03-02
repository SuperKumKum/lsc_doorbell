import asyncio
import ipaddress
import logging
from typing import Dict, Any, List, Optional, Tuple
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_DEVICE_ID,
    CONF_LOCAL_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SUBNET,
    DEFAULT_PORT,
    CONF_MAC,
    CONF_LAST_IP,
    RESULT_SUCCESS,
    RESULT_AUTH_FAILED,
    RESULT_NOT_FOUND,
    RESULT_CONNECTION_FAILED,
    RESULT_WAITING,
    RESULT_CONNECTING
)

_LOGGER = logging.getLogger(__name__)

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

class DeviceNotFound(HomeAssistantError):
    """Error to indicate no device was found."""

class LscTuyaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LSC Tuya Doorbell."""
    
    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._discoveries = []
        self._devices_in_progress = {}
        self._discovered_devices = []

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            try:
                # Check if we have a direct IP or a subnet
                host = user_input.get(CONF_HOST, "")
                
                if not host:
                    errors[CONF_HOST] = "host_required"
                elif "/" in host:  # This is a subnet
                    # Validate subnet format
                    try:
                        subnet = ipaddress.ip_network(host, strict=False)
                        if subnet.prefixlen < 24:
                            errors[CONF_HOST] = "subnet_too_large"
                        else:
                            # Valid subnet, proceed to discovery
                            self._devices_in_progress = user_input
                            return await self.async_step_discover()
                    except ValueError:
                        errors[CONF_HOST] = "invalid_subnet"
                else:
                    # Direct IP, validate connection
                    _LOGGER.debug(f"Validating direct IP connection to {host}")
                    validated = await self._validate_device_connection(
                        host,
                        user_input[CONF_PORT],
                        user_input[CONF_DEVICE_ID],
                        user_input[CONF_LOCAL_KEY],
                    )
                    
                    if validated == RESULT_AUTH_FAILED:
                        errors["base"] = "invalid_auth"
                    elif validated == RESULT_CONNECTION_FAILED:
                        errors["base"] = "cannot_connect"
                    elif validated == RESULT_SUCCESS:
                        # Connection successful, create entry
                        # We don't need MAC address anymore
                                
                        # Add default DPS map if not provided
                        if CONF_DPS_MAP not in user_input:
                            user_input[CONF_DPS_MAP] = DEFAULT_DPS_MAP
                            
                        _LOGGER.info(f"Creating entry for device at {host}")
                        return self.async_create_entry(
                            title=user_input[CONF_NAME],
                            data=user_input
                        )
            except Exception as e:
                _LOGGER.exception(f"Unexpected exception in user step: {str(e)}")
                errors["base"] = "unknown"

        # Show the form
        default_name = "LSC Doorbell"
        default_port = DEFAULT_PORT
        
        # If we have data from a previous attempt, use it
        if user_input:
            default_name = user_input.get(CONF_NAME, default_name)
            default_port = user_input.get(CONF_PORT, default_port)
            
        # Create a schema with defaults
        schema = vol.Schema({
            vol.Required(CONF_NAME, default=default_name): str,
            vol.Required(CONF_DEVICE_ID): str,
            vol.Required(CONF_LOCAL_KEY): str,
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_PORT, default=default_port): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
        })
        
        _LOGGER.debug("Showing user form with schema keys: %s", list(schema.schema.keys()))
        
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors
        )
        
    async def async_step_discover(self, user_input=None) -> FlowResult:
        """Handle the discovery step."""
        errors = {}
        
        if user_input is not None:
            if user_input.get("device_ip"):
                # User selected a device, create the config entry
                try:
                    config = {**self._devices_in_progress}
                    config[CONF_HOST] = user_input["device_ip"]
                    
                    # We don't need MAC address anymore, removed MAC lookup
                            
                    # Add default DPS map if not provided
                    if CONF_DPS_MAP not in config:
                        config[CONF_DPS_MAP] = DEFAULT_DPS_MAP
                    
                    _LOGGER.info(f"Creating entry for device at {config[CONF_HOST]}")
                    
                    return self.async_create_entry(
                        title=config[CONF_NAME],
                        data=config
                    )
                except Exception as e:
                    _LOGGER.exception(f"Error creating config entry: {str(e)}")
                    errors["base"] = "unknown"
            elif user_input.get("action") == "manual":
                # User wants to go back and enter IP manually
                return await self.async_step_user(self._devices_in_progress)
            elif user_input.get("action") == "rescan":
                # User wants to rescan
                self._discovered_devices = []
                # Will trigger a new scan below
        
        # Start discovery if we don't have results yet
        if not self._discovered_devices:
            subnet = self._devices_in_progress[CONF_HOST]
            device_id = self._devices_in_progress[CONF_DEVICE_ID]
            local_key = self._devices_in_progress[CONF_LOCAL_KEY]
            port = self._devices_in_progress[CONF_PORT]
            
            _LOGGER.info(f"Starting discovery in subnet {subnet} for device with ID {device_id}")
            discovered = await self._discover_devices(subnet, port, device_id, local_key)
            self._discovered_devices = discovered
            _LOGGER.info(f"Discovery complete, found {len(discovered)} devices")
            
        if not self._discovered_devices:
            # No devices found
            _LOGGER.warning("No devices found in subnet scan")
            errors["base"] = "no_devices_found"
            
            return self.async_show_form(
                step_id="discover",
                data_schema=vol.Schema({
                    vol.Required("action", default="rescan"): vol.In({
                        "rescan": "Scan again",
                        "manual": "Enter IP manually"
                    }),
                }),
                errors=errors,
                description_placeholders={
                    "subnet": self._devices_in_progress[CONF_HOST]
                }
            )
        
        # Create schema with discovered devices
        devices = {
            device["ip"]: f"{device['ip']}"
            for device in self._discovered_devices
        }
        
        _LOGGER.debug(f"Showing selection form with {len(devices)} devices")
        
        return self.async_show_form(
            step_id="discover",
            data_schema=vol.Schema({
                vol.Required("device_ip"): vol.In(devices),
                vol.Optional("action"): vol.In({
                    "rescan": "Scan again",
                    "manual": "Enter IP manually"
                }),
            }),
            errors=errors,
            description_placeholders={
                "subnet": self._devices_in_progress[CONF_HOST],
                "device_count": str(len(self._discovered_devices))
            }
        )

    async def async_step_import(self, import_config) -> FlowResult:
        """Handle import from YAML."""
        return await self.async_step_user(import_config)
        
    async def _discover_devices(self, subnet: str, port: int, device_id: str, local_key: str) -> List[Dict[str, Any]]:
        """Discover devices in the subnet."""
        _LOGGER.info(f"Starting discovery in subnet {subnet} with port {port}")
        
        try:
            network = ipaddress.ip_network(subnet, strict=False)
            hosts = list(network.hosts())
            
            _LOGGER.info(f"Network {subnet} contains {len(hosts)} host addresses to scan")
            
            # Split into chunks to process in parallel (max 25 concurrent)
            chunk_size = 25
            host_chunks = [hosts[i:i + chunk_size] for i in range(0, len(hosts), chunk_size)]
            
            discovered_devices = []
            total_scanned = 0
            
            for chunk_idx, chunk in enumerate(host_chunks):
                _LOGGER.debug(f"Processing chunk {chunk_idx+1}/{len(host_chunks)} ({len(chunk)} hosts)")
                
                # Check each IP in the chunk concurrently
                tasks = [self._check_device(str(ip), port, device_id, local_key) for ip in chunk]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, Exception):
                        _LOGGER.debug(f"Got exception during check: {str(result)}")
                        continue
                    if result:
                        _LOGGER.info(f"Found device: {result}")
                        discovered_devices.append(result)
                
                total_scanned += len(chunk)
                _LOGGER.debug(f"Scanned {total_scanned}/{len(hosts)} hosts, found {len(discovered_devices)} devices so far")
            
            _LOGGER.info(f"Discovery complete. Found {len(discovered_devices)} devices")
            return discovered_devices
            
        except Exception as e:
            _LOGGER.exception(f"Error during discovery: {str(e)}")
            return []
    
    async def _check_device(self, ip: str, port: int, device_id: str, local_key: str) -> Optional[Dict[str, Any]]:
        """Check if a device is a valid Tuya device."""
        try:
            # First check if port is open
            _LOGGER.debug(f"Checking if port {port} is open on {ip}")
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, port),
                    timeout=1.0
                )
                writer.close()
                await writer.wait_closed()
                _LOGGER.debug(f"Port {port} is open on {ip}")
            except (asyncio.TimeoutError, ConnectionRefusedError, OSError) as e:
                _LOGGER.debug(f"Port {port} is not open on {ip}: {str(e)}")
                return None
                
            # Port is open, try to connect with PyTuya
            _LOGGER.debug(f"Attempting to validate device at {ip} with PyTuya")
            try:
                result = await self._validate_device_connection(ip, port, device_id, local_key)
                
                if result == RESULT_SUCCESS:
                    # Successfully connected and validated with device ID and key
                    _LOGGER.info(f"Device at {ip} validated successfully with PyTuya")
                    return {"ip": ip, "valid": True}
                else:
                    _LOGGER.debug(f"Device at {ip} failed validation: {result}")
            except Exception as e:
                _LOGGER.exception(f"Error validating device at {ip}: {str(e)}")
            
            return None
            
        except Exception as e:
            _LOGGER.exception(f"Error checking device at {ip}: {str(e)}")
            return None
    
    async def _validate_device_connection(self, host: str, port: int, device_id: str, local_key: str) -> str:
        """Validate connection to a Tuya device."""
        protocol = None
        try:
            from .pytuya import connect
            
            _LOGGER.debug(f"Validating connection to {host}:{port}")
            _LOGGER.debug(f"Using device ID: {device_id[:5]}...{device_id[-5:]} and local key: {local_key[:3]}...")
            
            # Try connecting with a short timeout
            try:
                protocol = await connect(
                    host,
                    device_id,
                    local_key,
                    "3.3",  # Version
                    True,   # Debug to see more details
                    None,   # No listener needed for validation
                    port=port,
                    timeout=5
                )
                
                _LOGGER.debug(f"Connected to {host}:{port}, attempting to get status")
                
                # If connection succeeded, try to get status
                try:
                    status = await protocol.status()
                    _LOGGER.info(f"Received status from {host}: {status}")
                    
                    # Close connection
                    if protocol:
                        await protocol.close()
                        protocol = None
                    
                    return RESULT_SUCCESS
                except Exception as e:
                    _LOGGER.debug(f"Status request to {host} failed: {str(e)}")
                    
                    # Close connection
                    if protocol:
                        await protocol.close()
                        protocol = None
                    
                    if "Invalid key" in str(e) or "Checksum failed" in str(e):
                        _LOGGER.debug(f"Authentication failed for {host}")
                        return RESULT_AUTH_FAILED
                    _LOGGER.debug(f"Connection failed for {host}: {str(e)}")
                    return RESULT_CONNECTION_FAILED
            except Exception as e:
                _LOGGER.error(f"Connection to {host} failed: {str(e)}")
                return RESULT_CONNECTION_FAILED
                
        except Exception as e:
            _LOGGER.exception(f"Connection validation error for {host}: {str(e)}")
            return RESULT_CONNECTION_FAILED
        finally:
            # Always make sure we close the protocol if it exists
            if protocol:
                try:
                    await protocol.close()
                except Exception as e:
                    _LOGGER.debug(f"Error closing protocol: {str(e)}")
                protocol = None
    
    async def _get_device_mac(self, ip: str) -> Optional[str]:
        """Get MAC address for a device."""
        try:
            _LOGGER.debug(f"Trying to get MAC address for {ip} using ARP")
            
            # Try the arp command first
            try:
                proc = await asyncio.create_subprocess_exec(
                    'arp', '-n', ip,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                output = stdout.decode()
                
                _LOGGER.debug(f"ARP output for {ip}: {output}")
                
                # Parse ARP output
                lines = output.split('\n')
                for line in lines:
                    if ip in line and "ether" in line:
                        _LOGGER.debug(f"Found ARP line for {ip}: {line}")
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part == "ether" and i+1 < len(parts):
                                mac = parts[i+1]
                                _LOGGER.debug(f"Extracted MAC for {ip}: {mac}")
                                return mac
            except Exception as e:
                _LOGGER.debug(f"ARP command failed for {ip}: {str(e)}")
            
            # Try reading from /proc/net/arp as a fallback
            try:
                _LOGGER.debug(f"Trying to get MAC from /proc/net/arp for {ip}")
                proc = await asyncio.create_subprocess_exec(
                    'cat', '/proc/net/arp',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                arp_file = stdout.decode()
                
                for line in arp_file.split('\n'):
                    if ip in line:
                        _LOGGER.debug(f"Found /proc/net/arp line for {ip}: {line}")
                        parts = line.split()
                        if len(parts) >= 4:
                            mac = parts[3]
                            if ':' in mac:  # Verify it looks like a MAC
                                _LOGGER.debug(f"Extracted MAC for {ip} from /proc/net/arp: {mac}")
                                return mac
            except Exception as e:
                _LOGGER.debug(f"Reading /proc/net/arp failed for {ip}: {str(e)}")
                
            _LOGGER.warning(f"Could not determine MAC address for {ip}")
            return None
        except Exception as e:
            _LOGGER.exception(f"Error in MAC address lookup for {ip}: {str(e)}")
            return None
