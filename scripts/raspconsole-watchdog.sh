#!/bin/bash
# RasP-Console Watchdog - controlla e ripristina tutti i servizi ogni 60 secondi
# Esegue health check e riavvia servizi bloccati

LOG="/var/log/ConsolePi/watchdog.log"
MAX_LOG_SIZE=1048576  # 1MB

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG"
}

# Tronca log se troppo grande
[ -f "$LOG" ] && [ "$(stat -f%z "$LOG" 2>/dev/null || stat -c%s "$LOG" 2>/dev/null)" -gt "$MAX_LOG_SIZE" ] && tail -100 "$LOG" > "${LOG}.tmp" && mv "${LOG}.tmp" "$LOG"

# 1. Fix latency_timer FTDI (ogni boot o hotplug potrebbe resettarlo)
for dev in /sys/bus/usb-serial/devices/ttyUSB*/latency_timer; do
    [ -f "$dev" ] && [ "$(cat "$dev")" != "1" ] && echo 1 > "$dev" && log "FIX latency_timer: $dev"
done

# 2. Controlla dashboard (porta 8888)
if ! ss -tlnp | grep -q ':8888 '; then
    log "RESTART consolepi-web (porta 8888 non in ascolto)"
    systemctl restart consolepi-web
fi

# Health check dashboard - deve rispondere in 5 secondi
if ! curl -sf --max-time 5 http://localhost:8888/status > /dev/null 2>&1; then
    log "RESTART consolepi-web (non risponde)"
    # Kill zombie processes
    fuser -k 8888/tcp 2>/dev/null
    sleep 1
    systemctl restart consolepi-web
fi

# 3. Controlla ttyd (porta 8080) - solo se c'e un device USB
if ls /dev/ttyUSB* > /dev/null 2>&1 || ls /dev/ttyACM* > /dev/null 2>&1; then
    if ! ss -tlnp | grep -q ':8080 '; then
        log "RESTART ttyd-console (device presente ma porta 8080 non in ascolto)"
        systemctl restart ttyd-console
    fi
fi

# 4. Controlla consolepi-api (porta 5000)
if ! ss -tlnp | grep -q ':5000 '; then
    log "RESTART consolepi-api (porta 5000 non in ascolto)"
    systemctl restart consolepi-api 2>/dev/null
fi

# 5. Controlla connettivita internet (per Telegram)
if ! ping -c 1 -W 3 8.8.8.8 > /dev/null 2>&1; then
    log "WARN nessuna connettivita internet"
fi

# 6. Controlla spazio disco
DISK_USE=$(df / | awk 'NR==2 {print $5}' | tr -d '%')
if [ "$DISK_USE" -gt 90 ]; then
    log "WARN disco al ${DISK_USE}%"
    # Pulisci log vecchi
    find /var/log/ConsolePi/serial/ -name "*.log" -mtime +30 -delete 2>/dev/null
fi
