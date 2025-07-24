import asyncio
import logging
import netifaces
from typing import List, Tuple
from ipaddress import IPv4Network
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

async def async_scan_network(port: int = 6668, timeout: float = 1.0) -> List[Tuple[str, str]]:
    """Scan the local network for Tuya devices."""
    devices = []
interfaces = netifaces.interfaces()

    _LOGGER.info("Starting network scan for devices on port %s", port)
_LOGGER.debug("Found network interfaces: %s", interfaces)

    for interface in interfaces:
        addrs = netifaces.ifaddresses(interface).get(netifaces.AF_INET, [])
        _LOGGER.debug("Interface %s has %d IPv4 addresses", interface, len(addrs))

        for addr in addrs:
            if 'addr' not in addr or 'netmask' not in addr:
                _LOGGER.debug("Skipping interface %s: missing addr or netmask", interface)
                continue

            try:
                network = IPv4Network(f"{addr['addr']}/{addr['netmask']}", strict=False)
                _LOGGER.info("Scanning interface %s network %s (%d hosts)",
                             interface, network, network.num_addresses - 2)

                # Split into chunks to process in parallel (max 25 concurrent)
                hosts = list(network.hosts())
                chunk_size = 25
                host_chunks = [hosts[i:i + chunk_size] for i in range(0, len(hosts), chunk_size)]

                for chunk_idx, chunk in enumerate(host_chunks):
                    _LOGGER.debug("Processing chunk %d/%d on interface %s",
                                 chunk_idx+1, len(host_chunks), interface)
                    tasks = [async_check_device(str(ip), port, timeout) for ip in chunk]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    for result in results:
                        if isinstance(result, Exception):
                            continue
                        if result and isinstance(result, tuple):
                            ip, mac = result
                            _LOGGER.info("Found device at %s with MAC %s", ip, mac)
                            devices.append(result)
            except Exception as e:
                _LOGGER.exception("Error scanning network %s on interface %s: %s",
                                 addr.get('addr'), interface, str(e))

    _LOGGER.info("Network scan complete. Found %d devices with port %s open", len(devices), port)
    return devices

async def async_check_device(ip: str, port: int, timeout: float) -> Tuple[str, str]:
    """Check if a device is listening on the Tuya port and return (IP, '')."""
    try:
        _LOGGER.debug("Checking if %s has port %s open", ip, port)

        # Check if port is open
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=timeout
            )
            writer.close()
            await writer.wait_closed()
            _LOGGER.debug("Device at %s has port %s open", ip, port)

            # If we get here, port is open, return the IP
            return (ip, "")

        except (asyncio.TimeoutError, ConnectionRefusedError, OSError) as e:
            _LOGGER.debug("Device at %s does not have port %s open: %s", ip, port, str(e))
            return None

    except Exception as e:
        _LOGGER.debug("Error checking device at %s: %s", ip, str(e))
        return None

async def async_get_arp_mac(ip: str) -> str:
    """Get MAC address from ARP cache."""
    try:
        _LOGGER.debug("Looking up MAC address for %s", ip)

        # Try 'arp -n' format
        try:
            proc = await asyncio.create_subprocess_exec(
                'arp', '-n', ip,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            output = stdout.decode()
            _LOGGER.debug("ARP output for %s: %s", ip, output)

            # Parse different output formats
            lines = output.split('\n')
            for line in lines:
                if ip in line:
                    _LOGGER.debug("Found ARP line for %s: %s", ip, line)

                    # Format: Address HWtype HWaddress Flags Mask Iface
                    if 'HWaddress' in line:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part == 'HWaddress' and i+1 < len(parts):
                                mac = parts[i+1]
                                _LOGGER.debug("Found MAC via HWaddress: %s", mac)
                                return mac

                    # Format with ether: IP-address ether MAC-address ....
                    if 'ether' in line:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part == 'ether' and i+1 < len(parts):
                                mac = parts[i+1]
                                _LOGGER.debug("Found MAC via ether: %s", mac)
                                return mac

                    # Try to find a MAC-like pattern (6 pairs of hex digits separated by :)
                    parts = line.split()
                    for part in parts:
                        if ':' in part and len(part.split(':')) == 6:
                            _LOGGER.debug("Found MAC-like pattern: %s", part)
                            return part
        except Exception as e:
            _LOGGER.debug("ARP command failed: %s", str(e))

        # Try reading /proc/net/arp directly as fallback
        try:
            proc = await asyncio.create_subprocess_exec(
                'cat', '/proc/net/arp',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            arp_file = stdout.decode()
            _LOGGER.debug("/proc/net/arp contents related to %s: %s",
                         ip, [l for l in arp_file.split('\n') if ip in l])

            for line in arp_file.split('\n'):
                if ip in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        mac = parts[3]
                        if ':' in mac and len(mac.split(':')) == 6:
                            _LOGGER.debug("Found MAC in /proc/net/arp: %s", mac)
                            return mac
        except Exception as e:
            _LOGGER.debug("Reading /proc/net/arp failed: %s", str(e))

        _LOGGER.debug("Could not find MAC address for %s", ip)
        return None
    except Exception as e:
        _LOGGER.exception("Error in MAC address lookup: %s", str(e))
        return None
