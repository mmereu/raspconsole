#!/bin/bash
# Serial console via Python - gestisce backspace correttamente

LOG_DIR="/var/log/ConsolePi/serial"
mkdir -p "$LOG_DIR"

# Fix latency FTDI
echo 1 > /sys/bus/usb-serial/devices/ttyUSB0/latency_timer 2>/dev/null

exec python3 /usr/local/bin/serial-console.py /dev/ttyUSB0 9600
