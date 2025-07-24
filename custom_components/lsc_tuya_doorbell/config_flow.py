import asyncio
import ipaddress
import json
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
    CONF_DPS_MAP,
    DEFAULT_DPS_MAP,
    CONF_PROTOCOL_VERSION,
    DEFAULT_PROTOCOL_VERSION,
    PROTOCOL_VERSIONS,
    CONF_FIRMWARE_VERSION,
    DEFAULT_FIRMWARE_VERSION,
    FIRMWARE_VERSIONS,
    V4_DPS_OPTIONS,
    V5_DPS_OPTIONS,
    DPS_MAPPINGS,
    RESULT_SUCCESS,
    RESULT_AUTH_FAILED,
    RESULT_NOT_FOUND,
    RESULT_CONNECTION_FAILED,
    RESULT_WAITING,
    RESULT_CONNECTING,
    CONF_BUTTON_DP,
    CONF_MOTION_DP,
    CONF_SHOW_ADVANCED
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
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the config flow."""
        self._discoveries = []
        self._devices_in_progress = {}
        self._discovered_devices = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return LscTuyaOptionsFlow(config_entry)

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
                        user_input.get(CONF_PROTOCOL_VERSION, DEFAULT_PROTOCOL_VERSION),
                    )

                    if validated == RESULT_AUTH_FAILED:
                        errors["base"] = "invalid_auth"
                    elif validated == RESULT_CONNECTION_FAILED:
                        errors["base"] = "cannot_connect"
                    elif validated == RESULT_SUCCESS:
                        # Connection successful, create entry
                        # We don't need MAC address anymore

                        # Create DPS map from button and motion selections
                        # Get default values from constants if not specified
                        default_mapping = DPS_MAPPINGS.get(
                            user_input.get(CONF_FIRMWARE_VERSION, DEFAULT_FIRMWARE_VERSION),
                            DEFAULT_DPS_MAP
                        )
                        button_dp = user_input.get(CONF_BUTTON_DP, default_mapping.get("button"))
                        motion_dp = user_input.get(CONF_MOTION_DP, default_mapping.get("motion"))

                        # Create the DPS map
                        user_input[CONF_DPS_MAP] = {
                            "button": button_dp,
                            "motion": motion_dp
                        }

                        # If advanced view is shown and custom DPS map is provided, use it
                        if user_input.get(CONF_SHOW_ADVANCED, False) and CONF_DPS_MAP in user_input and user_input[CONF_DPS_MAP]:
                            if isinstance(user_input[CONF_DPS_MAP], str):
                                try:
                                    # Use the already imported json module, don't import it again
                                    custom_dps_map = json.loads(user_input[CONF_DPS_MAP])
                                    # Only update if it's a valid dict
                                    if isinstance(custom_dps_map, dict):
                                        user_input[CONF_DPS_MAP] = custom_dps_map
                                except Exception as e:
                                    _LOGGER.warning(f"Invalid custom DPS map, using dropdown selections: {e}")

                        _LOGGER.info(f"Creating entry for device at {host} with DPS map {user_input[CONF_DPS_MAP]}")

                        # Clean up temporary fields not needed for storage
                        if CONF_BUTTON_DP in user_input:
                            del user_input[CONF_BUTTON_DP]
                        if CONF_MOTION_DP in user_input:
                            del user_input[CONF_MOTION_DP]
                        if CONF_SHOW_ADVANCED in user_input:
                            del user_input[CONF_SHOW_ADVANCED]

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

        # Default firmware version
        selected_firmware = user_input.get(CONF_FIRMWARE_VERSION, DEFAULT_FIRMWARE_VERSION) if user_input else DEFAULT_FIRMWARE_VERSION

        # Get DPS options based on firmware version
        dps_options = V5_DPS_OPTIONS if selected_firmware == "Version 5" else V4_DPS_OPTIONS

        # Build dropdown options
        button_dp_options = {opt["dp_id"]: opt["description"] for opt in dps_options["button"]}
        motion_dp_options = {opt["dp_id"]: opt["description"] for opt in dps_options["motion"]}

        # Get default DPS values for the firmware version
        default_mapping = DPS_MAPPINGS.get(selected_firmware, DEFAULT_DPS_MAP)
        # Use safe access to user_input since it could be None
        default_button_dp = default_mapping.get("button")
        default_motion_dp = default_mapping.get("motion")

        # If user_input exists, override defaults with user values
        if user_input:
            default_button_dp = user_input.get(CONF_BUTTON_DP, default_button_dp)
            default_motion_dp = user_input.get(CONF_MOTION_DP, default_motion_dp)

        # Get show advanced setting (safe access)
        show_advanced = user_input.get(CONF_SHOW_ADVANCED, False) if user_input else False

        # Create JSON string representation of current DPS map based on selections
        current_dps_map = {
            "button": default_button_dp,
            "motion": default_motion_dp
        }
        dps_map_json = json.dumps(current_dps_map)

        # Base schema
        schema_dict = {
            vol.Required(CONF_NAME, default=default_name): str,
            vol.Required(CONF_DEVICE_ID): str,
            vol.Required(CONF_LOCAL_KEY): str,
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_PORT, default=default_port): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
            vol.Required(CONF_PROTOCOL_VERSION, default=DEFAULT_PROTOCOL_VERSION): vol.In(
                PROTOCOL_VERSIONS
            ),
            vol.Required(CONF_FIRMWARE_VERSION, default=DEFAULT_FIRMWARE_VERSION): vol.In(
                FIRMWARE_VERSIONS
            ),
            vol.Required(CONF_BUTTON_DP, default=default_button_dp): vol.In(button_dp_options),
            vol.Required(CONF_MOTION_DP, default=default_motion_dp): vol.In(motion_dp_options),
            vol.Optional(CONF_SHOW_ADVANCED, default=show_advanced): bool,
        }

        # Add advanced field if show_advanced is enabled
        if show_advanced:
            schema_dict[vol.Optional(CONF_DPS_MAP, default=dps_map_json)] = str

        # Create schema
        schema = vol.Schema(schema_dict)

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

                    # Make sure the protocol version is in the config
                    if CONF_PROTOCOL_VERSION not in config:
                        config[CONF_PROTOCOL_VERSION] = DEFAULT_PROTOCOL_VERSION

                    # If we found a device with a different protocol version during discovery, use that
                    selected_device = next((d for d in self._discovered_devices if d["ip"] == user_input["device_ip"]), None)
                    if selected_device and "protocol_version" in selected_device:
                        config[CONF_PROTOCOL_VERSION] = selected_device["protocol_version"]
                        _LOGGER.info(f"Using discovered protocol version: {selected_device['protocol_version']}")

                    # Set button_dp and motion_dp based on firmware version
                    firmware_version = config.get(CONF_FIRMWARE_VERSION, DEFAULT_FIRMWARE_VERSION)
                    default_mapping = DPS_MAPPINGS.get(firmware_version, DEFAULT_DPS_MAP)

                    # If DPS_MAP is already in config, extract button and motion values
                    if CONF_DPS_MAP in config and isinstance(config[CONF_DPS_MAP], dict):
                        button_dp = config[CONF_DPS_MAP].get("button", default_mapping.get("button"))
                        motion_dp = config[CONF_DPS_MAP].get("motion", default_mapping.get("motion"))
                    else:
                        button_dp = default_mapping.get("button")
                        motion_dp = default_mapping.get("motion")

                    # Create DPS map from button and motion selections
                    config[CONF_DPS_MAP] = {
                        "button": button_dp,
                        "motion": motion_dp
                    }

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
                # Try with configured protocol version first
                protocol_version = self._devices_in_progress.get(CONF_PROTOCOL_VERSION, DEFAULT_PROTOCOL_VERSION)
                result = await self._validate_device_connection(ip, port, device_id, local_key, protocol_version)

                if result == RESULT_SUCCESS:
                    # Successfully connected and validated with device ID and key
                    _LOGGER.info(f"Device at {ip} validated successfully with PyTuya using protocol version {protocol_version}")
                    return {"ip": ip, "valid": True, "protocol_version": protocol_version}

                # If first attempt fails, try other protocol versions
                for version in [v for v in PROTOCOL_VERSIONS if v != protocol_version]:
                    _LOGGER.debug(f"Trying alternative protocol version {version} for device at {ip}")
                    result = await self._validate_device_connection(ip, port, device_id, local_key, version)

                    if result == RESULT_SUCCESS:
                        _LOGGER.info(f"Device at {ip} validated successfully with PyTuya using alternative protocol version {version}")
                        # Update protocol version in the device configuration
                        self._devices_in_progress[CONF_PROTOCOL_VERSION] = version
                        return {"ip": ip, "valid": True, "protocol_version": version}
                else:
                    _LOGGER.debug(f"Device at {ip} failed validation: {result}")
            except Exception as e:
                _LOGGER.exception(f"Error validating device at {ip}: {str(e)}")

            return None

        except Exception as e:
            _LOGGER.exception(f"Error checking device at {ip}: {str(e)}")
            return None

    async def _validate_device_connection(self, host: str, port: int, device_id: str, local_key: str, protocol_version: str = DEFAULT_PROTOCOL_VERSION) -> str:
        """Validate connection to a Tuya device."""
        protocol = None
        try:
            from .pytuya import connect

            _LOGGER.debug(f"Validating connection to {host}:{port}")
            _LOGGER.debug(f"Using device ID: {device_id[:5]}...{device_id[-5:]}, local key: {local_key[:3]}..., and protocol version: {protocol_version}")

            # Try connecting with a short timeout
            try:
                protocol = await connect(
                    host,
                    device_id,
                    local_key,
                    protocol_version,  # Use specified protocol version
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


class LscTuyaOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for LSC Tuya Doorbell integration."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.options = dict(config_entry.options)
        self.device_config = dict(config_entry.data)
        # Store entry_id instead of the full config_entry to avoid deprecation warning
        self.entry_id = config_entry.entry_id

    async def async_step_init(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Check if user is just toggling the "Show Advanced Options" checkbox
            if (CONF_SHOW_ADVANCED in user_input and
                user_input.get(CONF_SHOW_ADVANCED) != self.device_config.get(CONF_SHOW_ADVANCED, False)):

                # Update the show_advanced flag in our temporary config
                temp_config = {**self.device_config}
                temp_config[CONF_SHOW_ADVANCED] = user_input[CONF_SHOW_ADVANCED]
                self.device_config = temp_config

                _LOGGER.debug(f"User toggled show_advanced to {user_input[CONF_SHOW_ADVANCED]}, reloading form")

                # Return the same form with updated show_advanced state
                # Note: we need to rebuild the form now that show_advanced has changed
                return await self.async_step_init()

            # Check if user changed the firmware version - if so, reload the form with the
            # appropriate DP options for that firmware version
            if (CONF_FIRMWARE_VERSION in user_input and
                user_input.get(CONF_FIRMWARE_VERSION) != self.device_config.get(CONF_FIRMWARE_VERSION, DEFAULT_FIRMWARE_VERSION)):

                # Update the firmware version in our temporary config
                temp_config = {**self.device_config}
                temp_config[CONF_FIRMWARE_VERSION] = user_input[CONF_FIRMWARE_VERSION]
                self.device_config = temp_config

                _LOGGER.debug(f"User changed firmware version to {user_input[CONF_FIRMWARE_VERSION]}, reloading form with updated options")

                # Return the same form with updated firmware version and corresponding DP options
                return await self.async_step_init()

            try:
                # Update device configuration
                updated_config = {**self.device_config}

                # Update values from user input
                if CONF_LOCAL_KEY in user_input:
                    updated_config[CONF_LOCAL_KEY] = user_input[CONF_LOCAL_KEY]
                if CONF_HOST in user_input:
                    updated_config[CONF_HOST] = user_input[CONF_HOST]
                if CONF_PORT in user_input:
                    updated_config[CONF_PORT] = user_input[CONF_PORT]
                if CONF_PROTOCOL_VERSION in user_input:
                    updated_config[CONF_PROTOCOL_VERSION] = user_input[CONF_PROTOCOL_VERSION]
                if CONF_FIRMWARE_VERSION in user_input:
                    updated_config[CONF_FIRMWARE_VERSION] = user_input[CONF_FIRMWARE_VERSION]
                # Handle button and motion DP selections
                firmware_version = user_input.get(CONF_FIRMWARE_VERSION, self.device_config.get(CONF_FIRMWARE_VERSION, DEFAULT_FIRMWARE_VERSION))

                # Check if we're in advanced mode
                show_advanced = user_input.get(CONF_SHOW_ADVANCED, False)

                # Get firmware-specific defaults
                firmware_defaults = DPS_MAPPINGS.get(firmware_version, {})

                # Create DPS map - start with firmware defaults
                dps_map = {
                    "button": firmware_defaults.get("button", "185"),
                    "motion": firmware_defaults.get("motion", "115")
                }

                if show_advanced:
                    # In advanced mode, use the custom DPS map
                    _LOGGER.debug("Using advanced mode for DPS settings")
                    # We'll handle the JSON DPS map later in the code
                else:
                    # In simple mode, use the dropdown selections
                    # Use safe defaults based on firmware version
                    firmware_defaults = DPS_MAPPINGS.get(firmware_version, DEFAULT_DPS_MAP)
                    button_dp = user_input.get(CONF_BUTTON_DP, firmware_defaults.get("button"))
                    motion_dp = user_input.get(CONF_MOTION_DP, firmware_defaults.get("motion"))

                    # Get the available options for the selected firmware version to validate
                    dps_options = V5_DPS_OPTIONS if firmware_version == "Version 5" else V4_DPS_OPTIONS
                    valid_button_dps = [opt["dp_id"] for opt in dps_options["button"]]
                    valid_motion_dps = [opt["dp_id"] for opt in dps_options["motion"]]

                    # Validate selections against firmware-specific options
                    if button_dp and button_dp not in valid_button_dps:
                        _LOGGER.warning(f"Selected button DP {button_dp} is not valid for {firmware_version}")
                        errors[CONF_BUTTON_DP] = "invalid_dp_for_firmware"

                    if motion_dp and motion_dp not in valid_motion_dps:
                        _LOGGER.warning(f"Selected motion DP {motion_dp} is not valid for {firmware_version}")
                        errors[CONF_MOTION_DP] = "invalid_dp_for_firmware"

                    # If we have valid selections, update the DPS map
                    if button_dp and not errors.get(CONF_BUTTON_DP):
                        dps_map["button"] = button_dp
                    if motion_dp and not errors.get(CONF_MOTION_DP):
                        dps_map["motion"] = motion_dp

                # If advanced view is shown and custom DPS map is provided, use it
                if user_input and user_input.get(CONF_SHOW_ADVANCED, False) and CONF_DPS_MAP in user_input:
                    # Make sure we have a valid DPS_MAP value
                    if isinstance(user_input[CONF_DPS_MAP], str) and user_input[CONF_DPS_MAP].strip():
                        try:
                            custom_dps_map = json.loads(user_input[CONF_DPS_MAP])
                            # Only update if it's a valid dict
                            if isinstance(custom_dps_map, dict):
                                dps_map = custom_dps_map
                        except Exception as e:
                            _LOGGER.error(f"Error parsing DPS map: {e}")
                            errors[CONF_DPS_MAP] = "invalid_dps_map"

                # Update the config with the final DPS map
                updated_config[CONF_DPS_MAP] = dps_map

                # Clean up temporary fields not needed for long-term storage
                if CONF_BUTTON_DP in updated_config:
                    del updated_config[CONF_BUTTON_DP]
                if CONF_MOTION_DP in updated_config:
                    del updated_config[CONF_MOTION_DP]

                # Keep CONF_SHOW_ADVANCED to preserve form state between sessions
                if CONF_SHOW_ADVANCED in user_input:
                    updated_config[CONF_SHOW_ADVANCED] = user_input[CONF_SHOW_ADVANCED]
                    _LOGGER.debug(f"Saved show_advanced = {user_input[CONF_SHOW_ADVANCED]} to config")

                # Validate connection with new settings if host and key are provided
                if not errors and CONF_HOST in updated_config and CONF_LOCAL_KEY in updated_config:
                    # Create a validation instance
                    validator = LscTuyaConfigFlow()
                    result = await validator._validate_device_connection(
                        updated_config[CONF_HOST],
                        updated_config.get(CONF_PORT, DEFAULT_PORT),
                        updated_config[CONF_DEVICE_ID],
                        updated_config[CONF_LOCAL_KEY],
                        updated_config.get(CONF_PROTOCOL_VERSION, DEFAULT_PROTOCOL_VERSION)
                    )

                    if result == RESULT_AUTH_FAILED:
                        errors[CONF_LOCAL_KEY] = "invalid_auth"
                    elif result == RESULT_CONNECTION_FAILED:
                        errors[CONF_HOST] = "cannot_connect"

                # Save changes if no errors
                if not errors:
                    _LOGGER.info(f"Updating configuration for {updated_config.get(CONF_NAME)}")

                    # Get the config entry by entry_id and update it
                    config_entry = self.hass.config_entries.async_get_entry(self.entry_id)
                    if config_entry:
                        self.hass.config_entries.async_update_entry(
                            config_entry,
                            data=updated_config
                        )

                    # Reload the integration to apply changes
                    return self.async_create_entry(title="", data={})

            except Exception as e:
                _LOGGER.exception(f"Unexpected error during reconfiguration: {e}")
                errors["base"] = "unknown"

        # Get current firmware version
        firmware_version = self.device_config.get(CONF_FIRMWARE_VERSION, DEFAULT_FIRMWARE_VERSION)
        _LOGGER.debug(f"Building form with firmware version: {firmware_version}")

        # Get DPS options based on firmware version
        dps_options = V5_DPS_OPTIONS if firmware_version == "Version 5" else V4_DPS_OPTIONS

        # Build dropdown options
        button_dp_options = {opt["dp_id"]: opt["description"] for opt in dps_options["button"]}
        motion_dp_options = {opt["dp_id"]: opt["description"] for opt in dps_options["motion"]}

        # Log available options
        _LOGGER.debug(f"Available button options for {firmware_version}: {button_dp_options}")
        _LOGGER.debug(f"Available motion options for {firmware_version}: {motion_dp_options}")

        # Get current DPS map
        current_dps_map = self.device_config.get(CONF_DPS_MAP, DEFAULT_DPS_MAP)

        # Get default DPs for this firmware version
        firmware_defaults = DPS_MAPPINGS.get(firmware_version, {})
        default_button_dp = firmware_defaults.get("button", "185")
        default_motion_dp = firmware_defaults.get("motion", "115")

        # Extract button and motion DPs, falling back to firmware-specific defaults
        current_button_dp = current_dps_map.get("button", default_button_dp)
        current_motion_dp = current_dps_map.get("motion", default_motion_dp)

        # Validate that the current selections are in the available options for this firmware
        # If not, use the first available option
        if current_button_dp not in button_dp_options:
            _LOGGER.debug(f"Current button DP {current_button_dp} not valid for {firmware_version}, using default")
            current_button_dp = next(iter(button_dp_options.keys()), default_button_dp)

        if current_motion_dp not in motion_dp_options:
            _LOGGER.debug(f"Current motion DP {current_motion_dp} not valid for {firmware_version}, using default")
            current_motion_dp = next(iter(motion_dp_options.keys()), default_motion_dp)

        # Create JSON string representation
        dps_map_json = json.dumps(current_dps_map)

        # Get show advanced setting (preserve state between form submissions)
        # First check if it's in the current user input
        if user_input and CONF_SHOW_ADVANCED in user_input:
            show_advanced = user_input[CONF_SHOW_ADVANCED]
        # Otherwise check if it was previously set in the config
        elif self.device_config.get(CONF_SHOW_ADVANCED) is not None:
            show_advanced = self.device_config.get(CONF_SHOW_ADVANCED)
        # Default to False if not set anywhere
        else:
            show_advanced = False

        _LOGGER.debug(f"Show advanced options: {show_advanced}")

        # Create base schema dict
        schema_dict = {
            vol.Optional(
                CONF_LOCAL_KEY,
                default=self.device_config.get(CONF_LOCAL_KEY, "")
            ): str,
            vol.Optional(
                CONF_HOST,
                default=self.device_config.get(CONF_HOST, "")
            ): str,
            vol.Optional(
                CONF_PORT,
                default=self.device_config.get(CONF_PORT, DEFAULT_PORT)
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Optional(
                CONF_PROTOCOL_VERSION,
                default=self.device_config.get(CONF_PROTOCOL_VERSION, DEFAULT_PROTOCOL_VERSION)
            ): vol.In(PROTOCOL_VERSIONS),
            vol.Optional(
                CONF_FIRMWARE_VERSION,
                default=self.device_config.get(CONF_FIRMWARE_VERSION, DEFAULT_FIRMWARE_VERSION)
            ): vol.In(FIRMWARE_VERSIONS),
            vol.Optional(CONF_SHOW_ADVANCED, default=show_advanced): bool,
        }

        # Add either simple dropdowns or advanced field based on show_advanced setting
        if show_advanced:
            _LOGGER.debug("Adding advanced fields to form")
            schema_dict[vol.Optional(
                CONF_DPS_MAP,
                default=dps_map_json
            )] = str
        else:
            # Only add the simple dropdown options if advanced mode is not enabled
            schema_dict[vol.Optional(
                CONF_BUTTON_DP,
                default=current_button_dp
            )] = vol.In(button_dp_options)

            schema_dict[vol.Optional(
                CONF_MOTION_DP,
                default=current_motion_dp
            )] = vol.In(motion_dp_options)

        # Create schema
        schema = vol.Schema(schema_dict)

        # Show the form
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "name": self.device_config.get(CONF_NAME, "LSC Doorbell"),
                "device_id": self.device_config.get(CONF_DEVICE_ID, "")
            }
        )
