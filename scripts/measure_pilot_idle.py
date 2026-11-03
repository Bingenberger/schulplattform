"""Measure the accepted ten-app pilot locally; never infer target-server capacity."""
import argparse,csv,json,secrets,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from schulplattform.pilot import Pilot,APP_SELECTIONS
from pilot_metrics import (docker,inspect,cgroup_path,cgroup_sample,cpu_delta,host_sample,
 host_cpu_delta,host_metadata,identities_unchanged,totals,summarize,PG,database_probe,work_probe,workload_summary)
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--state-dir",type=Path,default=ROOT/".work/pilot-v21")
parser.add_argument("--seconds",type=int,default=120)
parser.add_argument("--warmup",type=int,default=30)
parser.add_argument("--interval",type=int,default=5)
args=parser.parse_args()
if not 10<=args.seconds<=3600 or not 1<=args.interval<=60 or args.seconds<2*args.interval or not 0<=args.warmup<=300:
 parser.error("seconds 10..3600, interval 1..60, at least two intervals, warmup 0..300")
if not (args.state_dir/"state/installation.json").exists():parser.error("Accepted pilot installation required")
pilot=Pilot(args.state_dir)
if pilot.apps!=APP_SELECTIONS[-1]:parser.error("All ten selected apps are required")
stamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
directory=ROOT/"docs/messungen"/("local-idle-"+stamp+"-"+secrets.token_hex(3))
directory.mkdir()
services={};samples=[];success=False;started=False
def write(name,data): (directory/name).write_text(json.dumps(data,indent=2)+"\n")
try:
 started=True;pilot.start()
 print("All ten apps started; bounded idle warmup",flush=True)
 time.sleep(args.warmup)
 if not pilot.ready(None):raise ValueError("Pilot not ready after warmup")
 selection=[(app,"app") for app in pilot.apps]+[("kompetenz-manager","worker"),("abgen","pdf"),
   *[(app,service) for app,(service,role) in PG.items()],("infra","proxy"),("infra","mailpit")]
 for app,service in selection:
  item=pilot.inspect_service(app,service)
  if not item:raise ValueError("A selected service is missing")
  services[app+"/"+service]={"id":item["Id"],"project":pilot.project+"-"+app,"service":service}
 identities=inspect([item["id"] for item in services.values()])
 for name,service in services.items():
  row=identities[service["id"]]
  if not row["running"] or row["labels"]["com.docker.compose.project"]!=service["project"] or row["labels"]["com.docker.compose.service"]!=service["service"]:
   raise ValueError("Container identity/ownership contract failed")
  service["cgroup"]=str(cgroup_path(Path("/proc",str(row["pid"]),"cgroup").read_text()))
  service["image"]=row["image"];service["limits"]=row["limits"]
 metadata={"scope":"Local development-host idle observation; not target-server or capacity acceptance",
  "timestamp":stamp,"pilotProject":pilot.project,"installationId":json.loads((pilot.directory/"state/installation.json").read_text())["id"],
  "host":host_metadata(),"settings":{"warmupSeconds":args.warmup,"measurementSeconds":args.seconds,"intervalSeconds":args.interval},
  "services":services,"method":{"memory":"cgroup v2 memory.current, anon/file and current-inactive_file as separate views; never added together",
    "cpu":"cgroup usage_usec deltas / monotonic elapsed time; one core is 100%",
    "io":"cgroup block-I/O byte counters; host iowait/steal and PSI, not disk latency",
    "databases":"own database-role connection counts; collector backend excluded",
    "monitoringOverhead":"Docker exec for PG and queue/PDF probes every sample is included in container and host counters",
    "data":"Previously created synthetic pilot fixtures; no real school data",
    "pdf":"Fresh renderer process starts cold, no print job deliberately submitted",
    "cache":"No OS/page-cache flushing; caches affected by preceding local acceptance tests",
    "excludedServices":"Dashboard/deployment daemon and production relay are not part of this pilot runtime; host/desktop/foreign containers excluded from service totals",
    "missing":["HTTP latency/error rates","disk latency","ten-person load and 60-minute soak","import/PDF/mail/backup concurrency","separate load-generator host","queues outside two explicit native probes","queue age and SQL query latency"]}}
 write("metadata.json",metadata)
 start=time.monotonic();index=0
 with (directory/"samples.jsonl").open("w") as stream:
  while True:
   due=start+index*args.interval
   if index and due>start+args.seconds:break
   time.sleep(max(0,due-time.monotonic()))
   state=inspect([item["id"] for item in services.values()])
   if not identities_unchanged(identities,state):raise ValueError("Container stopped or restarted; series is incomplete")
   elapsed=time.monotonic()-start
   row={"timestamp":datetime.now(timezone.utc).isoformat(),"elapsedSeconds":elapsed,"services":{},"host":host_sample()}
   for name,service in services.items():
    point=cgroup_sample(Path(service["cgroup"]));point["state"]=state[service["id"]]
    point["state"]={key:point["state"][key] for key in ("running","oomKilled","restartCount","health","startedAt")}
    if samples:
     previous=samples[-1]["services"][name]
     point["cpuDelta"]=cpu_delta(previous["cpu"],point["cpu"],(point["monotonicNs"]-previous["monotonicNs"])/1e9)
    row["services"][name]=point
   row["totals"]=totals(row["services"])
   if samples:row["hostCpuDelta"]=host_cpu_delta(samples[-1]["host"]["cpu"],row["host"]["cpu"])
   row["postgres"]={}
   for app,(service,role) in PG.items():
    row["postgres"][app]=database_probe(services[app+"/"+service]["id"],role)
   row["workloads"]=work_probe(services)
   samples.append(row);stream.write(json.dumps(row)+"\n");stream.flush()
   if index%4==0:print("Collected idle sample "+str(index+1),flush=True)
   index+=1
 if not identities_unchanged(identities,inspect([s["id"] for s in services.values()])):
  raise ValueError("Container identity changed at end of observation")
 summary=summarize(samples)
 summary["complete"]=True;summary["scope"]=metadata["scope"]
 summary["allServicesHealthyOrWithoutHealthcheck"]=all(p["state"]["health"] in ("healthy","not-defined") for r in samples for p in r["services"].values())
 summary["oomKilledFlagObserved"]=any(p["state"]["oomKilled"] for r in samples for p in r["services"].values())
 summary["probeFailures"]=sum(1 for r in samples for p in r["workloads"].values() if p.get("unavailable"))
 summary["workloads"]=workload_summary(samples)
 summary["workloads"]["postgresOtherConnectionsMax"]={name:max(r["postgres"][name]["otherConnections"] for r in samples) for name in PG}
 summary["host"]={"minimumAvailableMemoryBytes":min(r["host"]["memory"]["MemAvailableBytes"] for r in samples),
  "maximumCpuIowaitPercent":max(r["hostCpuDelta"]["iowaitPercent"] for r in samples[1:]),
  "maximumCpuStealPercent":max(r["hostCpuDelta"]["stealPercent"] for r in samples[1:])}
 write("summary.json",summary)
 with (directory/"services.csv").open("w") as stream:
  fields=["service",*next(iter(summary["services"].values())).keys()]
  csvout=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n');csvout.writeheader()
  for name,data in summary["services"].items():csvout.writerow({"service":name,**{key:json.dumps(value,sort_keys=True) if isinstance(value,dict) else value for key,value in data.items()}})
 success=True
 print(json.dumps({"directory":str(directory.relative_to(ROOT)),"services":len(services),"samples":len(samples),"summary":summary["aggregate"]}),flush=True)
except BaseException:
 write("incomplete.json",{"complete":False,"samplesRecorded":len(samples),"reason":"Measurement failed or interrupted; no capacity verdict"})
 raise
finally:
 if started:pilot.stop()
 if (directory/"summary.json").exists():
  summary=json.loads((directory/"summary.json").read_text());summary["pilotStoppedDataRetained"]=True;write("summary.json",summary)
 if success:(ROOT/".work/latest-idle-measurement").write_text(str(directory))
