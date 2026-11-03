"""Local amd64 Leseflux build; never publish or seed accounts."""
import json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root/"docs/implementation/evidence"
for stage in ("runtime","tests"):
 command=["docker","build","--platform","linux/amd64","--memory","1536m","--target",stage,
  "-t","leseflux"+("-tests" if stage=="tests" else "")+":0.1.0-dev","."]
 with (out/("leseflux-build-"+stage+".log")).open("w") as log:
  log.write("$ "+" ".join(command)+"\n");log.flush()
  result=subprocess.run(command,cwd=root/".work/apps/leseflux",stdout=log,stderr=subprocess.STDOUT,timeout=1200)
  log.write("\nexit_code="+str(result.returncode)+"\n")
 if result.returncode:raise SystemExit("Leseflux build failed; inspect stage log")
info=json.loads(subprocess.check_output(["docker","image","inspect","leseflux:0.1.0-dev"],text=True))[0]
report={key:info[key] for key in ("Id","Size","Architecture","Os","RepoDigests")}
report["runtime"]=json.loads(subprocess.check_output(["docker","run","--rm","--read-only","--network","none","leseflux:0.1.0-dev",
 "node","-e","console.log(JSON.stringify({node:process.version,prisma:require('@prisma/client/package.json').version,fastify:require('fastify/package.json').version}))"],text=True))
(out/"leseflux-image.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report))
