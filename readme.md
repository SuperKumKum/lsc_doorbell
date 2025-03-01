# LSC Tuya Doorbell Integration for Home Assistant

A Home Assistant custom component for doorbells sold at Action stores in the Netherlands.
This integration supports LSC Smart Connect video doorbells that use the Tuya platform.

## Features

- Detects doorbell button presses (DP 185)
- Detects motion events (DP 115)
- Provides sensor entities for motion, button press and connection status
- Fires events you can use in automations
- Uses local Tuya protocol - no cloud connection required

## Installation

### HACS (recommended)

1. Make sure you have [HACS](https://hacs.xyz/) installed
2. Add this repository as a custom repository in HACS
3. Install the "LSC Tuya Doorbell" integration from HACS
4. Restart Home Assistant

### Manual installation

1. Copy the `custom_components/lsc_tuya_doorbell` directory to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Configuration

You can add this integration through the Home Assistant UI:

1. Go to Configuration > Integrations
2. Click on "+ Add Integration"
3. Search for "LSC Tuya Doorbell"
4. Follow the configuration steps to add your doorbell device

### Configuration Parameters

- **Device ID**: The Tuya device ID (can be obtained from the Tuya developer platform or tools like Tuya Cloudcutter)
- **Local Key**: The Tuya device local key (can be obtained from the Tuya developer platform or Tuya Cloudcutter)
- **Host**: IP address of your doorbell (optional - will be discovered automatically if not provided)
- **MAC Address**: MAC address of your doorbell (for automatic IP rediscovery if the IP changes)

## Implementation Details

This integration uses a custom PyTuya library to connect to Tuya devices locally. It establishes a persistent connection to the doorbell and listens for events like button presses and motion detection.

Key features of the implementation:

- Async communication with the Tuya device
- Automatic reconnection with exponential backoff
- IP address rediscovery if the doorbell's IP changes
- Support for protocol version 3.3 which is common for these devices
- Comprehensive logging for debugging

## Events

The integration fires the following events that you can use in your automations:

- `lsc_tuya_doorbell_button_press`: Fired when someone presses the doorbell button
- `lsc_tuya_doorbell_motion`: Fired when motion is detected

Each event includes:
- `device_id`: The Tuya device ID
- `image_data`: Data payload from the device, which may include image information
- `timestamp`: The time the event was detected

## Troubleshooting

- Enable debug logging for the component by adding the following to your `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.lsc_tuya_doorbell: debug
```
- Ensure your doorbell is on the same network as your Home Assistant instance
- Make sure the device ID and local key are correct
- Check if the correct port is being used (default is 6668)

## Technical Details

The integration communicates with the doorbell device using the Tuya local API protocol version 3.3. It establishes a persistent connection to the device and listens for updates on specific datapoints:

- DP 185: Doorbell button press
- DP 115: Motion detection

These datapoints may contain encoded data that includes information about the event and potentially links to images that were captured.

## Credits

This integration was created by Jurgen Mahn and is based on:
- PyTuya library for local Tuya device communication
- Community research on the Tuya protocol