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
    
    for interface in interfaces:
        addrs = netifaces.ifaddresses(interface).get(netifaces.AF_INET, [])
        for addr in addrs:
            if 'addr' not in addr or 'netmask' not in addr:
                continue
                
            network = IPv4Network(f"{addr['addr']}/{addr['netmask']}", strict=False)
            _LOGGER.debug("Scanning interface %s network %s", interface, network)
            
            tasks = [async_check_device(str(ip), port, timeout) for ip in network.hosts()]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if result and isinstance(result, tuple):
                    devices.append(result)
    
    return devices

async def async_check_device(ip: str, port: int, timeout: float) -> Tuple[str, str]:
    """Check if a device is listening on the Tuya port and return (IP, MAC)."""
    try:
        # Try to get MAC from ARP first
        mac = await async_get_arp_mac(ip)
        if mac:
            return (ip, mac)
            
        # Fallback to port check
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        
        mac = await async_get_arp_mac(ip)
        return (ip, mac) if mac else None
        
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
        return None

async def async_get_arp_mac(ip: str) -> str:
    """Get MAC address from ARP cache."""
    try:
        proc = await asyncio.create_subprocess_exec(
            'arp', '-n', ip,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        lines = stdout.decode().split('\n')
        if len(lines) >= 2 and 'HWaddress' in lines[1]:
            return lines[1].split()[2]
    except Exception as e:
        _LOGGER.debug("ARP lookup failed: %s", str(e))
    
    return None
