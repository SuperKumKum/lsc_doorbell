#!/usr/bin/env python3
"""
Scan network for Tuya devices.
This will help identify Tuya devices on your network and determine their device IDs and protocol versions.

Usage:
  python3 scan_for_tuya_devices.py
"""

import argparse
import json
import logging
import sys
import tinytuya

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Scan for Tuya devices on the network."""
    args = parse_arguments()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        tinytuya.set_debug(True)
    
    logger.info("Scanning for Tuya devices on the network...")
    
    # Scan for devices
    devices = tinytuya.discover(timeout=args.timeout)
    
    if not devices:
        logger.error("No Tuya devices found on the network.")
        return
    
    logger.info(f"Found {len(devices)} Tuya devices!")
    
    # Print device information
    for i, device in enumerate(devices):
        try:
            logger.info(f"\nDevice {i+1}:")
            logger.info(f"  IP: {device['ip']}")
            logger.info(f"  Device ID: {device['gwId']}")
            logger.info(f"  Product Name: {device.get('productName', 'Unknown')}")
            logger.info(f"  Version: {device.get('version', 'Unknown')}")
            logger.info(f"  Type: {device.get('type', 'Unknown')}")
            
            # Additional details
            if args.verbose:
                logger.info("\nFull device details:")
                for key, value in device.items():
                    logger.info(f"  {key}: {value}")
        except Exception as e:
            logger.error(f"Error processing device info: {e}")
    
    # Save to file if requested
    if args.output:
        try:
            with open(args.output, 'w') as f:
                json.dump(devices, f, indent=2)
            logger.info(f"\nDevice information saved to {args.output}")
        except Exception as e:
            logger.error(f"Error saving to file: {e}")
    
    logger.info("\nImportant: To connect to these devices, you need the 'local key'")
    logger.info("You can get this from the Tuya IoT Cloud Platform or by extracting it from the app")
    logger.info("See https://github.com/jasonacox/tinytuya for more details")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Scan for Tuya devices on the network')
    parser.add_argument('--timeout', type=int, default=8, help='Timeout in seconds for device discovery (default: 8)')
    parser.add_argument('--output', help='Save device information to a JSON file')
    parser.add_argument('--verbose', action='store_true', help='Show all available device details')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    return parser.parse_args()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nScan interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)