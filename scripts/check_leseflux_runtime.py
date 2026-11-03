"""Existing pure business suite in locked Node container without network."""
from pathlib import Path
import subprocess
root=Path(__file__).resolve().parents[1]
command=["docker","run","--rm","--init","--network","none","--read-only","--cap-drop","ALL",
 "--security-opt","no-new-privileges:true","--memory","768m","--cpus","2","--pids-limit","192",
 "--tmpfs","/tmp:size=128m,mode=1777","leseflux-tests:0.1.0-dev",
 "npm","run","test","-w","apps/api","--","--maxWorkers=2","--minWorkers=1","--no-cache"]
result=subprocess.run(command,capture_output=True,text=True,timeout=300)
(root/"docs/implementation/evidence/leseflux-functional.log").write_text("$ "+" ".join(command)+"\n"+result.stdout+result.stderr+"\nexit_code="+str(result.returncode)+"\n")
print(result.stdout[-3500:]);print(result.stderr[-1000:]);raise SystemExit(result.returncode)
