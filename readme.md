# LSC Tuya Doorbell Integration for Home Assistant

This integration adds support for LSC branded Tuya doorbells sold at Action stores in the Netherlands. It works by connecting to the doorbell's local API using the device ID and key.

## Features

- Doorbell button press detection
- Motion detection

Other features (like video streaming, two-way audio, etc.) are not implemented as they are already covered by other integrations.

## Prerequisites

- Home Assistant instance
- Tuya/LSC doorbell (from Action stores)
- Device ID and local key for your doorbell (see "Getting Device ID and Key" section)
- The doorbell must be on the same network as your Home Assistant instance

## Installation

### HACS (Recommended)

1. Make sure [HACS](https://hacs.xyz/) is installed
2. Add this repository as a custom repository in HACS:
   - Go to HACS → Integrations → ⋮ (menu) → Custom repositories
   - Add the URL of this repository
   - Category: Integration
3. Click "Install"
4. Restart Home Assistant

### Manual Installation

1. Download the latest release
2. Copy the `lsc_tuya_doorbell` directory to your `config/custom_components` directory
3. Restart Home Assistant

## Configuration

Add the following to your `configuration.yaml`:

```yaml
lsc_tuya_doorbell:
  devices:
    - name: Front Door
      device_id: YOUR_DEVICE_ID
      local_key: YOUR_LOCAL_KEY
      host: 192.168.1.x  # Optional, will auto-discover if not specified
```

## Getting Device ID and Key

You can extract the device ID and local key using one of these methods:

1. Use the [Tuya IoT Platform](https://iot.tuya.com/)
2. Use [Tuya Smart app with LSC devices](https://play.google.com/store/apps/details?id=com.tuya.smart)
3. Extract from the app using methods described in the [tuyapi project](https://github.com/codetheweb/tuyapi/blob/master/docs/SETUP.md)

## Events

This integration fires the following events:

- `lsc_tuya_doorbell_button_press` - When the doorbell button is pressed
- `lsc_tuya_doorbell_motion` - When motion is detected

## Usage with Automations

Example automation to announce when the doorbell is pressed:

```yaml
automation:
  - alias: "Doorbell Press Announcement"
    trigger:
      platform: event
      event_type: lsc_tuya_doorbell_button_press
    action:
      - service: tts.google_translate_say
        data:
          entity_id: media_player.living_room_speaker
          message: "Someone is at the door"
```

## Troubleshooting

- Make sure your doorbell and Home Assistant are on the same network
- Verify your device ID and local key are correct
- Check Home Assistant logs for any error messages
- Try specifying the host IP manually if auto-discovery fails

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- This project was built using the [Tuya Local API](https://developer.tuya.com/en/docs/iot/device-access-service?id=Ka8fdh5o7iubk)
- Special thanks to the Home Assistant community