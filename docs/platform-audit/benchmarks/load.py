#!/usr/bin/env python3
"""Closed-loop local HTTP benchmark, raw JSONL, no cookies/tokens in output."""
import argparse,concurrent.futures,json,os,random,socket,time,urllib.request,urllib.error,urllib.parse,ipaddress,math,threading
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('plan',type=Path);p.add_argument('--users',type=int,default=10);p.add_argument('--seconds',type=float,default=1200);p.add_argument('--warmup',type=float,default=300);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
if not 1<=a.users<=250 or not 0<a.seconds<=7200 or a.warmup<0:p.error('users 1..250, seconds 0..7200, warmup >=0')
plan=json.loads(a.plan.read_text());origins=plan['origins']
for origin in origins.values():
 u=urllib.parse.urlsplit(origin)
 if u.scheme not in ('http','https') or u.username or u.password or u.path not in ('','/'):p.error('plain HTTP(S) origins required')
 # Explicit local namespace only; hostname+address checked before starting.
 if u.hostname not in ('localhost','127.0.0.1','::1') and not u.hostname.endswith('.test'):p.error('only loopback or isolated .test origins allowed')
 for entry in socket.getaddrinfo(u.hostname,u.port or (443 if u.scheme=='https' else 80)):
  ip=ipaddress.ip_address(entry[4][0])
  if not (ip.is_loopback or ip.is_private):p.error('target resolves to public address')
for action in plan['actions']:
 if not action['path'].startswith('/') or action['path'].startswith('//') or '?' in action['path']:p.error('paths must be local, without query secrets')
 if action['method'] not in ('GET','POST','PUT','DELETE'):p.error('unsupported method')
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
lock=threading.Lock();a.output.parent.mkdir(parents=True,exist_ok=True)
start=time.monotonic();stop=start+a.warmup+a.seconds
with a.output.open('w') as out:
 def user(i):
  rng=random.Random(i);opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect());time.sleep(rng.uniform(0,min(1,a.seconds)))
  while time.monotonic()<stop:
   action=rng.choices(plan['actions'],weights=[x['weight'] for x in plan['actions']])[0]
   headers={'Content-Type':'application/json'}
   # Cookie/header values stay in environment; never serialize them.
   for k,envname in action.get('header_env',{}).items():headers[k]=os.environ[envname]
   data=json.dumps(action['body']).encode() if 'body' in action else None
   request=urllib.request.Request(origins[action['app']]+action['path'],data=data,headers=headers,method=action['method'])
   t=time.monotonic();status=0;size=0
   try:
    with opener.open(request,timeout=10) as response:status=response.status;size=len(response.read())
   except urllib.error.HTTPError as e:status=e.code;size=len(e.read())
   except (OSError,TimeoutError):pass
   row={'elapsed_s':round(t-start,4),'user':i,'action':action['name'],'latency_ms':round((time.monotonic()-t)*1000,3),'status':status,'bytes':size,'technical_error':status not in action.get('expected',[200]),'warmup':t-start<a.warmup}
   with lock:out.write(json.dumps(row)+'\n');out.flush()
   time.sleep(rng.uniform(*plan.get('think_seconds',[4,8])))
 with concurrent.futures.ThreadPoolExecutor(max_workers=a.users) as executor:list(executor.map(user,range(a.users)))
rows=[json.loads(x) for x in a.output.read_text().splitlines()];rows=[x for x in rows if not x['warmup']]
def percentile(xs,q):return sorted(xs)[max(0,math.ceil(len(xs)*q)-1)] if xs else None
summary={'users':a.users,'measurement_seconds':a.seconds,'warmup_seconds':a.warmup,'count':len(rows),'rps':len(rows)/a.seconds,'error_rate':sum(x['technical_error'] for x in rows)/len(rows) if rows else None,'response_bytes':sum(x['bytes'] for x in rows),'latency_ms':{str(q):percentile([r['latency_ms'] for r in rows],q) for q in [.5,.95,.99]},'actions':{n:{'count':sum(r['action']==n for r in rows),'p95_ms':percentile([r['latency_ms'] for r in rows if r['action']==n],.95)} for n in {r['action'] for r in rows}}}
a.output.with_suffix('.summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
