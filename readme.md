# LSC Tuya Doorbell Integration for Home Assistant

![doorbell](https://github.com/jurgenmahn/ha_tuya_doorbell/icons/logo.png)

**Answer your door with local control and full privacy!** This Home Assistant integration connects directly to your LSC Smart Connect video doorbell without any cloud dependencies, giving you complete control and privacy.

Available at Action stores across the Netherlands and other European countries, these affordable smart doorbells can now be fully integrated with your Home Assistant setup - no cloud subscription required!

## 🚀 Features

- **Local Control**: Direct communication with your doorbell - no cloud dependency
- **Real-time Events**: Instant notification of doorbell presses and motion detection
- **Complete Privacy**: All data stays within your home network
- **Automatic Discovery**: Finds your doorbell on the network even if its IP changes
- **Smart Automations**: Trigger lights, announcements, and other actions when someone's at your door
- **Reliable Connection**: Maintains persistent connection with automatic reconnection

## 📋 Requirements

- Home Assistant (Core 2022.5.0 or newer)
- LSC Smart Connect Video Doorbell with Tuya chipset
- Doorbell's Device ID and Local Key (obtained from Tuya Developer platform or using Tuya Cloudcutter)

## 📲 Installation

### HACS Installation (Recommended)

1. Make sure you have [HACS](https://hacs.xyz/) installed
2. In HACS, go to "Integrations" → click the three dots → "Custom repositories"
3. Add `https://github.com/jurgenmahn/ha_tuya_doorbell` as a custom repository (Category: Integration)
4. Click "Download" next to the LSC Tuya Doorbell integration
5. Restart Home Assistant

### Manual Installation

1. Download the latest release
2. Copy the `custom_components/lsc_tuya_doorbell` directory to your Home Assistant `custom_components` directory
3. Restart Home Assistant

## ⚙️ Configuration

Setting up is easy through the Home Assistant UI:

1. Go to **Settings** → **Devices & Services**
2. Click the **"+ Add Integration"** button
3. Search for "LSC Tuya Doorbell" and select it
4. Enter the following information:
   - **Name**: A friendly name for your doorbell
   - **Device ID**: Your doorbell's Tuya device ID
   - **Local Key**: Your doorbell's local key
   - **IP Address**: Your doorbell's IP address or a subnet to scan (e.g., 192.168.1.0/24)
   - **Port**: The port your doorbell uses (default: 6668)

The integration will:
1. Connect directly to your doorbell using the local Tuya protocol
2. Create sensors for motion detection, doorbell button presses, and connection status
3. Set up event triggers you can use in your automations

## 🔄 Working with Events

The integration fires these events you can use in your automations:

- `lsc_tuya_doorbell_button_press`: When someone presses the doorbell button
- `lsc_tuya_doorbell_motion`: When motion is detected
- `lsc_tuya_doorbell_connected`: When the doorbell device connects to Home Assistant
- `lsc_tuya_doorbell_disconnected`: When the doorbell device disconnects from Home Assistant

### Example Automation: Flash Lights When Doorbell Pressed

```yaml
automation:
  - alias: "Doorbell Press - Flash Lights"
    trigger:
      platform: event
      event_type: lsc_tuya_doorbell_button_press
    action:
      - service: light.turn_on
        entity_id: light.porch_light
        data:
          flash: short
      - service: notify.mobile_app
        data:
          title: "Doorbell"
          message: "Someone is at the door!"
```

### Example Automation: Get Notified When Doorbell Disconnects

```yaml
automation:
  - alias: "Doorbell Disconnection Alert"
    trigger:
      platform: event
      event_type: lsc_tuya_doorbell_disconnected
    action:
      - service: notify.mobile_app
        data:
          title: "Doorbell Alert"
          message: "Your doorbell has disconnected from Home Assistant"
          data:
            channel: "Doorbell Status"
            importance: high
```

## 🔍 Troubleshooting

Having issues? Try these steps:

- Enable debug logging by adding to your `configuration.yaml`:
  ```yaml
  logger:
    default: info
    logs:
      custom_components.lsc_tuya_doorbell: debug
  ```
- Ensure your doorbell is on the same network as Home Assistant
- Verify your device ID and local key are correct
- Check if your doorbell is using the default port (6668)
- If your doorbell disappears periodically, try setting a static IP for it in your router

## 🛠️ Technical Details

This integration communicates with your doorbell using protocol version 3.3 of the Tuya local API. It establishes a persistent connection to listen for these specific datapoints:

- DP 185: Doorbell button press events
- DP 115: Motion detection events

The integration includes:
- Automatic credential-based device rediscovery if the IP changes
- Exponential backoff for reconnection attempts
- Decoded JSON payloads from button presses and motion events

## 📝 Credits

This Home Assistant integration was developed with the assistance of AI tools:

Aider: Initially used as an AI coding assistant to help develop and refine the codebase
Claude Code: Used as an AI coding assistant to help develop and refine the codebase

100% of the application code was created through collaboration with these AI assistants.
Special thanks to the Home Assistant community for their excellent documentation and frameworks that made this integration possible.

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.