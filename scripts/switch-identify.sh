#!/bin/bash
# Identify connected switch via serial port
# Sends CR, reads prompt (e.g. <HUAWEI>), saves to /tmp/switch-hostname.txt

DEVICE="/dev/ttyUSB0"
OUTPUT_FILE="/tmp/switch-hostname.txt"
BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
CHAT_ID="YOUR_TELEGRAM_GROUP_CHAT_ID"
HOSTNAME_PI=$(hostname)
IP=$(hostname -I 2>/dev/null | awk '{print $1}')

# Wait for device to be ready
sleep 2

# Check device exists
if [ ! -e "$DEVICE" ]; then
    echo "unknown" > "$OUTPUT_FILE"
    exit 1
fi

# Send CR and read response (3 seconds timeout)
RESPONSE=$(python3 -c "
import serial, time
try:
    s = serial.Serial('$DEVICE', 9600, timeout=3)
    s.write(b'\r')
    time.sleep(2)
    data = s.read(4096).decode('utf-8', errors='ignore')
    s.close()
    print(data)
except Exception as e:
    print('')
" 2>/dev/null)

# Extract hostname from prompt (e.g. <HUAWEI> or [HUAWEI])
SWITCH_HOST=$(echo "$RESPONSE" | grep -oP '(?<=<)[^>]+(?=>)' | tail -1)
if [ -z "$SWITCH_HOST" ]; then
    SWITCH_HOST=$(echo "$RESPONSE" | grep -oP '(?<=\[)[^\]]+(?=\])' | tail -1)
fi
if [ -z "$SWITCH_HOST" ]; then
    SWITCH_HOST="switch-sconosciuto"
fi

# Save hostname
echo "$SWITCH_HOST" > "$OUTPUT_FILE"

# Send Telegram notification
DATE=$(date '+%d/%m/%Y %H:%M:%S')
curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
    -d "chat_id=${CHAT_ID}" \
    -d "text=🔍 <b>Switch identificato</b> su ${HOSTNAME_PI}
📅 ${DATE}
🌐 IP: <code>${IP}</code>
📟 Switch: <b>${SWITCH_HOST}</b>
🔗 Console: http://${IP}:8080" \
    -d "parse_mode=HTML" > /dev/null 2>&1
