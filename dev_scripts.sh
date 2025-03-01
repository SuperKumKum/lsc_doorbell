#!/bin/bash
# Development and debugging scripts for LSC Tuya Doorbell component

# Install component for local development
install_local() {
  echo "Installing component for local development..."
  mkdir -p "$HOME/.homeassistant/custom_components/lsc_tuya_doorbell/"
  cp -r custom_components/lsc_tuya_doorbell/* "$HOME/.homeassistant/custom_components/lsc_tuya_doorbell/"
  echo "Component installed to $HOME/.homeassistant/custom_components/lsc_tuya_doorbell/"
}

# Enable debug logs
enable_debug_logs() {
  LOGGER_CONFIG="logger:\n  default: info\n  logs:\n    custom_components.lsc_tuya_doorbell: debug"
  
  if grep -q "custom_components.lsc_tuya_doorbell" "$HOME/.homeassistant/configuration.yaml"; then
    echo "Debug logging already configured"
  else
    echo -e "\n# Debug logging for LSC Tuya Doorbell\n$LOGGER_CONFIG" >> "$HOME/.homeassistant/configuration.yaml"
    echo "Debug logging configured in configuration.yaml"
  fi
}

# Test connectivity to a device
test_device_connection() {
  if [ -z "$1" ]; then
    echo "Usage: $0 test-connection IP_ADDRESS [PORT]"
    return 1
  fi
  
  IP="$1"
  PORT="${2:-6668}"
  
  echo "Testing connection to $IP:$PORT..."
  nc -zv "$IP" "$PORT"
  
  if [ $? -eq 0 ]; then
    echo "Connection successful!"
  else
    echo "Connection failed!"
  fi
}

# Scan network for devices on port 6668
scan_network() {
  PORT="${1:-6668}"
  echo "Scanning network for devices on port $PORT..."
  
  # Get local network information
  IP_BASE=$(ip route | grep default | awk '{print $3}' | cut -d. -f1-3)
  
  if [ -z "$IP_BASE" ]; then
    echo "Could not determine network address"
    return 1
  fi
  
  echo "Scanning network $IP_BASE.0/24 for port $PORT..."
  for i in $(seq 1 254); do
    (nc -zv -w 1 "$IP_BASE.$i" "$PORT" 2>&1 | grep succeeded) &
    # Limit parallel processes
    if [ $((i % 10)) -eq 0 ]; then
      wait
    fi
  done
  
  wait
  echo "Scan complete"
}

# Monitor component logs
monitor_logs() {
  LOG_FILE="$HOME/.homeassistant/home-assistant.log"
  
  if [ ! -f "$LOG_FILE" ]; then
    echo "Log file not found at $LOG_FILE"
    return 1
  fi
  
  echo "Monitoring logs for lsc_tuya_doorbell component..."
  tail -f "$LOG_FILE" | grep "lsc_tuya_doorbell"
}

# Decode base64 payload (for testing)
decode_payload() {
  if [ -z "$1" ]; then
    echo "Usage: $0 decode-payload BASE64_STRING"
    return 1
  fi
  
  echo "Decoding base64 payload..."
  echo "$1" | base64 -d | jq .
}

# Main script logic
case "$1" in
  install)
    install_local
    ;;
  debug-logs)
    enable_debug_logs
    ;;
  test-connection)
    test_device_connection "$2" "$3"
    ;;
  scan-network)
    scan_network "$2"
    ;;
  monitor-logs)
    monitor_logs
    ;;
  decode-payload)
    decode_payload "$2"
    ;;
  *)
    echo "LSC Tuya Doorbell Development Scripts"
    echo ""
    echo "Usage: $0 COMMAND [options]"
    echo ""
    echo "Commands:"
    echo "  install              Install component locally for development"
    echo "  debug-logs           Enable debug logging in configuration.yaml"
    echo "  test-connection IP   Test connection to a device"
    echo "  scan-network [PORT]  Scan network for devices on port (default: 6668)"
    echo "  monitor-logs         Monitor component logs in real-time"
    echo "  decode-payload DATA  Decode base64 payload from logs"
    ;;
esac