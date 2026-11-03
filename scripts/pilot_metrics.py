"""Read-only cgroup-v2 pilot measurements. No Docker environment or payload dumps."""
import json,os,platform,re,subprocess,time
from pathlib import Path,PurePosixPath

CGROUP=Path("/sys/fs/cgroup")
MEMORY_FIELDS=("MemTotal","MemAvailable","MemFree","SwapTotal","SwapFree","Cached","Buffers","SReclaimable","Shmem")
def pairs(text):
    result={}
    for line in text.splitlines():
        key,value=line.split()
        number=int(value)
        if number<0:raise ValueError("Negative kernel counter")
        result[key]=number
    return result
def meminfo(text):
    result={}
    for line in text.splitlines():
        key,rest=line.split(":",1)
        if key in MEMORY_FIELDS:
            parts=rest.split()
            if len(parts)!=2 or parts[1]!="kB":raise ValueError("Unknown meminfo unit")
            result[key+"Bytes"]=int(parts[0])*1024
    return result
def pressure(text):
    return {line.split()[0]:{key:float(value) if key!="total" else int(value)
            for key,value in (item.split("=") for item in line.split()[1:])}
            for line in text.splitlines()}
def cgroup_path(text,root=CGROUP):
    entries=[line[3:] for line in text.splitlines() if line.startswith("0::")]
    if len(entries)!=1:raise ValueError("Unified cgroup v2 required")
    relative=PurePosixPath(entries[0])
    if not relative.is_absolute() or ".." in relative.parts:raise ValueError("Invalid cgroup path")
    path=(root.joinpath(*relative.parts[1:])).resolve()
    if not path.is_relative_to(root.resolve()):raise ValueError("Cgroup path escaped controller root")
    return path
def io_counters(text):
    result={}
    for line in text.splitlines():
        parts=line.split();result[parts[0]]={key:int(value) for key,value in (part.split("=") for part in parts[1:])}
    return result
def delta(before,after,key):
    value=after[key]-before[key]
    if value<0:raise ValueError("Kernel counter reset; series is not comparable")
    return value
def cpu_delta(before,after,seconds):
    if seconds<=0:raise ValueError("Positive elapsed time required")
    result={"cores":delta(before,after,"usage_usec")/1e6/seconds}
    for key in ("nr_periods","nr_throttled","throttled_usec"):
        if key in before and key in after:result[key]=delta(before,after,key)
    return result
def host_cpu(text):
    values=[int(value) for value in text.splitlines()[0].split()[1:9]]
    return dict(zip(("user","nice","system","idle","iowait","irq","softirq","steal"),values))
def host_cpu_delta(before,after):
    values={key:delta(before,after,key) for key in before};total=sum(values.values())
    if total<=0:return None
    return {"busyPercent":100*(total-values["idle"]-values["iowait"])/total,
            "iowaitPercent":100*values["iowait"]/total,"stealPercent":100*values["steal"]/total}
def cgroup_sample(path):
    memory=pairs((path/"memory.stat").read_text())
    current=int((path/"memory.current").read_text())
    sample={"monotonicNs":time.monotonic_ns(),"memoryCurrentBytes":current,
      "memoryAnonBytes":memory.get("anon"),"memoryFileBytes":memory.get("file"),
      "memoryInactiveFileBytes":memory.get("inactive_file"),
      "workingSetApproxBytes":max(0,current-memory.get("inactive_file",0)),
      "memoryEvents":pairs((path/"memory.events").read_text()),
      "cpu":pairs((path/"cpu.stat").read_text()),"pids":int((path/"pids.current").read_text()),
      "io":io_counters((path/"io.stat").read_text())}
    peak=path/"memory.peak"
    sample["memoryLifetimePeakBytes"]=int(peak.read_text()) if peak.exists() else None
    return sample
def totals(services):
    # Separate views of the same cgroup charges; NEVER add anon, file and current.
    fields=("memoryCurrentBytes","memoryAnonBytes","memoryFileBytes","workingSetApproxBytes")
    result={field:sum(s[field] for s in services.values()) if all(s[field] is not None for s in services.values()) else None for field in fields}
    cpus=[s.get("cpuDelta",{}).get("cores") for s in services.values()]
    result["cpuCores"]=sum(cpus) if all(value is not None for value in cpus) else None
    return result
def docker(*args):
    result=subprocess.run(["docker",*args],capture_output=True,text=True,timeout=15)
    if result.returncode:raise ValueError("Docker metric query failed; output withheld")
    return result.stdout
def inspect(ids):
    if not ids or any(not re.fullmatch("[a-f0-9]{64}",cid) for cid in ids):raise ValueError("Full container IDs required")
    raw=json.loads(docker("inspect",*ids))
    return {row["Id"]:{"pid":row["State"]["Pid"],"startedAt":row["State"]["StartedAt"],
       "running":row["State"]["Running"],"oomKilled":row["State"]["OOMKilled"],
       "restartCount":row["RestartCount"],"health":row["State"].get("Health",{}).get("Status","not-defined"),
       "image":row["Image"],"labels":{k:row["Config"].get("Labels",{}).get(k) for k in
         ("com.docker.compose.project","com.docker.compose.service")},
       "limits":{"memoryBytes":row["HostConfig"]["Memory"],"nanoCpus":row["HostConfig"]["NanoCpus"],
         "pids":row["HostConfig"]["PidsLimit"]}} for row in raw}
def identities_unchanged(before,after):
    if set(before)!=set(after):return False
    return all(after[cid]["running"] and all(before[cid][key]==after[cid][key]
       for key in ("pid","startedAt","image","restartCount")) for cid in before)
def host_sample():
    return {"memory":meminfo(Path("/proc/meminfo").read_text()),"cpu":host_cpu(Path("/proc/stat").read_text()),
        "pressure":{key:pressure(Path("/proc/pressure",key).read_text()) for key in ("cpu","memory","io")}}
def host_metadata():
    release={}
    for line in Path("/etc/os-release").read_text().splitlines():
        if "=" in line:
            key,value=line.split("=",1)
            if key in ("ID","VERSION_ID","PRETTY_NAME"):release[key]=value.strip('"')
    model=next((line.split(":",1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("model name")),"unknown")
    space=os.statvfs(Path.cwd())
    return {"os":release,"kernel":platform.release(),"architecture":platform.machine(),"cpuModel":model,
       "logicalCpus":os.cpu_count(),"processCpuAffinityCount":len(os.sched_getaffinity(0)),
       "workspaceFilesystem":{"bytes":space.f_blocks*space.f_frsize,"availableBytes":space.f_bavail*space.f_frsize},
       "memory":meminfo(Path("/proc/meminfo").read_text()),
       "docker":json.loads(docker("info","--format",'{"serverVersion":{{json .ServerVersion}},"cgroupVersion":{{json .CgroupVersion}},"cgroupDriver":{{json .CgroupDriver}}}'))}
PG={"schulwissen":("db","schulwissen"),"fahrradausbildung":("db","fahrrad"),
    "leseflux":("postgres","leseflux"),"abgen":("postgres","abgen")}
def database_probe(cid,role):
    sql="""SELECT json_build_object('otherConnections',count(*),'active',count(*) FILTER(WHERE state='active'),
     'idle',count(*) FILTER(WHERE state='idle'),'idleInTransaction',count(*) FILTER(WHERE state='idle in transaction'),
     'lockWaits',count(*) FILTER(WHERE wait_event_type='Lock'))
     FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()"""
    return json.loads(docker("exec",cid,"psql","-X","-At","--no-password","-v","ON_ERROR_STOP=1","-U",role,"-d",role,"-c",sql))
def work_probe(services):
    sources={
      "losverkauf/app":("python","import sqlite3,json; c=sqlite3.connect('file:/data/losverkauf.db?mode=ro',uri=True,timeout=1);print(json.dumps(dict(c.execute('SELECT status,count(*) FROM mail_outbox GROUP BY status').fetchall())));c.close()"),
      "kompetenz-manager/worker":("python","import sqlite3,json;c=sqlite3.connect('file:/app/instance/schule.db?mode=ro',uri=True,timeout=1);print(json.dumps({'unmailedNotificationRows':c.execute('SELECT count(*) FROM notification WHERE mailed_at IS NULL').fetchone()[0]}));c.close()"),
      "abgen/pdf":("node","fetch('http://127.0.0.1:3001/health').then(r=>r.json()).then(x=>console.log(JSON.stringify({active:x.active,rendererWarm:x.ready}))).catch(()=>process.exit(1))")}
    result={}
    for name,(binary,program) in sources.items():
        try:result[name]=json.loads(docker("exec",services[name]["id"],binary,"-e" if binary=="node" else "-c",program))
        except (ValueError,KeyError):result[name]={"unavailable":True}
    return result
def summarize(samples):
    if len(samples)<2:raise ValueError("At least two samples required")
    services={}
    for name in samples[0]["services"]:
        values=[row["services"][name] for row in samples]
        cpus=[value["cpuDelta"]["cores"] for value in values if "cpuDelta" in value]
        first,last=values[0],values[-1]
        services[name]={"memoryCurrentMinBytes":min(v["memoryCurrentBytes"] for v in values),
          "memoryCurrentMaxBytes":max(v["memoryCurrentBytes"] for v in values),
          "memoryAnonMaxBytes":max(v["memoryAnonBytes"] for v in values),
          "workingSetApproxMaxBytes":max(v["workingSetApproxBytes"] for v in values),
          "cpuMeanCores":sum(cpus)/len(cpus),"cpuMaxCores":max(cpus),
          "oomEventsDelta":delta(first["memoryEvents"],last["memoryEvents"],"oom"),
          "oomKillsDelta":delta(first["memoryEvents"],last["memoryEvents"],"oom_kill"),
          "restartCountDelta":last["state"]["restartCount"]-first["state"]["restartCount"],
          "ioBytesDelta":{key:sum(item.get(key,0) for item in last["io"].values())-sum(item.get(key,0) for item in first["io"].values()) for key in ("rbytes","wbytes")},
          "throttledUsecDelta":last["cpu"].get("throttled_usec",0)-first["cpu"].get("throttled_usec",0)}
    aggregate={"memoryCurrentMaxBytes":max(row["totals"]["memoryCurrentBytes"] for row in samples),
       "memoryAnonMaxBytes":max(row["totals"]["memoryAnonBytes"] for row in samples),
       "workingSetApproxMaxBytes":max(row["totals"]["workingSetApproxBytes"] for row in samples),
       "cpuMeanCores":sum(row["totals"]["cpuCores"] for row in samples[1:])/(len(samples)-1),
       "cpuMaxCores":max(row["totals"]["cpuCores"] for row in samples[1:]),
       "oomKillsDelta":sum(s["oomKillsDelta"] for s in services.values()),
       "restartCountDelta":sum(s["restartCountDelta"] for s in services.values())}
    return {"services":services,"aggregate":aggregate,"sampleCount":len(samples),
       "observedSeconds":samples[-1]["elapsedSeconds"]-samples[0]["elapsedSeconds"]}


def workload_summary(samples):
    def values(name,field,default):
        points=[row["workloads"][name] for row in samples]
        if any(point.get("unavailable") for point in points):return None
        return [point.get(field,default) for point in points]
    pdf=values("abgen/pdf","active",False)
    pending=values("losverkauf/app","pending",0)
    unmailed=values("kompetenz-manager/worker","unmailedNotificationRows",0)
    return {"abgenPdfActiveSamples":sum(bool(value) for value in pdf) if pdf is not None else None,
      "losverkaufPendingMax":max(pending) if pending is not None else None,
      "kompetenzUnmailedMax":max(unmailed) if unmailed is not None else None}
