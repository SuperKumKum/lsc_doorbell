# TinyTuya Wizard Guide

The TinyTuya library includes a wizard that can help you discover Tuya devices on your network and find their local keys. This is often more reliable than trying to manually specify protocol versions.

## How to Use the TinyTuya Wizard

1. Open a terminal and run:

```bash
python3 -m tinytuya wizard
```

This will:
- Scan your network for Tuya devices
- Help you get the device keys (you'll need the Tuya IoT Platform credentials)
- Test the connection to each device
- Generate a `devices.json` file with all the discovered information

## Key Steps in the Wizard

1. **Initial Scan**: Scans your network for Tuya devices and shows what it finds
2. **Get Device Keys**: You'll need to connect to the Tuya IoT Platform to get the device keys
3. **Test Devices**: Tests connection to each device using different protocol versions
4. **Configuration**: Creates a devices.json file with all the device information

## Other Helpful TinyTuya Commands

### Scan the Network Only
```bash
python3 -m tinytuya scan
```

### Monitor a Device's Status
```bash
python3 -m tinytuya monitor DEVICE_ID IP_ADDRESS LOCAL_KEY
```

For example:
```bash
python3 -m tinytuya monitor XXXXXXXXXXXXXXXXvg 92.168.113.26 XXXXXXXXXXX62
```

### Sniff for TuyaMCU Devices (Protocol 3.4)
```bash
python3 -m tinytuya sniff
```

## Next Steps After Getting the Correct Information

Once you've found the correct device information (IP, ID, key, protocol version), update your Home Assistant component to use these values. If the protocol version is different than 3.3, that's likely why your current implementation isn't working.

## Additional References

- TinyTuya GitHub: https://github.com/jasonacox/tinytuya
- Tuya Local Home Assistant Integration: https://github.com/rospogrigio/localtuya