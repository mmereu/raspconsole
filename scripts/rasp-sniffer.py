#!/usr/bin/env python3
"""RasP-Sniffer — Web UI per packet capture con tshark su Raspberry Pi.
Porta 9090. Avvia/ferma catture, filtra con BPF, scarica il .pcap."""

import json
import os
import signal
import subprocess
import threading
import time
from flask import Flask, Response, jsonify, request, render_template_string, send_file

CAPTURE_DIR = "/var/log/rasp-sniffer"
PCAP_FILE = os.path.join(CAPTURE_DIR, "capture.pcap")
PORT = 9090

os.makedirs(CAPTURE_DIR, exist_ok=True)
app = Flask(__name__)
_lock = threading.Lock()
_proc = None
_start_time = None
_iface = None
_bpf = ""


def get_interfaces():
    try:
        out = subprocess.check_output(["ip", "-o", "link", "show"], text=True, timeout=3)
        ifaces = []
        for line in out.strip().splitlines():
            parts = line.split(":", 2)
            if len(parts) >= 2:
                name = parts[1].strip().split("@")[0]
                if name not in ("lo", ""):
                    ifaces.append(name)
        return ifaces
    except Exception:
        return ["eth0", "wlan0"]


def is_alive():
    return _proc is not None and _proc.poll() is None


HTML = r"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>RasP-Sniffer</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0d1117; color: #c9d1d9; min-height: 100vh; }
    .wrap { max-width: 720px; margin: 0 auto; padding: 32px 16px; }
    header { border-bottom: 1px solid #21262d; padding-bottom: 20px; margin-bottom: 24px; }
    header h1 { font-size: 24px; color: #58a6ff; }
    header p { font-size: 13px; color: #8b949e; margin-top: 4px; }
    .card { background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
    .card h2 { font-size: 12px; color: #58a6ff; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 16px; }
    .row { margin-bottom: 14px; }
    label { display: block; font-size: 12px; color: #8b949e; margin-bottom: 6px; }
    select, input[type=text] {
      width: 100%; padding: 8px 12px; background: #0d1117; color: #c9d1d9;
      border: 1px solid #30363d; border-radius: 6px; font-size: 14px; outline: none;
    }
    select:focus, input:focus { border-color: #58a6ff; }
    .btn-row { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 16px; }
    button {
      padding: 8px 18px; border: none; border-radius: 6px; font-size: 14px;
      font-weight: 600; cursor: pointer; transition: opacity .15s;
    }
    button:hover:not(:disabled) { opacity: .85; }
    button:disabled { opacity: .35; cursor: not-allowed; }
    #btn-start { background: #238636; color: #fff; }
    #btn-stop  { background: #da3633; color: #fff; }
    #btn-dl    { background: #1f6feb; color: #fff; }
    .stats {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 12px;
    }
    .stat { background: #0d1117; border: 1px solid #21262d; border-radius: 6px; padding: 12px; }
    .stat-label { font-size: 11px; color: #8b949e; text-transform: uppercase; letter-spacing: .8px; margin-bottom: 6px; }
    .stat-value { font-size: 20px; font-weight: 700; color: #c9d1d9; }
    .badge { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }
    .badge-off { background: #21262d; color: #8b949e; }
    .badge-on  { background: #1a4520; color: #3fb950; }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
    .badge-on .dot { animation: blink 1s infinite; }
    @keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }
    #log-box {
      background: #0d1117; border: 1px solid #21262d; border-radius: 6px;
      padding: 10px 14px; font-family: 'Courier New', monospace; font-size: 12px;
      color: #8b949e; min-height: 36px;
    }
  </style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>&#x1F4E1; RasP-Sniffer</h1>
    <p>Packet capture web interface &mdash; powered by tshark</p>
  </header>

  <div class="card">
    <h2>Configurazione</h2>
    <div class="row">
      <label for="iface">Interfaccia di rete</label>
      <select id="iface"></select>
    </div>
    <div class="row">
      <label for="bpf">Filtro BPF <span style="color:#484f58">(opzionale &mdash; es: tcp port 443, icmp, host 10.0.0.1)</span></label>
      <input type="text" id="bpf" placeholder="tcp port 80">
    </div>
    <div class="btn-row">
      <button id="btn-start" onclick="startCapture()">&#9654; Avvia cattura</button>
      <button id="btn-stop"  onclick="stopCapture()" disabled>&#9632; Ferma</button>
      <button id="btn-dl"    onclick="location.href='/download'" disabled>&#11015; Scarica .pcap</button>
    </div>
  </div>

  <div class="card">
    <h2>Stato</h2>
    <div class="stats">
      <div class="stat">
        <div class="stat-label">Stato</div>
        <div class="stat-value" id="s-status">
          <span class="badge badge-off"><span class="dot"></span>Fermo</span>
        </div>
      </div>
      <div class="stat">
        <div class="stat-label">Interfaccia</div>
        <div class="stat-value" id="s-iface">&#8212;</div>
      </div>
      <div class="stat">
        <div class="stat-label">Durata</div>
        <div class="stat-value" id="s-dur">&#8212;</div>
      </div>
      <div class="stat">
        <div class="stat-label">File .pcap</div>
        <div class="stat-value" id="s-size">&#8212;</div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Log</h2>
    <div id="log-box">Pronto.</div>
  </div>
</div>

<script>
var $ = function(id) { return document.getElementById(id); };

function log(msg) {
  var t = new Date().toLocaleTimeString('it-IT');
  $('log-box').textContent = '[' + t + '] ' + msg;
}

function fmtBytes(b) {
  if (!b) return '—';
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b/1024).toFixed(1) + ' KB';
  return (b/1048576).toFixed(2) + ' MB';
}

function fmtDur(s) {
  if (!s) return '—';
  var h = Math.floor(s/3600), m = Math.floor(s%3600/60), sec = s%60;
  return (h ? h+'h ' : '') + (m ? m+'m ' : '') + sec + 's';
}

function loadIfaces() {
  fetch('/interfaces').then(function(r){ return r.json(); }).then(function(list) {
    var sel = $('iface');
    sel.innerHTML = '';
    list.forEach(function(i) { sel.add(new Option(i, i)); });
  }).catch(function(){});
}

function updateStatus() {
  fetch('/status').then(function(r){ return r.json(); }).then(function(s) {
    var on = s.capturing;
    $('s-status').innerHTML = on
      ? '<span class="badge badge-on"><span class="dot"></span>In cattura</span>'
      : '<span class="badge badge-off"><span class="dot"></span>Fermo</span>';
    $('s-iface').textContent = s.iface || '—';
    $('s-dur').textContent   = on ? fmtDur(s.duration) : '—';
    $('s-size').textContent  = fmtBytes(s.file_size);
    $('btn-start').disabled = on;
    $('btn-stop').disabled  = !on;
    $('btn-dl').disabled    = !s.file_exists;
  }).catch(function(){});
}

function startCapture() {
  var iface = $('iface').value;
  var bpf   = $('bpf').value.trim();
  fetch('/start', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({iface: iface, filter: bpf})
  }).then(function(r){ return r.json(); }).then(function(d) {
    log(d.message); updateStatus();
  }).catch(function(e) { log('Errore: ' + e); });
}

function stopCapture() {
  fetch('/stop', {method: 'POST'})
    .then(function(r){ return r.json(); })
    .then(function(d) { log(d.message); updateStatus(); })
    .catch(function(e) { log('Errore: ' + e); });
}

loadIfaces();
updateStatus();
setInterval(updateStatus, 2000);
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/interfaces")
def interfaces():
    return jsonify(get_interfaces())


@app.route("/status")
def status():
    size = 0
    try:
        size = os.path.getsize(PCAP_FILE)
    except FileNotFoundError:
        pass
    return jsonify({
        "capturing":   is_alive(),
        "iface":       _iface or "",
        "filter":      _bpf or "",
        "duration":    int(time.time() - _start_time) if _start_time else 0,
        "file_size":   size,
        "file_exists": os.path.exists(PCAP_FILE),
    })


@app.route("/start", methods=["POST"])
def start():
    global _proc, _start_time, _iface, _bpf
    data = request.get_json(force=True) or {}
    iface = data.get("iface", "eth0")
    bpf   = data.get("filter", "").strip()
    with _lock:
        if is_alive():
            return jsonify({"ok": False, "message": "Cattura gia' in corso"})
        try:
            os.remove(PCAP_FILE)
        except FileNotFoundError:
            pass
        cmd = ["tshark", "-i", iface, "-w", PCAP_FILE]
        if bpf:
            cmd += ["-f", bpf]
        try:
            _proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            _start_time = time.time()
            _iface = iface
            _bpf   = bpf
            msg = "Cattura avviata su " + iface
            if bpf:
                msg += " | filtro: " + bpf
            return jsonify({"ok": True, "message": msg})
        except FileNotFoundError:
            return jsonify({"ok": False, "message": "tshark non trovato — installa: sudo apt install tshark"})
        except PermissionError:
            return jsonify({"ok": False, "message": "Permesso negato — eseguire il servizio come root"})
        except Exception as e:
            return jsonify({"ok": False, "message": str(e)})


@app.route("/stop", methods=["POST"])
def stop():
    global _proc, _start_time
    with _lock:
        if not is_alive():
            return jsonify({"ok": False, "message": "Nessuna cattura in corso"})
        _proc.send_signal(signal.SIGTERM)
        try:
            _proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _proc.kill()
        _proc = None
        _start_time = None
        size = 0
        try:
            size = os.path.getsize(PCAP_FILE)
        except FileNotFoundError:
            pass
        return jsonify({"ok": True, "message": "Cattura fermata — {:,} byte salvati".format(size)})


@app.route("/download")
def download():
    if not os.path.exists(PCAP_FILE):
        return Response("Nessun file disponibile", status=404)
    return send_file(
        PCAP_FILE,
        as_attachment=True,
        download_name="capture.pcap",
        mimetype="application/vnd.tcpdump.pcap",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)
