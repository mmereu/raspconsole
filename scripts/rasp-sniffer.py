#!/usr/bin/env python3
"""RasP-Sniffer — Wireshark-style live packet capture web interface.
Porta 9090. Streaming SSE in tempo reale, righe colorate per protocollo."""

import json
import os
import queue
import signal
import subprocess
import threading
import time
from flask import Flask, Response, jsonify, request, render_template_string, send_file

CAPTURE_DIR = "/var/log/rasp-sniffer"
PCAP_FILE = os.path.join(CAPTURE_DIR, "capture.pcap")
PORT = 9090
MAX_PKT = 10000

os.makedirs(CAPTURE_DIR, exist_ok=True)
app = Flask(__name__)
_lock = threading.Lock()
_proc = None
_start_time = None
_iface = None
_bpf = ""
_packets = []
_sse_queues = []


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


def parse_line(line):
    """Parse | separated tshark -T fields output."""
    parts = line.split("|", 6)
    if len(parts) < 7:
        return None
    try:
        return {
            "no":    int(parts[0]) if parts[0].strip().isdigit() else 0,
            "time":  parts[1].strip(),
            "src":   parts[2].strip(),
            "dst":   parts[3].strip(),
            "proto": parts[4].strip(),
            "len":   parts[5].strip(),
            "info":  parts[6].strip(),
        }
    except (ValueError, IndexError):
        return None


def broadcast(data):
    with _lock:
        dead = []
        for q in _sse_queues:
            try:
                q.put_nowait(data)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _sse_queues.remove(q)


def reader_thread(proc):
    global _packets
    for raw in proc.stdout:
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        pkt = parse_line(line)
        if not pkt:
            continue
        pkt_json = json.dumps(pkt)
        with _lock:
            _packets.append(pkt)
            if len(_packets) > MAX_PKT:
                _packets.pop(0)
        broadcast(pkt_json)


HTML = r"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<title>RasP-Sniffer</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Courier New',monospace;background:#1e1e2e;color:#cdd6f4;display:flex;flex-direction:column;height:100vh;overflow:hidden}
#toolbar{background:#181825;padding:7px 10px;display:flex;align-items:center;gap:6px;border-bottom:2px solid #313244;flex-shrink:0;flex-wrap:wrap}
#toolbar h1{font-size:14px;color:#89b4fa;margin-right:4px;font-family:sans-serif}
#filter-bar{background:#11111b;padding:5px 10px;display:flex;align-items:center;gap:6px;border-bottom:1px solid #313244;flex-shrink:0}
#filter-bar label{font-size:11px;color:#6c7086}
#bpf{background:#313244;color:#cdd6f4;border:1px solid #45475a;border-radius:3px;padding:3px 8px;font-size:12px;font-family:monospace;width:340px}
#bpf.invalid{border-color:#f38ba8}
select{background:#313244;color:#cdd6f4;border:1px solid #45475a;border-radius:3px;padding:3px 8px;font-size:12px}
button{padding:4px 12px;border:none;border-radius:3px;font-size:12px;font-weight:700;cursor:pointer;font-family:sans-serif}
button:hover:not(:disabled){filter:brightness(1.15)}
button:disabled{opacity:.35;cursor:not-allowed}
#btn-start{background:#a6e3a1;color:#1e1e2e}
#btn-stop{background:#f38ba8;color:#1e1e2e}
#btn-clear{background:#45475a;color:#cdd6f4}
#btn-dl{background:#89b4fa;color:#1e1e2e}
.sep{color:#45475a;font-size:16px}
#stats{margin-left:auto;font-size:11px;color:#6c7086;font-family:sans-serif;white-space:nowrap}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#f38ba8;margin-right:5px;vertical-align:middle}
.dot.on{background:#a6e3a1;animation:blink .9s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.25}}
#wrap{flex:1;overflow:auto}
table{width:100%;border-collapse:collapse;font-size:11.5px}
thead th{background:#181825;color:#89b4fa;padding:4px 8px;text-align:left;border-right:1px solid #1e1e2e;border-bottom:2px solid #313244;position:sticky;top:0;z-index:10;font-family:sans-serif;font-size:11px;text-transform:uppercase;letter-spacing:.5px;white-space:nowrap;cursor:pointer;user-select:none}
thead th:hover{background:#313244}
td{padding:2px 8px;border-bottom:1px solid #11111b;white-space:nowrap;overflow:hidden;max-width:320px;text-overflow:ellipsis}
.no{width:52px;color:#6c7086}
.time{width:110px;color:#a6adc8}
.src{width:160px}
.dst{width:160px}
.proto{width:68px;font-weight:700}
.len{width:46px;text-align:right;color:#a6adc8}
.info{color:#cdd6f4}
/* Protocol row colors — Wireshark-inspired dark */
tr.TCP    {background:#182036}
tr.UDP    {background:#182a1e}
tr.DNS    {background:#2a2a10}
tr.HTTP   {background:#122a12}
tr.HTTPS,tr.TLS,tr.SSL{background:#12122a}
tr.ARP    {background:#22102a}
tr.ICMP   {background:#2a1212}
tr.DHCP   {background:#2a1e10}
tr.STP    {background:#102222}
tr.LLDP   {background:#101e2a}
tr.OTHER  {background:#1e1e2e}
tbody tr:hover{filter:brightness(1.6);cursor:default}
tbody tr.sel{outline:1px solid #89b4fa;filter:brightness(1.8)}
#autoscroll{accent-color:#89b4fa}
</style>
</head>
<body>
<div id="toolbar">
  <h1>&#x1F4E1; RasP-Sniffer</h1>
  <span class="sep">|</span>
  <label style="font-size:11px;color:#6c7086;font-family:sans-serif">Interfaccia</label>
  <select id="iface"></select>
  <button id="btn-start" onclick="startCapture()">&#9654; Avvia</button>
  <button id="btn-stop"  onclick="stopCapture()" disabled>&#9632; Ferma</button>
  <span class="sep">|</span>
  <button id="btn-clear" onclick="clearTable()">&#10006; Pulisci</button>
  <button id="btn-dl" onclick="location.href='/download'" disabled>&#11015; Scarica .pcap</button>
  <div id="stats">
    <span class="dot" id="dot"></span>
    <span id="stat-pkt">0 pacchetti</span>
    &nbsp;|&nbsp;
    <span id="stat-size">—</span>
    &nbsp;|&nbsp;
    <span id="stat-dur">—</span>
  </div>
</div>
<div id="filter-bar">
  <label for="bpf">Filtro BPF:</label>
  <input type="text" id="bpf" placeholder="tcp port 80 &#160;|&#160; icmp &#160;|&#160; host 10.0.0.1 &#160;|&#160; not arp">
  <label style="font-size:11px;color:#6c7086;margin-left:10px">
    <input type="checkbox" id="autoscroll" checked> Auto-scroll
  </label>
</div>
<div id="wrap">
  <table id="pkt-table">
    <thead>
      <tr>
        <th class="no">No.</th>
        <th class="time">Tempo</th>
        <th class="src">Origine</th>
        <th class="dst">Destinazione</th>
        <th class="proto">Protocollo</th>
        <th class="len">Lung.</th>
        <th class="info">Info</th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>
</div>

<script>
var pktCount = 0;
var es = null;
var autoscroll = true;

document.getElementById('autoscroll').addEventListener('change', function(e) {
  autoscroll = e.target.checked;
});

function protoClass(p) {
  var map = {
    'TCP':'TCP','UDP':'UDP','DNS':'DNS','HTTP':'HTTP','HTTPS':'HTTPS',
    'TLS':'TLS','SSL':'SSL','ARP':'ARP','ICMP':'ICMP','ICMPv6':'ICMP',
    'DHCP':'DHCP','DHCPv6':'DHCP','STP':'STP','LLDP':'LLDP',
    'IGMP':'OTHER','MDNS':'DNS','LLMNR':'DNS','NTP':'OTHER'
  };
  return map[p] || 'OTHER';
}

function addRow(pkt) {
  pktCount++;
  var tb = document.getElementById('tbody');
  var tr = document.createElement('tr');
  tr.className = protoClass(pkt.proto);
  tr.innerHTML =
    '<td class="no">'   + escHtml(String(pkt.no))    + '</td>' +
    '<td class="time">' + escHtml(pkt.time)           + '</td>' +
    '<td class="src">'  + escHtml(pkt.src)            + '</td>' +
    '<td class="dst">'  + escHtml(pkt.dst)            + '</td>' +
    '<td class="proto">'+ escHtml(pkt.proto)          + '</td>' +
    '<td class="len">'  + escHtml(pkt.len)            + '</td>' +
    '<td class="info">' + escHtml(pkt.info)           + '</td>';
  tr.onclick = function() {
    var prev = document.querySelector('tr.sel');
    if (prev) prev.classList.remove('sel');
    tr.classList.add('sel');
  };
  tb.appendChild(tr);
  if (autoscroll) {
    var wrap = document.getElementById('wrap');
    wrap.scrollTop = wrap.scrollHeight;
  }
  document.getElementById('stat-pkt').textContent = pktCount + ' pacchetti';
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function fmtBytes(b) {
  if (!b) return '—';
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b/1024).toFixed(1) + ' KB';
  return (b/1048576).toFixed(2) + ' MB';
}

function fmtDur(s) {
  if (!s) return '—';
  var h=Math.floor(s/3600),m=Math.floor(s%3600/60),sec=s%60;
  return (h?h+'h ':'')+(m?m+'m ':'')+sec+'s';
}

function loadIfaces() {
  fetch('/interfaces').then(function(r){return r.json();}).then(function(list){
    var sel = document.getElementById('iface');
    sel.innerHTML = '';
    list.forEach(function(i){ sel.add(new Option(i,i)); });
  });
}

function updateStatus() {
  fetch('/status').then(function(r){return r.json();}).then(function(s){
    var on = s.capturing;
    var dot = document.getElementById('dot');
    dot.className = 'dot' + (on ? ' on' : '');
    document.getElementById('stat-size').textContent = fmtBytes(s.file_size);
    document.getElementById('stat-dur').textContent  = on ? fmtDur(s.duration) : '—';
    document.getElementById('btn-start').disabled = on;
    document.getElementById('btn-stop').disabled  = !on;
    document.getElementById('btn-dl').disabled    = !s.file_exists;
  });
}

function startCapture() {
  var iface = document.getElementById('iface').value;
  var bpf   = document.getElementById('bpf').value.trim();
  clearTable();
  fetch('/start', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({iface: iface, filter: bpf})
  }).then(function(r){return r.json();}).then(function(d){
    if (d.ok) {
      connectSSE();
      updateStatus();
    } else {
      alert(d.message);
    }
  });
}

function stopCapture() {
  fetch('/stop',{method:'POST'}).then(function(r){return r.json();}).then(function(){
    if (es) { es.close(); es = null; }
    updateStatus();
  });
}

function clearTable() {
  document.getElementById('tbody').innerHTML = '';
  pktCount = 0;
  document.getElementById('stat-pkt').textContent = '0 pacchetti';
}

function connectSSE() {
  if (es) es.close();
  es = new EventSource('/stream');
  es.onmessage = function(e) {
    try { addRow(JSON.parse(e.data)); } catch(err) {}
  };
  es.onerror = function() {
    es.close(); es = null;
  };
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


@app.route("/stream")
def stream():
    """SSE endpoint — invia un evento JSON per ogni pacchetto catturato."""
    q = queue.Queue(maxsize=2000)
    with _lock:
        _sse_queues.append(q)

    def generate():
        try:
            while True:
                try:
                    data = q.get(timeout=15)
                    yield "data: {}\n\n".format(data)
                except queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            with _lock:
                if q in _sse_queues:
                    _sse_queues.remove(q)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/start", methods=["POST"])
def start():
    global _proc, _start_time, _iface, _bpf, _packets
    data = request.get_json(force=True) or {}
    iface = data.get("iface", "eth0")
    bpf   = data.get("filter", "").strip()
    with _lock:
        if is_alive():
            return jsonify({"ok": False, "message": "Cattura gia in corso"})
        try:
            os.remove(PCAP_FILE)
        except FileNotFoundError:
            pass
        _packets = []

    cmd = [
        "tshark", "-i", iface, "-l", "-n",
        "-w", PCAP_FILE,
        "-T", "fields",
        "-e", "frame.number",
        "-e", "frame.time_relative",
        "-e", "_ws.col.Source",
        "-e", "_ws.col.Destination",
        "-e", "_ws.col.Protocol",
        "-e", "frame.len",
        "-e", "_ws.col.Info",
        "-E", "separator=|",
        "-E", "header=n",
        "-E", "quote=n",
    ]
    if bpf:
        cmd += ["-f", bpf]

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True,
                                bufsize=1)
        with _lock:
            _proc = proc
            _start_time = time.time()
            _iface = iface
            _bpf = bpf
        threading.Thread(target=reader_thread, args=(proc,), daemon=True).start()
        msg = "Cattura avviata su " + iface
        if bpf:
            msg += " | filtro: " + bpf
        return jsonify({"ok": True, "message": msg})
    except FileNotFoundError:
        return jsonify({"ok": False, "message": "tshark non trovato"})
    except PermissionError:
        return jsonify({"ok": False, "message": "Permesso negato — eseguire come root"})
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
    return jsonify({"ok": True, "message": "Cattura fermata — {:,} byte".format(size)})


@app.route("/download")
def download():
    if not os.path.exists(PCAP_FILE):
        return Response("Nessun file disponibile", status=404)
    return send_file(PCAP_FILE, as_attachment=True, download_name="capture.pcap",
                     mimetype="application/vnd.tcpdump.pcap")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)
