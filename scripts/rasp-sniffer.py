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


def get_own_ip():
    try:
        out = subprocess.check_output(["hostname", "-I"], text=True, timeout=3)
        return out.strip().split()[0]
    except Exception:
        return ""


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
/* Pannello analisi */
#analyze-panel{display:none;position:fixed;top:0;right:0;width:440px;height:100vh;background:#181825;border-left:2px solid #313244;z-index:100;overflow-y:auto;padding:16px;box-shadow:-4px 0 20px #000a}
#analyze-panel h2{font-size:13px;color:#cba6f7;font-family:sans-serif;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center}
#analyze-panel h3{font-size:11px;color:#6c7086;text-transform:uppercase;letter-spacing:.8px;margin:14px 0 6px;font-family:sans-serif}
.finding{background:#1e1e2e;border-radius:6px;padding:10px 12px;margin-bottom:8px;border-left:3px solid #45475a}
.finding.red{border-color:#f38ba8}
.finding.orange{border-color:#fab387}
.finding.info{border-color:#89b4fa}
.finding.green{border-color:#a6e3a1}
.finding-title{font-size:12px;font-weight:700;margin-bottom:4px;color:#cdd6f4}
.finding-action{font-size:11px;color:#a6adc8;line-height:1.5}
.proto-bar{display:flex;align-items:center;gap:8px;margin-bottom:5px;font-size:11px}
.proto-bar-fill{height:10px;border-radius:3px;background:#cba6f7;min-width:2px;transition:width .3s}
.host-row{display:flex;justify-content:space-between;font-size:11px;padding:3px 0;border-bottom:1px solid #1e1e2e;color:#cdd6f4}
.host-row span{color:#6c7086}
#close-analyze{background:none;border:none;color:#6c7086;font-size:18px;cursor:pointer;padding:0}
#close-analyze:hover{color:#cdd6f4}
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
  <button id="btn-analyze" onclick="runAnalyze()" style="background:#cba6f7;color:#1e1e2e" disabled>&#128270; Analizza</button>
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

<div id="analyze-panel">
  <h2>&#128270; Analisi traffico <button id="close-analyze" onclick="closeAnalyze()">&#10005;</button></h2>
  <div id="analyze-content">Premi Analizza per elaborare i pacchetti catturati.</div>
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
    document.getElementById('btn-start').disabled   = on;
    document.getElementById('btn-stop').disabled    = !on;
    document.getElementById('btn-dl').disabled      = !s.file_exists;
    document.getElementById('btn-analyze').disabled = (pktCount === 0);
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

function runAnalyze() {
  document.getElementById('analyze-panel').style.display = 'block';
  document.getElementById('analyze-content').innerHTML = '<p style="color:#6c7086;font-size:12px">Elaborazione in corso...</p>';
  fetch('/analyze').then(function(r){return r.json();}).then(function(d){
    if (d.total === 0) {
      document.getElementById('analyze-content').innerHTML = '<p style="color:#6c7086;font-size:12px">Nessun pacchetto da analizzare. Avvia prima una cattura.</p>';
      return;
    }
    var html = '<p style="font-size:11px;color:#6c7086;margin-bottom:12px">Analizzati <b style="color:#cdd6f4">' + d.total + '</b> pacchetti</p>';

    // Findings
    html += '<h3>Rilevazioni e consigli</h3>';
    d.findings.forEach(function(f) {
      html += '<div class="finding ' + f.level + '">' +
        '<div class="finding-title">' + f.icon + ' ' + escHtml(f.title) + '</div>' +
        '<div class="finding-action">' + escHtml(f.action) + '</div></div>';
    });

    // Top protocolli
    var maxP = d.top_protos.length ? d.top_protos[0][1] : 1;
    html += '<h3>Protocolli pi&#249; frequenti</h3>';
    d.top_protos.forEach(function(p) {
      var pct = Math.round(p[1] / maxP * 100);
      html += '<div class="proto-bar">' +
        '<div style="width:80px;overflow:hidden;text-overflow:ellipsis">' + escHtml(p[0]) + '</div>' +
        '<div class="proto-bar-fill" style="width:' + pct + 'px"></div>' +
        '<span style="color:#6c7086">' + p[1] + '</span></div>';
    });

    // Top sorgenti
    html += '<h3>Host pi&#249; attivi (origine)</h3>';
    d.top_src.forEach(function(h) {
      html += '<div class="host-row"><span style="font-family:monospace">' + escHtml(h[0]) + '</span><span>' + h[1] + ' pkt</span></div>';
    });

    // Top destinazioni
    html += '<h3>Host pi&#249; contattati (destinazione)</h3>';
    d.top_dst.forEach(function(h) {
      html += '<div class="host-row"><span style="font-family:monospace">' + escHtml(h[0]) + '</span><span>' + h[1] + ' pkt</span></div>';
    });

    document.getElementById('analyze-content').innerHTML = html;
  }).catch(function(e) {
    document.getElementById('analyze-content').innerHTML = '<p style="color:#f38ba8;font-size:12px">Errore: ' + e + '</p>';
  });
}

function closeAnalyze() {
  document.getElementById('analyze-panel').style.display = 'none';
}

function loadDefaultFilter() {
  fetch('/myip').then(function(r) { return r.json(); }).then(function(d) {
    if (d.ip) {
      var f = document.getElementById('bpf');
      if (!f.value) f.value = 'not host ' + d.ip;
    }
  }).catch(function() {});
}
loadIfaces();
loadDefaultFilter();
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


@app.route("/myip")
def myip():
    return jsonify({"ip": get_own_ip()})


@app.route("/analyze")
def analyze():
    with _lock:
        pkts = list(_packets)

    if not pkts:
        return jsonify({"total": 0, "findings": [], "top_protos": [], "top_src": [], "top_dst": []})

    proto_counts = {}
    src_counts = {}
    dst_counts = {}
    info_all = []

    for p in pkts:
        proto = p.get("proto", "") or "OTHER"
        src   = p.get("src", "")
        dst   = p.get("dst", "")
        info  = p.get("info", "").lower()

        proto_counts[proto] = proto_counts.get(proto, 0) + 1
        if src:
            src_counts[src] = src_counts.get(src, 0) + 1
        if dst:
            dst_counts[dst] = dst_counts.get(dst, 0) + 1
        info_all.append(info)

    top_protos = sorted(proto_counts.items(), key=lambda x: x[1], reverse=True)[:8]
    top_src    = sorted(src_counts.items(),   key=lambda x: x[1], reverse=True)[:5]
    top_dst    = sorted(dst_counts.items(),   key=lambda x: x[1], reverse=True)[:5]

    findings = []

    # --- Sicurezza ---
    if proto_counts.get("HTTP", 0) > 0:
        findings.append({"level": "red", "icon": "🔴",
            "title": "HTTP non cifrato ({} pacchetti)".format(proto_counts["HTTP"]),
            "action": "Migra i servizi web a HTTPS (porta 443). I dati HTTP sono leggibili da chiunque sulla rete."})

    telnet_pkts = proto_counts.get("TELNET", 0) + sum(1 for i in info_all if "telnet" in i)
    if telnet_pkts > 0:
        findings.append({"level": "red", "icon": "🔴",
            "title": "Telnet rilevato — credenziali in chiaro",
            "action": "Sostituisci Telnet con SSH. Telnet trasmette username e password leggibili."})

    ftp_pkts = proto_counts.get("FTP", 0) + proto_counts.get("FTP-DATA", 0)
    if ftp_pkts > 0:
        findings.append({"level": "orange", "icon": "🟠",
            "title": "FTP rilevato ({} pacchetti)".format(ftp_pkts),
            "action": "Usa SFTP o FTPS al posto di FTP. Le credenziali FTP viaggiano in chiaro."})

    snmp_pkts = proto_counts.get("SNMP", 0)
    if snmp_pkts > 0:
        findings.append({"level": "orange", "icon": "🟠",
            "title": "SNMP rilevato ({} pacchetti)".format(snmp_pkts),
            "action": "Verifica che sia usato SNMPv3 con autenticazione. SNMPv1/v2c usano community string in chiaro."})

    # Possibile port scan: un singolo src verso molti dst diversi
    for src, count in src_counts.items():
        dst_from_src = sum(1 for p in pkts if p.get("src") == src and p.get("dst"))
        unique_dst = len(set(p.get("dst") for p in pkts if p.get("src") == src and p.get("dst")))
        if unique_dst > 20 and count > 50:
            findings.append({"level": "orange", "icon": "🟠",
                "title": "Possibile port/network scan da {}".format(src),
                "action": "L'host {} ha contattato {} destinazioni distinte. Verifica se è attività legittima.".format(src, unique_dst)})
            break

    # --- Suggerimenti di rete ---
    dns_pkts = proto_counts.get("DNS", 0) + proto_counts.get("MDNS", 0)
    if dns_pkts > 0:
        findings.append({"level": "info", "icon": "🔵",
            "title": "DNS: {} query rilevate".format(dns_pkts),
            "action": "Il traffico DNS è normale. Se vuoi filtrarlo: aggiungi 'and not port 53' al filtro BPF."})

    arp_pkts = proto_counts.get("ARP", 0)
    if arp_pkts > 30:
        findings.append({"level": "orange", "icon": "🟠",
            "title": "ARP elevato: {} pacchetti".format(arp_pkts),
            "action": "Molti pacchetti ARP possono indicare un ARP scan o conflitti IP. Verifica la rete."})
    elif arp_pkts > 0:
        findings.append({"level": "info", "icon": "🔵",
            "title": "ARP: {} pacchetti (normale)".format(arp_pkts),
            "action": "Traffico ARP nella norma. Per nasconderlo al prossimo avvio: aggiungi 'and not arp' al filtro BPF."})

    if not findings:
        findings.append({"level": "green", "icon": "🟢",
            "title": "Nessuna anomalia rilevata",
            "action": "Il traffico analizzato non mostra protocolli insicuri o comportamenti anomali."})

    return jsonify({
        "total":      len(pkts),
        "top_protos": top_protos,
        "top_src":    top_src,
        "top_dst":    top_dst,
        "findings":   findings,
    })


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

    # Escludi automaticamente il traffico del Raspberry stesso
    own_ip = get_own_ip()
    exclude = "not host {}".format(own_ip) if own_ip else ""
    if exclude:
        effective_bpf = "({}) and {}".format(bpf, exclude) if bpf else exclude
    else:
        effective_bpf = bpf

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
    if effective_bpf:
        cmd += ["-f", effective_bpf]

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True,
                                bufsize=1)
        with _lock:
            _proc = proc
            _start_time = time.time()
            _iface = iface
            _bpf = effective_bpf
        threading.Thread(target=reader_thread, args=(proc,), daemon=True).start()
        msg = "Cattura avviata su " + iface
        if effective_bpf:
            msg += " | filtro: " + effective_bpf
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
