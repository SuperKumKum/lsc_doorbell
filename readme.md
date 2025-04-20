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
- **Doorbell Image Support**: Automatically extracts image URLs from doorbell events for display in Home Assistant
- **Advanced Payload Decoding**: Handles multiple data formats to ensure image compatibility
- **Event Tracking**: Tracks doorbell and motion events with timestamps and counters

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

### 📸 Displaying Doorbell Images

When a doorbell event occurs, the integration will automatically extract image URLs from various payload formats and make them available in your Home Assistant. The image URLs are stored in the connection status sensor attributes and can be displayed using Lovelace cards.

#### Connection Status Sensor Attributes

The connection status sensor (`sensor.lsc_tuya_doorbell_connection_status`) now includes the following attributes:

- `doorbell_count`: Total number of doorbell button press events
- `motion_count`: Total number of motion detection events
- `last_doorbell_time`: Timestamp of the last doorbell press
- `last_motion_time`: Timestamp of the last motion detection
- `last_doorbell_image`: URL of the image from the last doorbell press
- `last_motion_image`: URL of the image from the last motion detection
- `doorbell_image_url`: Same as last_doorbell_image, formatted for Lovelace cards
- `motion_image_url`: Same as last_motion_image, formatted for Lovelace cards

#### Lovelace Card for Doorbell Images

```yaml
type: picture-entity
entity: sensor.lsc_tuya_doorbell_connection_status
image: "{{ state_attr('sensor.lsc_tuya_doorbell_connection_status', 'doorbell_image_url') }}"
name: Last Doorbell Image
show_state: false
show_name: true
camera_view: auto
```

#### Lovelace Card for Motion Detection Images

```yaml
type: picture-entity
entity: sensor.lsc_tuya_doorbell_connection_status
image: "{{ state_attr('sensor.lsc_tuya_doorbell_connection_status', 'motion_image_url') }}"
name: Last Motion Image
show_state: false
show_name: true
camera_view: auto
```

#### Picture-Elements Card with Latest Event Information

This card shows both doorbell and motion images along with event counts and timestamps:

```yaml
type: picture-elements
image: /local/images/doorbell-background.jpg
elements:
  - type: picture
    entity: sensor.lsc_tuya_doorbell_connection_status
    image: "{{ state_attr('sensor.lsc_tuya_doorbell_connection_status', 'doorbell_image_url') }}"
    style:
      top: 25%
      left: 25%
      width: 40%
      border-radius: 8px
  - type: state-label
    entity: sensor.lsc_tuya_doorbell_connection_status
    attribute: doorbell_count
    prefix: "Doorbell Events: "
    style:
      top: 50%
      left: 25%
  - type: state-label
    entity: sensor.lsc_tuya_doorbell_connection_status
    attribute: last_doorbell_time
    prefix: "Last Press: "
    style:
      top: 55%
      left: 25%
  - type: picture
    entity: sensor.lsc_tuya_doorbell_connection_status
    image: "{{ state_attr('sensor.lsc_tuya_doorbell_connection_status', 'motion_image_url') }}"
    style:
      top: 25%
      left: 75%
      width: 40%
      border-radius: 8px
  - type: state-label
    entity: sensor.lsc_tuya_doorbell_connection_status
    attribute: motion_count
    prefix: "Motion Events: "
    style:
      top: 50%
      left: 75%
  - type: state-label
    entity: sensor.lsc_tuya_doorbell_connection_status
    attribute: last_motion_time
    prefix: "Last Motion: "
    style:
      top: 55%
      left: 75%
```

You can also include these images in notifications:

```yaml
service: notify.mobile_app
data:
  title: "Someone at the Door!"
  message: "Doorbell pressed at {{ now().strftime('%H:%M:%S') }}"
  data:
    image: "{{ state_attr('sensor.lsc_tuya_doorbell_connection_status', 'doorbell_image_url') }}"
    # Optional - use a different notification channel
    channel: "Doorbell Alerts"
    # Optional - make the notification sticky
    sticky: true
```

#### Multi-Camera Dashboard Card

This example creates a more comprehensive dashboard with both doorbell and motion images:

```yaml
type: vertical-stack
cards:
  - type: markdown
    content: >
      # Doorbell Status
      Status: {{ states('sensor.lsc_tuya_doorbell_connection_status') }}
  - type: horizontal-stack
    cards:
      - type: picture-entity
        entity: sensor.lsc_tuya_doorbell_connection_status
        name: Last Doorbell Image
        image: "{{ state_attr('sensor.lsc_tuya_doorbell_connection_status', 'doorbell_image_url') }}"
        camera_view: auto
      - type: picture-entity
        entity: sensor.lsc_tuya_doorbell_connection_status
        name: Last Motion Image
        image: "{{ state_attr('sensor.lsc_tuya_doorbell_connection_status', 'motion_image_url') }}"
        camera_view: auto
  - type: glance
    entities:
      - entity: sensor.lsc_tuya_doorbell_connection_status
        name: Status
      - entity: sensor.lsc_tuya_doorbell_connection_status
        name: Doorbell Events
        attribute: doorbell_count
      - entity: sensor.lsc_tuya_doorbell_connection_status
        name: Motion Events
        attribute: motion_count
```

### Example Automation: Doorbell Press with Image Notification

```yaml
automation:
  - alias: "Doorbell Press - Notification with Image"
    trigger:
      platform: event
      event_type: lsc_tuya_doorbell_button_press
    action:
      # Flash lights to indicate someone is at the door
      - service: light.turn_on
        target:
          entity_id: light.porch_light
        data:
          flash: short
          
      # Wait briefly for the image URL to be processed
      - delay:
          seconds: 1
          
      # Get current count of doorbell presses today
      - service: counter.increment
        target:
          entity_id: counter.daily_doorbell_presses
          
      # Announce on speakers
      - service: media_player.volume_set
        target:
          entity_id: media_player.living_room_speaker
        data:
          volume_level: 0.6
      - service: tts.google_translate_say
        target:
          entity_id: media_player.living_room_speaker
        data:
          message: "Someone is at the door"
          
      # Send rich notification with doorbell image
      - service: notify.mobile_app
        data:
          title: "🔔 Doorbell Pressed"
          message: >
            Someone is at the door!
            Time: {{ now().strftime('%H:%M:%S') }}
            Event #{{ state_attr('sensor.lsc_tuya_doorbell_connection_status', 'doorbell_count') }}
          data:
            image: "{{ state_attr('sensor.lsc_tuya_doorbell_connection_status', 'doorbell_image_url') }}"
            # Make it a high priority notification
            priority: high
            # Group all doorbell notifications with the same tag
            tag: "doorbell_press"
            # Make it sticky so user has to dismiss it
            sticky: true
            # Use a specific channel (Android)
            channel: "Doorbell Alerts"
            # Add action buttons (Android)
            actions:
              - action: "UNLOCK_DOOR"
                title: "Unlock Door"
                uri: "/api/services/lock/unlock"
              - action: "IGNORE"
                title: "Ignore"
```

### Example Automation: Motion Detection Notification with Image

```yaml
automation:
  - alias: "Motion Detection - Send Notification with Image"
    trigger:
      platform: event
      event_type: lsc_tuya_doorbell_motion
    action:
      # Wait for image URL to be processed and available in sensor
      - delay:
          seconds: 1
          
      # Send notification with motion image
      - service: notify.mobile_app
        data:
          title: "Motion Detected"
          message: "Motion detected at {{ now().strftime('%H:%M:%S') }} (Event #{{ state_attr('sensor.lsc_tuya_doorbell_connection_status', 'motion_count') }})"
          data:
            image: "{{ state_attr('sensor.lsc_tuya_doorbell_connection_status', 'motion_image_url') }}"
            ttl: 0
            priority: high
            # Optional - group notifications with the same tag
            tag: "doorbell_motion"
            # Optional - make it sticky
            sticky: true
            
      # Turn on porch light for 2 minutes when motion is detected at night
      - service: light.turn_on
        target:
          entity_id: light.porch_light
        data:
          brightness_pct: 100
        condition:
          condition: sun
          after: sunset
          before: sunrise
          
      # Turn off light after 2 minutes
      - delay:
          minutes: 2
      - service: light.turn_off
        target:
          entity_id: light.porch_light
        condition:
          condition: sun
          after: sunset
          before: sunrise
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

### Troubleshooting Image URLs

If your doorbell images aren't appearing in Home Assistant:

1. Check the debug logs to see if image URLs are being extracted:
   ```yaml
   # In configuration.yaml
   logger:
     default: info
     logs:
       custom_components.lsc_tuya_doorbell: debug
   ```

2. Look for log entries containing "Extracted image URL" to see if URLs are being found.

3. Verify that images exist in the attributes of the connection status sensor:
   ```
   Developer Tools → States → Search for "lsc_tuya_doorbell_connection_status"
   ```

4. If no image URLs are being found, try pressing the doorbell button multiple times to send different types of payloads.

5. Some Tuya doorbell models use different payload formats. The integration now supports multiple formats:
   - Standard Tuya cloud storage format with bucket and files
   - Direct URL in 'url' field
   - URL in 'image_url' field
   - Cloud image with fileId and timeStamp
   - Image paths in any string field
   - Nested objects with URLs

6. If you identify a new image URL format not handled by the integration, please report it in the GitHub issues.

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