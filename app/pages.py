"""Server-rendered HTML for the three pages. No external CDNs — everything is
inline so the app has no third-party dependencies at runtime and works behind a
plain ALB with no egress."""

_STYLE = """
:root{--bg:#0e1116;--card:#1a1f29;--fg:#e6edf3;--muted:#8b949e;--accent:#2f81f7;
--good:#3fb950;--bad:#f85149;--warn:#d29922}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
background:var(--bg);color:var(--fg)}
.wrap{max-width:1100px;margin:0 auto;padding:20px}
h1{font-size:20px;margin:0 0 4px}.sub{color:var(--muted);font-size:13px;margin-bottom:20px}
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.card{background:var(--card);border:1px solid #262c36;border-radius:10px;padding:16px}
.tile .n{font-size:30px;font-weight:700}.tile .l{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.two{display:grid;gap:14px;grid-template-columns:1fr 1fr;margin-top:14px}
@media(max-width:760px){.two{grid-template-columns:1fr}}
.feed{height:280px;overflow:auto;font-family:ui-monospace,Menlo,monospace;font-size:12px}
.row{padding:3px 0;border-bottom:1px solid #21262d;display:flex;gap:8px;justify-content:space-between}
.pod{color:var(--accent)}.err{color:var(--bad)}.lt{color:var(--warn)}
.bar{height:10px;background:#21262d;border-radius:5px;overflow:hidden;margin-top:4px}
.bar>span{display:block;height:100%;background:var(--accent)}
.qr{background:#fff;padding:12px;border-radius:10px;display:inline-block}
a{color:var(--accent)}
button{font-size:15px;border:0;border-radius:8px;padding:12px 16px;cursor:pointer}
input{background:#0e1116;color:var(--fg);border:1px solid #30363d;border-radius:6px;padding:8px;width:100%}
label{font-size:12px;color:var(--muted);display:block;margin:10px 0 3px}
.big{width:100%;padding:26px;font-size:22px;font-weight:700;background:var(--accent);color:#fff}
.stop{background:var(--bad);color:#fff}.ghost{background:#21262d;color:var(--fg)}
.pill{display:inline-block;padding:2px 8px;border-radius:20px;font-size:12px}
"""


def dashboard(qr_svg: str, mobile_url: str) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ping — live dashboard</title><style>{_STYLE}</style></head><body><div class="wrap">
<h1>Ping · live traffic dashboard</h1>
<div class="sub">Scan to join. Every tap generates a real request, a structured log line, and load for the HPA to react to.</div>
<div class="two">
  <div class="card" style="text-align:center">
    <div class="qr">{qr_svg}</div>
    <div style="margin-top:10px"><a href="{mobile_url}">{mobile_url}</a></div>
  </div>
  <div>
    <div class="grid">
      <div class="card tile"><div class="n" id="total">0</div><div class="l">Total pings</div></div>
      <div class="card tile"><div class="n" id="pps">0</div><div class="l">Pings / sec</div></div>
      <div class="card tile"><div class="n" id="sessions">0</div><div class="l">Active phones</div></div>
      <div class="card tile"><div class="n" id="p50">0</div><div class="l">p50 ms</div></div>
      <div class="card tile"><div class="n" id="p95">0</div><div class="l">p95 ms</div></div>
      <div class="card tile"><div class="n err" id="errors">0</div><div class="l">Errors</div></div>
    </div>
    <div class="card" style="margin-top:14px">
      <div class="l">Requests per pod</div><div id="pods"></div>
    </div>
  </div>
</div>
<div class="card" style="margin-top:14px">
  <div class="l">Live feed — request &rarr; pod that served it</div>
  <div class="feed" id="feed"></div>
</div>
<div class="sub" style="margin-top:14px">This dashboard is served by pod <span class="pod" id="me">?</span> · <a href="/admin">admin load test</a></div>
</div>
<script>
const $=id=>document.getElementById(id);
function fmtPods(pods){{
  const entries=Object.entries(pods).sort((a,b)=>b[1]-a[1]);
  const max=Math.max(1,...entries.map(e=>e[1]));
  $('pods').innerHTML=entries.map(([p,c])=>
    `<div style="margin-top:8px"><div class="row"><span class="pod">${{p}}</span><span>${{c}}</span></div>`+
    `<div class="bar"><span style="width:${{Math.round(100*c/max)}}%"></span></div></div>`).join('')||'<div class="sub">no traffic yet</div>';
}}
function onStats(s){{
  $('total').textContent=s.total;$('pps').textContent=s.pings_per_second;
  $('sessions').textContent=s.active_sessions;$('p50').textContent=s.p50_ms;
  $('p95').textContent=s.p95_ms;$('errors').textContent=s.errors;$('me').textContent=s.serving_pod;
  fmtPods(s.pods||{{}});
}}
function onPing(e){{
  const feed=$('feed');const d=document.createElement('div');d.className='row';
  const cls=e.status>=400?'err':(e.source==='loadtest'?'lt':'pod');
  const t=new Date(e.ts*1000).toLocaleTimeString();
  d.innerHTML=`<span>#${{e.seq}} · ${{t}} · ${{e.source}}</span>`+
    `<span class="${{cls}}">${{e.pod}} · ${{e.latency_ms}}ms · ${{e.status}}</span>`;
  feed.prepend(d);while(feed.childNodes.length>120)feed.removeChild(feed.lastChild);
}}
const es=new EventSource('/events');
es.addEventListener('stats',ev=>onStats(JSON.parse(ev.data)));
es.addEventListener('ping',ev=>onPing(JSON.parse(ev.data)));
</script></body></html>"""


def mobile() -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Send Ping</title><style>{_STYLE}
.wrap{{max-width:420px;padding-top:40px;text-align:center}}
</style></head><body><div class="wrap">
<h1>Send a Ping</h1>
<div class="sub">Each tap hits the backend and shows which pod answered.</div>
<button class="big" id="btn">Send Ping</button>
<div class="grid" style="margin-top:20px">
  <div class="card tile"><div class="n" id="mine">0</div><div class="l">Your pings</div></div>
  <div class="card tile"><div class="n" id="lat">–</div><div class="l">Last latency ms</div></div>
</div>
<div class="card" style="margin-top:14px">
  <div class="l">Answered by pod</div><div class="pod" id="pod" style="font-family:ui-monospace,monospace">–</div>
</div>
</div>
<script>
const $=id=>document.getElementById(id);
const sid=(crypto.randomUUID?crypto.randomUUID():String(Math.random()));
let mine=0,busy=false;
async function ping(){{
  if(busy)return;busy=true;$('btn').disabled=true;
  try{{
    const r=await fetch('/ping?session='+sid,{{method:'POST'}});
    const j=await r.json();mine++;
    $('mine').textContent=mine;$('lat').textContent=j.latency_ms;$('pod').textContent=j.pod;
  }}catch(e){{$('pod').textContent='error';}}
  busy=false;$('btn').disabled=false;
}}
$('btn').addEventListener('click',ping);
// heartbeat so the phone stays counted as an active session
setInterval(()=>fetch('/heartbeat?session='+sid,{{method:'POST'}}).catch(()=>{{}}),10000);
</script></body></html>"""


def admin() -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Admin — controlled load test</title><style>{_STYLE}.wrap{{max-width:640px}}</style></head><body><div class="wrap">
<h1>Controlled load test</h1>
<div class="sub">Admin only. Generates traffic <b>against this app only</b>, within hard caps, with automatic and emergency stop. Not a stress tool for anything external.</div>
<div class="card">
  <label>Admin token</label><input id="token" type="password" placeholder="bearer token">
  <div class="two">
    <div><label>Rate (req/s) · max <span id="mr">?</span></label><input id="rate" type="number" value="10" min="1"></div>
    <div><label>Concurrency · max <span id="mc">?</span></label><input id="conc" type="number" value="5" min="1"></div>
  </div>
  <label>Duration (s) · max <span id="md">?</span></label><input id="dur" type="number" value="30" min="1">
  <div class="two" style="margin-top:16px">
    <button class="big" id="start">Start</button>
    <button class="ghost" id="stop">Graceful stop</button>
  </div>
  <button class="big stop" id="estop" style="margin-top:12px">EMERGENCY STOP</button>
</div>
<div class="card" style="margin-top:14px">
  <div class="l">Status</div><pre id="status" style="white-space:pre-wrap;margin:6px 0 0">idle</pre>
</div>
<div class="sub" style="margin-top:10px"><a href="/">back to dashboard</a></div>
</div>
<script>
const $=id=>document.getElementById(id);
const hdr=()=>({{'Authorization':'Bearer '+$('token').value,'Content-Type':'application/json'}});
async function call(path,body){{
  const r=await fetch(path,{{method:'POST',headers:hdr(),body:body?JSON.stringify(body):null}});
  const t=await r.text();let j;try{{j=JSON.parse(t)}}catch(e){{j={{error:t}}}}
  render(j,r.ok);return j;
}}
function render(j,ok){{
  $('status').textContent=JSON.stringify(j,null,2);
  $('status').style.color=ok?'':'var(--bad)';
  if(j.max_rate){{$('mr').textContent=j.max_rate;$('mc').textContent=j.max_concurrency;$('md').textContent=j.max_duration_seconds;}}
}}
$('start').onclick=()=>call('/admin/loadtest/start',{{rate:+$('rate').value,concurrency:+$('conc').value,duration:+$('dur').value}});
$('stop').onclick=()=>call('/admin/loadtest/stop');
$('estop').onclick=()=>call('/admin/loadtest/emergency-stop');
async function poll(){{
  try{{const r=await fetch('/admin/loadtest/status');render(await r.json(),true);}}catch(e){{}}
}}
poll();setInterval(poll,1500);
</script></body></html>"""
