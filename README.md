# RasP-Console

**[English]** | [Italiano](#italiano)

A Raspberry Pi-based serial console server for network switches, featuring a web terminal, Telegram notifications, and automated monitoring.

Designed for multi-site deployments by field technicians — each unit boots, reports its IP via Telegram, and provides instant browser-based access to the switch console port.

![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi-red)
![OS](https://img.shields.io/badge/OS-Debian%20Trixie-blue)
![Terminal](https://img.shields.io/badge/terminal-ttyd%201.7.7-green)

## Features

- **Web terminal** at `http://<ip>:8080` — browser-based serial console via [ttyd](https://github.com/tsl0922/ttyd)
- **Ctrl+C / Ctrl+V** clipboard support via nginx reverse proxy with JS injection
- **Backspace fix** for Huawei VRP switches (DEL → BS conversion)
- **Proper line rendering** — ONLCR fix for correct newline handling in web terminal
- **Telegram notifications** — boot, shutdown, USB connect/disconnect, switch hostname
- **Switch auto-identification** — reads switch hostname on USB connect, reports to Telegram
- **Hardware watchdog** — automatic reboot if system hangs
- **FTDI latency fix** — 1ms latency timer (vs 16ms default) for clean serial output at 9600 baud
- **Session logging** — serial sessions logged to `/var/log/ConsolePi/serial/`
- **Log rotation** — automatic cleanup of logs older than 30 days

## Architecture

```
Browser → nginx :8080 (Ctrl+V fix) → ttyd :8081 → serial-console.py → /dev/ttyUSB0 → Switch
```

| Port | Service | Description |
|------|---------|-------------|
| 8080 | nginx   | Reverse proxy with clipboard JS injection |
| 8081 | ttyd    | Web terminal (xterm.js) |
| 8888 | Dashboard | OceanX-style status page |
| 5000 | ConsolePi API | REST API |

## Hardware

- Raspberry Pi (any model with USB)
- FTDI FT232R USB-to-serial adapter
- Console cable (RJ45 rollover for Huawei)
- Tested with: **Huawei CloudEngine** series switches (9600 baud)

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/mmereu/raspconsole.git
cd raspconsole
```

### 2. Configure Telegram (optional)

Edit `scripts/telegram-notify.sh` and `scripts/switch-identify.sh`:

```bash
TELEGRAM_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID="YOUR_TELEGRAM_GROUP_CHAT_ID"
```

### 3. Install dependencies

```bash
sudo apt-get install -y nginx python3 picocom
# Install ttyd v1.7.7 from https://github.com/tsl0922/ttyd/releases
sudo cp /usr/local/bin/ttyd /usr/local/bin/ttyd
```

### 4. Deploy files

```bash
# Scripts
sudo cp scripts/*.py scripts/*.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/*.py /usr/local/bin/*.sh

# Systemd services
sudo cp systemd/*.service systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ttyd-console.service raspconsole-watchdog.timer

# nginx
sudo mkdir -p /etc/nginx/static
sudo cp nginx/static/paste-fix.js /etc/nginx/static/
sudo cp nginx/ttyd.conf /etc/nginx/sites-available/ttyd
sudo ln -sf /etc/nginx/sites-available/ttyd /etc/nginx/sites-enabled/ttyd
sudo rm -f /etc/nginx/sites-enabled/default
sudo systemctl enable --now nginx

# udev rules
sudo cp udev/*.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
```

### 5. Set hostname (one per unit)

```bash
sudo hostnamectl set-hostname RasP-Console-SiteName
```

## File Structure

```
raspconsole/
├── scripts/
│   ├── serial-console.py          # Serial bridge (backspace + ONLCR fix)
│   ├── console-connect.sh         # ttyd entry point
│   ├── telegram-notify.sh         # Telegram notification sender
│   ├── switch-identify.sh         # Auto-detect switch hostname
│   └── raspconsole-watchdog.sh    # Service health watchdog
├── systemd/
│   ├── ttyd-console.service       # ttyd web terminal
│   ├── consolepi-web.service      # Status dashboard
│   ├── raspconsole-watchdog.*     # Watchdog timer + service
│   └── consolepi-telegram-*.service  # Telegram event triggers
├── nginx/
│   ├── ttyd.conf                  # Reverse proxy config
│   └── static/paste-fix.js       # Ctrl+V clipboard injection
├── udev/
│   ├── 98-serial-latency.rules    # FTDI 1ms latency fix
│   └── 99-usb-serial-telegram.rules  # USB event → Telegram
└── web/
    └── web-landing.py             # Status dashboard (port 8888)
```

## Technical Notes

- `tty.setraw()` disables `ONLCR` on the PTY slave — `serial-console.py` manually converts `\n→\r\n` on serial output
- `navigator.clipboard` requires HTTPS in Chrome — clipboard support uses native browser paste events instead
- FTDI default latency of 16ms causes fragmented output at 9600 baud — udev rule sets it to 1ms persistently
- `BindsTo=` on device units causes permanent stops on disconnect — use `Restart=always` instead
- ser2net conflicts with picocom on the same port — disabled in favor of direct picocom

## Multi-Deploy

Clone the SD card from a configured unit. Only change the hostname per unit:

```bash
sudo hostnamectl set-hostname RasP-Console-<TechnicianName>
```

All units report to the same Telegram group automatically.

## License

MIT

---

## Italiano

Console seriale su Raspberry Pi per switch di rete, con terminale web, notifiche Telegram e monitoraggio automatico.

Progettato per deployment multi-sito da tecnici installatori — ogni unità si avvia, comunica il proprio IP via Telegram e fornisce accesso immediato alla porta console dello switch tramite browser.

## Funzionalità

- **Terminale web** su `http://<ip>:8080` — console seriale via browser con [ttyd](https://github.com/tsl0922/ttyd)
- **Ctrl+C / Ctrl+V** — supporto appunti tramite nginx reverse proxy con injection JavaScript
- **Fix Backspace** per switch Huawei VRP (conversione DEL → BS)
- **Rendering corretto** — fix ONLCR per visualizzazione corretta delle righe nel terminale web
- **Notifiche Telegram** — avvio, spegnimento, connessione/disconnessione USB, hostname switch
- **Identificazione automatica switch** — legge l'hostname dello switch alla connessione USB e lo invia su Telegram
- **Hardware watchdog** — riavvio automatico in caso di blocco del sistema
- **Fix latenza FTDI** — latency timer a 1ms (vs 16ms default) per output seriale pulito a 9600 baud
- **Log sessioni** — sessioni seriali salvate in `/var/log/ConsolePi/serial/`
- **Rotazione log** — pulizia automatica dei log più vecchi di 30 giorni

## Architettura

```
Browser → nginx :8080 (fix Ctrl+V) → ttyd :8081 → serial-console.py → /dev/ttyUSB0 → Switch
```

| Porta | Servizio | Descrizione |
|-------|----------|-------------|
| 8080  | nginx    | Reverse proxy con injection JS per appunti |
| 8081  | ttyd     | Terminale web (xterm.js) |
| 8888  | Dashboard | Pagina di stato stile OceanX |
| 5000  | ConsolePi API | REST API |

## Hardware

- Raspberry Pi (qualsiasi modello con USB)
- Adattatore USB-seriale FTDI FT232R
- Cavo console (rollover RJ45 per Huawei)
- Testato con switch serie **Huawei CloudEngine** (9600 baud)

## Avvio rapido

### 1. Clona e configura

```bash
git clone https://github.com/mmereu/raspconsole.git
cd raspconsole
```

### 2. Configura Telegram (opzionale)

Modifica `scripts/telegram-notify.sh` e `scripts/switch-identify.sh`:

```bash
TELEGRAM_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID="YOUR_TELEGRAM_GROUP_CHAT_ID"
```

### 3. Installa le dipendenze

```bash
sudo apt-get install -y nginx python3 picocom
# Installa ttyd v1.7.7 da https://github.com/tsl0922/ttyd/releases
```

### 4. Deploy dei file

```bash
# Script
sudo cp scripts/*.py scripts/*.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/*.py /usr/local/bin/*.sh

# Servizi systemd
sudo cp systemd/*.service systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ttyd-console.service raspconsole-watchdog.timer

# nginx
sudo mkdir -p /etc/nginx/static
sudo cp nginx/static/paste-fix.js /etc/nginx/static/
sudo cp nginx/ttyd.conf /etc/nginx/sites-available/ttyd
sudo ln -sf /etc/nginx/sites-available/ttyd /etc/nginx/sites-enabled/ttyd
sudo rm -f /etc/nginx/sites-enabled/default
sudo systemctl enable --now nginx

# Regole udev
sudo cp udev/*.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
```

### 5. Imposta l'hostname (uno per unità)

```bash
sudo hostnamectl set-hostname RasP-Console-NomeTecnico
```

## Note tecniche

- `tty.setraw()` disabilita `ONLCR` sul PTY slave — `serial-console.py` converte manualmente `\n→\r\n` sull'output seriale
- `navigator.clipboard` richiede HTTPS in Chrome — il supporto appunti usa invece gli eventi paste nativi del browser
- La latenza FTDI default di 16ms causa output frammentato a 9600 baud — la regola udev la imposta a 1ms in modo persistente
- `BindsTo=` sulle device unit causa stop permanenti alla disconnessione — usare `Restart=always`
- ser2net va in conflitto con picocom sulla stessa porta — disabilitato in favore di picocom diretto

## Multi-Deploy

Clona la SD card da un'unità configurata. Cambia solo l'hostname per distinguere le unità:

```bash
sudo hostnamectl set-hostname RasP-Console-<NomeTecnico>
```

Tutte le unità inviano notifiche allo stesso gruppo Telegram automaticamente.
