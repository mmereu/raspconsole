#!/bin/bash
# RaspberryConsole Telegram Notification Script
# Sends notifications on boot (with internet) and USB cable events

BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
CHAT_ID="YOUR_TELEGRAM_GROUP_CHAT_ID"
HOSTNAME=$(hostname)
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
DATE=$(date '+%d/%m/%Y %H:%M:%S')

send_telegram() {
    local message="$1"
    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d "chat_id=${CHAT_ID}" \
        -d "text=${message}" \
        -d "parse_mode=HTML" > /dev/null 2>&1
}

case "$1" in
    boot)
        # Wait for network connectivity
        for i in $(seq 1 30); do
            if ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1; then
                IP=$(hostname -I 2>/dev/null | awk '{print $1}')
                send_telegram "🟢 <b>${HOSTNAME}</b> avviato
📅 ${DATE}
🌐 IP: <code>${IP}</code>
🔗 Console: http://${IP}:8080
📊 Dashboard: http://${IP}:8888"
                exit 0
            fi
            sleep 2
        done
        # No internet after 60s
        send_telegram "🟡 <b>${HOSTNAME}</b> avviato (senza internet)
📅 ${DATE}
🌐 IP: <code>${IP:-N/A}</code>"
        ;;
    usb-connect)
        DEVICE="$2"
        DEVNAME=$(basename "$DEVICE" 2>/dev/null)
        send_telegram "🔌 <b>Cavo USB collegato</b> su ${HOSTNAME}
📅 ${DATE}
📟 Device: <code>${DEVICE}</code>
🔗 Console: http://${IP}:8080"
        ;;
    usb-disconnect)
        DEVICE="$2"
        send_telegram "⚡ <b>Cavo USB scollegato</b> su ${HOSTNAME}
📅 ${DATE}
📟 Device: <code>${DEVICE}</code>"
        ;;
    shutdown)
        send_telegram "🔴 <b>${HOSTNAME}</b> in spegnimento
📅 ${DATE}"
        ;;
    *)
        echo "Usage: $0 {boot|usb-connect|usb-disconnect|shutdown} [device]"
        exit 1
        ;;
esac
