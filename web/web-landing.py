#!/etc/ConsolePi/venv/bin/python
"""RasP-Console Web Dashboard - OceanX Style"""
import http.server
import socketserver
import subprocess
import json
import os

PORT = 8888

HTML = r"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RasP-Console — Serial Console Server</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #000d15;
  --surface: rgba(0,38,62,0.4);
  --surface-hover: rgba(0,38,62,0.6);
  --cyan: #90e0ef;
  --ocean: #0077b6;
  --teal: #1de9b6;
  --purple: #b388ff;
  --pink: #ff80ab;
  --red: #ff3b30;
  --green: #00d084;
  --glow: rgba(144,224,239,0.25);
  --text1: rgba(255,255,255,0.95);
  --text2: rgba(255,255,255,0.55);
  --text3: rgba(255,255,255,0.30);
  --border: rgba(144,224,239,0.12);
  --border-hover: rgba(144,224,239,0.35);
  --radius: 14px;
  --fast: 0.2s ease;
  --smooth: 0.4s cubic-bezier(.4,0,.2,1);
}
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
html{font-size:16px;scroll-behavior:smooth}
body{font-family:'DM Sans',sans-serif;color:var(--text1);background:var(--bg);min-height:100vh;overflow-x:hidden}

/* Orbs */
.orbs{position:fixed;inset:0;z-index:-1;pointer-events:none;overflow:hidden}
.orb{position:absolute;border-radius:50%;backdrop-filter:blur(6px);border:1px solid rgba(255,255,255,0.05)}
.orb-1{width:280px;height:280px;top:5%;left:-4%;background:radial-gradient(circle at 30% 30%,rgba(144,224,239,0.07),transparent 70%);animation:float1 22s ease-in-out infinite}
.orb-2{width:180px;height:180px;top:50%;right:-2%;background:radial-gradient(circle at 40% 40%,rgba(29,233,182,0.06),transparent 70%);animation:float2 28s ease-in-out infinite}
.orb-3{width:130px;height:130px;top:25%;left:40%;background:radial-gradient(circle at 50% 50%,rgba(179,136,255,0.05),transparent 70%);animation:float3 18s ease-in-out infinite}
@keyframes float1{0%,100%{transform:translate(0,0) scale(1)}50%{transform:translate(50px,40px) scale(1.05)}}
@keyframes float2{0%,100%{transform:translate(0,0)}50%{transform:translate(-40px,-50px) scale(1.06)}}
@keyframes float3{0%,100%{transform:translate(0,0)}33%{transform:translate(35px,-25px)}66%{transform:translate(-20px,40px)}}

/* Navbar */
.navbar{position:sticky;top:0;z-index:100;padding:0.8rem 2rem;display:flex;align-items:center;justify-content:space-between;background:rgba(0,13,21,0.7);backdrop-filter:blur(20px);border-bottom:1px solid var(--border)}
.navbar::after{content:'';position:absolute;bottom:-1px;left:0;width:100%;height:1px;background:linear-gradient(90deg,transparent,var(--cyan),transparent);animation:borderGlow 4s ease-in-out infinite}
@keyframes borderGlow{0%,100%{opacity:0.3}50%{opacity:1}}
.nav-brand{display:flex;align-items:center;gap:0.8rem;text-decoration:none;color:var(--text1)}
.nav-ico{width:42px;height:42px;border-radius:10px;display:flex;align-items:center;justify-content:center;background:rgba(144,224,239,0.08);border:1px solid var(--border);box-shadow:0 0 16px var(--glow)}
.nav-ico svg{width:24px;height:24px;stroke:var(--cyan);fill:none;stroke-width:1.75}
.nav-title{font-family:'Outfit',sans-serif;font-weight:700;font-size:1.1rem;letter-spacing:-0.02em}
.nav-title span{font-weight:300;color:var(--text2)}
.nav-right{display:flex;align-items:center;gap:1rem}
.clock{font-family:'JetBrains Mono',monospace;font-size:0.8rem;color:var(--cyan);padding:0.4rem 0.8rem;background:rgba(144,224,239,0.06);border:1px solid var(--border);border-radius:8px}
.status-pill{display:inline-flex;align-items:center;gap:0.4rem;padding:0.3rem 0.8rem;border-radius:100px;font-size:0.72rem;font-weight:600;letter-spacing:0.05em;text-transform:uppercase}
.status-online{color:var(--teal);background:rgba(29,233,182,0.1);border:1px solid rgba(29,233,182,0.25)}
.status-offline{color:var(--red);background:rgba(255,59,48,0.1);border:1px solid rgba(255,59,48,0.25)}
.status-dot{width:6px;height:6px;border-radius:50%;animation:pulse 2s ease-in-out infinite}
.status-online .status-dot{background:var(--teal)}
.status-offline .status-dot{background:var(--red)}
@keyframes pulse{0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(29,233,182,0.4)}50%{opacity:0.7;box-shadow:0 0 0 6px rgba(29,233,182,0)}}

.main{max-width:1000px;margin:0 auto;padding:2rem 1.5rem}

/* Hero */
.hero{text-align:center;padding:2rem 0 2.5rem}
.hero-badge{display:inline-flex;align-items:center;gap:0.5rem;padding:0.3rem 1rem;border-radius:100px;font-size:0.72rem;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:var(--cyan);background:rgba(144,224,239,0.08);border:1px solid rgba(144,224,239,0.2);margin-bottom:1rem}
.hero h1{font-family:'Outfit',sans-serif;font-size:clamp(1.8rem,4vw,2.6rem);font-weight:800;letter-spacing:-0.03em;line-height:1.1;margin-bottom:0.6rem}
.hero-accent{background:linear-gradient(135deg,var(--cyan),var(--teal),var(--purple));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.hero p{font-size:0.95rem;color:var(--text2);max-width:480px;margin:0 auto;line-height:1.6}

/* Stats */
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:2.5rem}
.stat{padding:1.2rem 1rem;border-radius:var(--radius);text-align:center;background:var(--surface);backdrop-filter:blur(16px);border:1px solid var(--border);transition:all var(--smooth);position:relative;overflow:hidden}
.stat::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,var(--cyan),transparent);opacity:0;transition:opacity var(--smooth)}
.stat:hover{transform:translateY(-4px);background:var(--surface-hover);border-color:var(--border-hover);box-shadow:0 12px 40px rgba(0,0,0,0.3),0 0 30px var(--glow)}
.stat:hover::before{opacity:1}
.stat-icon{margin-bottom:0.3rem;display:flex;justify-content:center}
.stat-icon svg{width:24px;height:24px;stroke:var(--cyan);stroke-width:1.75;fill:none}
.stat-num{font-family:'Outfit',sans-serif;font-size:1.6rem;font-weight:700;letter-spacing:-0.03em;background:linear-gradient(135deg,#fff,var(--cyan));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;line-height:1.2}
.stat-label{font-size:0.7rem;font-weight:500;color:var(--text2);text-transform:uppercase;letter-spacing:0.06em;margin-top:0.15rem}

/* Section heading */
.sh{display:flex;align-items:center;gap:1rem;margin-bottom:1.2rem}
.sh-text{font-family:'Outfit',sans-serif;font-size:0.8rem;font-weight:600;text-transform:uppercase;letter-spacing:0.1em;color:var(--text2);white-space:nowrap}
.sh-line{flex:1;height:1px;background:linear-gradient(90deg,var(--border),transparent)}

/* Device card */
.devices-grid{display:grid;gap:1rem;margin-bottom:2.5rem}
.device-card{border-radius:var(--radius);background:var(--surface);backdrop-filter:blur(16px);border:1px solid var(--border);padding:1.5rem;transition:all var(--smooth);display:flex;align-items:center;justify-content:space-between;gap:1.5rem}
.device-card:hover{background:var(--surface-hover);border-color:var(--border-hover);box-shadow:0 12px 40px rgba(0,0,0,0.3),0 0 20px var(--glow)}
.device-left{display:flex;align-items:center;gap:1.2rem}
.device-ico{width:52px;height:52px;border-radius:12px;display:flex;align-items:center;justify-content:center;background:rgba(29,233,182,0.12);border:1px solid rgba(29,233,182,0.2);flex-shrink:0}
.device-ico svg{width:26px;height:26px;stroke:var(--teal);fill:none;stroke-width:1.75}
.device-ico.disconnected{background:rgba(255,59,48,0.1);border-color:rgba(255,59,48,0.2)}
.device-ico.disconnected svg{stroke:var(--red)}
.device-info h3{font-family:'Outfit',sans-serif;font-size:1rem;font-weight:600;margin-bottom:0.25rem}
.device-meta{display:flex;gap:0.8rem;flex-wrap:wrap}
.device-meta span{font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:var(--text2)}
.no-device{text-align:center;padding:2.5rem;color:var(--text2);font-size:0.9rem}
.no-device svg{width:48px;height:48px;stroke:var(--text3);fill:none;stroke-width:1.5;margin-bottom:0.8rem}
.btn{display:inline-flex;align-items:center;gap:0.5rem;padding:0.6rem 1.4rem;border-radius:10px;text-decoration:none;font-weight:600;font-size:0.85rem;transition:all var(--fast);border:none;cursor:pointer}
.btn-primary{background:linear-gradient(135deg,rgba(29,233,182,0.2),rgba(29,233,182,0.1));color:var(--teal);border:1px solid rgba(29,233,182,0.3)}
.btn-primary:hover{background:linear-gradient(135deg,rgba(29,233,182,0.35),rgba(29,233,182,0.2));box-shadow:0 4px 20px rgba(29,233,182,0.2);transform:translateY(-2px)}
.btn-primary svg{width:16px;height:16px;stroke:currentColor;fill:none;stroke-width:2}

/* Services grid */
.services{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin-bottom:2.5rem}
.svc{border-radius:var(--radius);background:var(--surface);backdrop-filter:blur(16px);border:1px solid var(--border);padding:1.2rem;transition:all var(--smooth);text-decoration:none;color:var(--text1);display:block}
.svc:hover{transform:translateY(-4px);background:var(--surface-hover);border-color:var(--border-hover);box-shadow:0 12px 40px rgba(0,0,0,0.3),0 0 20px var(--glow)}
.svc-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:0.8rem}
.svc-ico{width:40px;height:40px;border-radius:10px;display:flex;align-items:center;justify-content:center}
.svc-ico svg{width:20px;height:20px;stroke-width:1.75;fill:none}
.svc-arrow{width:24px;height:24px;border-radius:50%;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);display:flex;align-items:center;justify-content:center;color:var(--text3);transition:all var(--fast)}
.svc:hover .svc-arrow{background:rgba(144,224,239,0.15);border-color:rgba(144,224,239,0.3);color:var(--cyan);transform:translate(2px,-2px)}
.svc-arrow svg{width:12px;height:12px;stroke:currentColor;fill:none;stroke-width:2}
.svc-title{font-family:'Outfit',sans-serif;font-size:0.9rem;font-weight:600;margin-bottom:0.3rem}
.svc-desc{font-size:0.78rem;color:var(--text2);line-height:1.4;margin-bottom:0.6rem}
.svc-badges{display:flex;gap:0.4rem}
.badge{display:inline-flex;align-items:center;padding:2px 8px;border-radius:100px;font-family:'JetBrains Mono',monospace;font-size:0.62rem;font-weight:600}
.b-port{background:rgba(144,224,239,0.1);color:var(--cyan);border:1px solid rgba(144,224,239,0.18)}
.b-proto{background:rgba(179,136,255,0.1);color:var(--purple);border:1px solid rgba(179,136,255,0.18)}
.b-active{background:rgba(29,233,182,0.1);color:var(--teal);border:1px solid rgba(29,233,182,0.18)}

/* Footer */
.footer{margin-top:1rem;padding:1rem 2rem;background:rgba(255,255,255,0.03);backdrop-filter:blur(20px);border-top:1px solid var(--border);display:flex;align-items:center;justify-content:space-between}
.footer-text{font-size:0.75rem;color:var(--text3)}
.footer-status{display:flex;align-items:center;gap:0.5rem;font-size:0.72rem;color:var(--text2)}
.footer-dot{width:7px;height:7px;border-radius:50%;background:var(--teal);box-shadow:0 0 8px rgba(29,233,182,0.5);animation:pulse 2s ease-in-out infinite}

@media(max-width:768px){
  .stats{grid-template-columns:repeat(2,1fr)}
  .services{grid-template-columns:1fr}
  .navbar{padding:0.8rem 1rem}
  .device-card{flex-direction:column;align-items:stretch}
  .footer{flex-direction:column;gap:0.5rem;text-align:center}
}
@media(max-width:480px){
  .stats{grid-template-columns:1fr 1fr}
  .hero h1{font-size:1.6rem}
}

::-webkit-scrollbar{width:8px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.12);border-radius:4px}
::-webkit-scrollbar-thumb:hover{background:rgba(255,255,255,0.22)}
::selection{background:rgba(144,224,239,0.25);color:#fff}
</style>
</head>
<body>

<div class="orbs"><div class="orb orb-1"></div><div class="orb orb-2"></div><div class="orb orb-3"></div></div>

<nav class="navbar">
  <a href="#" class="nav-brand">
    <div class="nav-ico"><svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg></div>
    <div class="nav-title">RasP <span>Console</span></div>
  </a>
  <div class="nav-right">
    <span class="status-pill status-online" id="status"><span class="status-dot"></span>Online</span>
    <span class="clock" id="clock">00:00:00</span>
  </div>
</nav>

<main class="main">

<section class="hero">
  <div class="hero-badge"><span class="status-dot" style="background:var(--teal)"></span>Serial Console Server</div>
  <h1>Console di Rete<br><span class="hero-accent">via Browser</span></h1>
  <p>Accesso diretto alla console seriale degli switch di rete tramite interfaccia web.</p>
</section>

<section class="stats">
  <div class="stat">
    <div class="stat-icon"><svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/></svg></div>
    <div class="stat-num" id="s-devices">0</div>
    <div class="stat-label">Devices</div>
  </div>
  <div class="stat">
    <div class="stat-icon"><svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg></div>
    <div class="stat-num" id="s-baud">--</div>
    <div class="stat-label">ttyd</div>
  </div>
  <div class="stat">
    <div class="stat-icon"><svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg></div>
    <div class="stat-num" id="s-uptime">--</div>
    <div class="stat-label">Uptime</div>
  </div>
  <div class="stat">
    <div class="stat-icon"><svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg></div>
    <div class="stat-num" id="s-ip">--</div>
    <div class="stat-label">IP Address</div>
  </div>
</section>

<div class="sh"><span class="sh-text">Serial Devices</span><div class="sh-line"></div></div>
<div class="devices-grid" id="devices">
  <div class="no-device">
    <svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M16 16v1a2 2 0 01-2 2H3a2 2 0 01-2-2V7a2 2 0 012-2h2m5.66 0H14a2 2 0 012 2v3.34l1 1L23 7v10"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
    Nessun cavo console USB collegato
  </div>
</div>

<div class="sh"><span class="sh-text">Servizi</span><div class="sh-line"></div></div>
<div class="services">
  <a class="svc" href="javascript:openConsole()">
    <div class="svc-head">
      <div class="svc-ico" style="background:rgba(29,233,182,0.12);border:1px solid rgba(29,233,182,0.2)"><svg viewBox="0 0 24 24" stroke="var(--teal)" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg></div>
      <div class="svc-arrow"><svg viewBox="0 0 24 24"><path d="M7 17L17 7"/><path d="M7 7h10v10"/></svg></div>
    </div>
    <div class="svc-title">Web Console</div>
    <div class="svc-desc">Terminale seriale via browser con ttyd e picocom</div>
    <div class="svc-badges"><span class="badge b-port">:8080</span><span class="badge b-proto">TTY</span></div>
  </a>
  <a class="svc" href="javascript:void(0)" onclick="window.open('http://'+location.hostname+':5000/api/docs','_blank')">
    <div class="svc-head">
      <div class="svc-ico" style="background:rgba(144,224,239,0.12);border:1px solid rgba(144,224,239,0.2)"><svg viewBox="0 0 24 24" stroke="var(--cyan)" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg></div>
      <div class="svc-arrow"><svg viewBox="0 0 24 24"><path d="M7 17L17 7"/><path d="M7 7h10v10"/></svg></div>
    </div>
    <div class="svc-title">ConsolePi API</div>
    <div class="svc-desc">REST API per discovery e gestione remota</div>
    <div class="svc-badges"><span class="badge b-port">:5000</span><span class="badge b-proto">REST</span></div>
  </a>
  <a class="svc" href="javascript:void(0)" onclick="window.open('ssh://raspconsole@'+location.hostname)">
    <div class="svc-head">
      <div class="svc-ico" style="background:rgba(179,136,255,0.12);border:1px solid rgba(179,136,255,0.2)"><svg viewBox="0 0 24 24" stroke="var(--purple)" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><circle cx="6" cy="6" r="1" fill="var(--purple)" stroke="none"/><circle cx="6" cy="18" r="1" fill="var(--purple)" stroke="none"/></svg></div>
      <div class="svc-arrow"><svg viewBox="0 0 24 24"><path d="M7 17L17 7"/><path d="M7 7h10v10"/></svg></div>
    </div>
    <div class="svc-title">SSH Admin</div>
    <div class="svc-desc">Accesso amministrativo al Raspberry Pi</div>
    <div class="svc-badges"><span class="badge b-port">:22</span><span class="badge b-proto">SSH</span></div>
  </a>
</div>

</main>

<footer class="footer">
  <span class="footer-text">ConsolePi + ttyd | RasP-Console</span>
  <span class="footer-status"><span class="footer-dot"></span>Tutti i servizi operativi</span>
</footer>

<script>
function updateClock(){const d=new Date();document.getElementById('clock').textContent=d.toLocaleTimeString('it-IT')}
setInterval(updateClock,1000);updateClock();

function openConsole(){window.open('http://'+location.hostname+':8080','_blank')}

async function refresh(){
  try{
    const r=await fetch('/status');const d=await r.json();
    const st=document.getElementById('status');
    st.className='status-pill status-online';
    st.innerHTML='<span class="status-dot"></span>Online';
    document.getElementById('s-devices').textContent=d.devices.length;
    document.getElementById('s-ip').textContent=d.system.IP;
    const up=d.system.Uptime.replace('up ','');
    document.getElementById('s-uptime').textContent=up;
    document.getElementById('s-baud').textContent=d.ttyd_running?'ONLINE':'OFFLINE';
    document.getElementById('s-baud').style.background=d.ttyd_running?'linear-gradient(135deg,#fff,var(--teal))':'linear-gradient(135deg,#fff,var(--red))';
    document.getElementById('s-baud').style.webkitBackgroundClip='text';
    const devs=document.getElementById('devices');
    if(d.devices.length>0){
      devs.innerHTML=d.devices.map(dev=>
        '<div class="device-card">'+
        '<div class="device-left">'+
        '<div class="device-ico"><svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M16 16v1a2 2 0 01-2 2H3a2 2 0 01-2-2V7a2 2 0 012-2h2m5.66 0H14a2 2 0 012 2v3.34"/><polygon points="23 7 16 12 23 17 23 7"/></svg></div>'+
        '<div class="device-info"><h3>'+(d.switch_hostname||dev.name)+'</h3>'+
        '<div class="device-meta"><span>'+dev.path+'</span><span>9600 8N1</span><span>FTDI</span><span>'+(d.ttyd_running?'ttyd ONLINE':'ttyd OFFLINE')+'</span></div></div></div>'+
        '<a href="javascript:openConsole()" class="btn btn-primary"><svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>Apri Console</a></div>'
      ).join('');
    }else{
      devs.innerHTML='<div class="no-device"><svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M16 16v1a2 2 0 01-2 2H3a2 2 0 01-2-2V7a2 2 0 012-2h2m5.66 0H14a2 2 0 012 2v3.34l1 1L23 7v10"/><line x1="1" y1="1" x2="23" y2="23"/></svg><br>Nessun cavo console USB collegato</div>';
    }
  }catch(e){
    document.getElementById('status').className='status-pill status-offline';
    document.getElementById('status').innerHTML='<span class="status-dot"></span>Offline';
  }
}
refresh();setInterval(refresh,5000);
</script>
</body>
</html>"""


def _cmd(args, default="unknown"):
    try:
        return subprocess.check_output(args, text=True, timeout=3).strip()
    except Exception:
        return default


def _get_status():
    devices = []
    try:
        for dev in sorted(os.listdir("/dev")):
            if dev.startswith("ttyUSB") or dev.startswith("ttyACM"):
                devices.append({"name": dev, "path": f"/dev/{dev}"})
    except Exception:
        pass
    ttyd_running = os.path.exists("/proc") and any(
        "ttyd" in (open(f"/proc/{p}/comm").read().strip() if os.path.isfile(f"/proc/{p}/comm") else "")
        for p in os.listdir("/proc") if p.isdigit()
    ) if os.path.exists("/proc") else False
    switch_hostname = ""
    try:
        with open("/tmp/switch-hostname.txt") as f:
            switch_hostname = f.read().strip()
    except Exception:
        pass
    ip = _cmd(["hostname", "-I"])
    if ip != "unknown":
        ip = ip.split()[0]
    return {
        "devices": devices,
        "system": {
            "Hostname": _cmd(["hostname"]),
            "IP": ip,
            "Uptime": _cmd(["uptime", "-p"]),
        },
        "ttyd_running": ttyd_running,
        "serial_connected": len(devices) > 0,
        "switch_hostname": switch_hostname,
    }


class Handler(http.server.SimpleHTTPRequestHandler):
    timeout = 10

    def do_GET(self):
        try:
            if self.path == "/" or self.path == "/index.html":
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(HTML.encode())
            elif self.path == "/status":
                data = _get_status()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            else:
                self.send_response(404)
                self.end_headers()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args):
        pass


class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with ThreadedServer(("", PORT), Handler) as httpd:
        print(f"Landing page on port {PORT}")
        httpd.serve_forever()
