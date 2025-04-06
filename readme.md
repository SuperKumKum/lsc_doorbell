# LSC Tuya Doorbell Integration for Home Assistant

![doorbell](https://github.com/jurgenmahn/ha_tuya_doorbell/blob/main/icons/logo.png)

**Answer your door with local control and full privacy!** This Home Assistant integration connects directly to your LSC Smart Connect video doorbell without any cloud dependencies, giving you complete control and privacy.

Available at Action stores across the Netherlands and other European countries, these affordable smart doorbells can now be fully integrated with your Home Assistant setup - no cloud subscription required!

## 🚀 Features

- **Local Control**: Direct communication with your doorbell - no cloud dependency
- **Real-time Events**: Instant notification of doorbell presses and motion detection
- **Complete Privacy**: All data stays within your home network
- **Automatic Discovery**: Finds your doorbell on the network even if its IP changes
- **Smart Automations**: Trigger lights, announcements, and other actions when someone's at your door
- **Reliable Connection**: Maintains persistent connection with automatic reconnection
- **Multiple Protocol Support**: Compatible with various Tuya protocol versions (3.1, 3.2, 3.3, 3.4) for broader device compatibility

## 📋 Requirements

- Home Assistant (Core 2022.5.0 or newer)
- LSC Smart Connect Video Doorbell with Tuya chipset
- Doorbell's Device ID and Local Key (obtained from Tuya Developer platform or using Tuya Cloudcutter)
- Python package: `netifaces>=0.11.0` (installed automatically)

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
   - **Protocol Version**: The Tuya protocol version to use (default: 3.3)

The integration will:
1. Connect directly to your doorbell using the local Tuya protocol
2. Create sensors for motion detection, doorbell button presses, and connection status
3. Set up event triggers you can use in your automations

### Updating Configuration

If you need to modify your doorbell configuration after setup (for example, to change the protocol version or update the local key):

1. Go to **Settings** → **Devices & Services**
2. Find the LSC Tuya Doorbell integration and click **Configure**
3. Update your settings and click **Submit**
4. If updating the protocol version, the integration will attempt to reconnect using the new version

You can also completely remove and re-add the integration if needed.

## 🔍 Finding Your Device's Local Key and ID

To use this integration, you'll need your doorbell's device ID and local key. Here are several methods to obtain these:

### Method 1: TinyTuya Wizard (Recommended)

1. Install TinyTuya: `pip install --user tinytuya`
2. Run the wizard: `python3 -m tinytuya wizard`
3. Follow the prompts to scan your network and retrieve device keys

### Method 2: Tuya IoT Platform

1. Create an account on [Tuya IoT Platform](https://iot.tuya.com/)
2. Create a cloud project and add your devices
3. Get device IDs and local keys from the project settings

### Method 3: Third-Party Tools

- Use [Tuya Cloudcutter](https://github.com/tuya-cloudcutter/tuya-cloudcutter) to unbind your device and generate local keys
- Use the [LSC2MQTT](https://github.com/ACE1046/LSC2MQTT) project which can help retrieve keys for LSC devices

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

### Example Automation: Record Video When Motion Detected

```yaml
automation:
  - alias: "Motion Detection - Record Video"
    trigger:
      platform: event
      event_type: lsc_tuya_doorbell_motion
    action:
      # Turn on camera recording for 30 seconds
      - service: camera.record
        target:
          entity_id: camera.front_door
        data:
          filename: "/config/www/recordings/motion_{{ now().strftime('%Y%m%d_%H%M%S') }}.mp4"
          duration: 30
      # Send notification with thumbnail
      - service: notify.mobile_app
        data:
          title: "Motion Detected"
          message: "Motion detected at the front door"
          data:
            image: "/local/snapshots/front_door_latest.jpg"
            ttl: 0
            priority: high
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

### Example Automation: Log Doorbell Connection Status

```yaml
automation:
  - alias: "Doorbell Connection Status Logger"
    trigger:
      - platform: event
        event_type: lsc_tuya_doorbell_connected
      - platform: event
        event_type: lsc_tuya_doorbell_disconnected
    action:
      - service: persistent_notification.create
        data:
          title: >
            Doorbell {{ trigger.event.event_type.split('_')[-1] | title }}
          message: >
            The doorbell {{ trigger.event.event_type.split('_')[-1] | title }} at {{ trigger.event.data.timestamp }}
            {% if trigger.event.event_type == 'lsc_tuya_doorbell_connected' %}
            IP Address: {{ trigger.event.data.host }}
            {% endif %}
          notification_id: "doorbell_status_{{ trigger.event.event_type.split('_')[-1] }}"
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
- Try different protocol versions (3.1, 3.2, 3.3, 3.4) if your doorbell isn't connecting successfully
- Ensure your doorbell is on the same network as Home Assistant
- Verify your device ID and local key are correct
- Check if your doorbell is using the default port (6668)
- If your doorbell disappears periodically, try setting a static IP for it in your router

### Protocol Version Troubleshooting

If you're having connection issues, try these protocol versions in order:
1. 3.3 (default)
2. 3.1 (works with many older Tuya devices)
3. 3.4 (for newer Tuya devices)
4. 3.2 (less common)

You can diagnose which protocol version works best using the included `test_doorbell_tinytuya.py` script in the dev-scripts directory:

```bash
python3 dev-scripts/test_doorbell_tinytuya.py --ip <DOORBELL_IP> --id <DEVICE_ID> --key <LOCAL_KEY> --version 3.1 --debug
```

## 🛠️ Technical Details

This integration communicates with your doorbell using your selected protocol version of the Tuya local API. It establishes a persistent connection to listen for these specific datapoints:

- DP 185: Doorbell button press events
- DP 115: Motion detection events

These datapoint numbers can be customized in your configuration if your device uses different datapoints.

The integration includes:
- Automatic credential-based device rediscovery if the IP changes
- Multi-protocol support to ensure compatibility with different doorbell variants
- Exponential backoff for reconnection attempts
- Decoded JSON payloads from button presses and motion events

## 🧪 Development Tools

The repository includes several development tools to help troubleshoot and test your doorbell:

- `test_doorbell_pytuya.py`: Test connection using our internal pytuya module
- `test_doorbell_tinytuya.py`: Test connection using TinyTuya library with different protocol versions
- `scan_for_tuya_devices.py`: Scan your network for any Tuya devices and their details

You can run these tools directly from the `dev-scripts/` directory to diagnose connection issues.

## 📝 Credits

This Home Assistant integration was developed with the assistance of AI tools:

- Aider: Initially used as an AI coding assistant to help develop and refine the codebase
- Claude Code: Used as an AI coding assistant to help develop and refine the codebase

100% of the application code was created through collaboration with these AI assistants.
Special thanks to the Home Assistant community for their excellent documentation and frameworks that made this integration possible.

## License

This project is licensed under the MIT License.

---

## 🚀 Built with human ingenuity & a dash of AI wizardry

This project emerged from late-night coding sessions, unexpected inspiration, and the occasional debugging dance. Every line of code has a story behind it.

Found a bug? Have a wild idea? The issues tab is your canvas.

Authored By: [👨‍💻 Jurgen Mahn](https://github.com/jurgenmahn) with some help from AI code monkies [Claude](https://claude.ai) & [Manus.im](https://manus.im/app)

*"Sometimes the code writes itself. Other times, we collaborate with the machines."*

⚡ Happy hacking, fellow explorer ⚡