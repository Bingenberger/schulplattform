"""Build the locked Next standalone runtime without importing private assets/data."""
import json
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/"docs/implementation/evidence"
for stage,tag in [("runtime","grundschultafel:0.1.0-dev"),("tests","grundschultafel-tests:0.1.0-dev")]:
    command=["docker","build","--platform","linux/amd64","--memory","2048m","--target",stage,"-t",tag,"."]
    with (out/("grundschultafel-build-"+stage+".log")).open("w") as log:
        log.write("$ "+" ".join(command)+"\n");log.flush()
        result=subprocess.run(command,cwd=ROOT/".work/apps/grundschultafel",stdout=log,stderr=subprocess.STDOUT,timeout=1200)
        log.write(f"\nexit_code={result.returncode}\n")
    if result.returncode:raise SystemExit("Next standalone build failed; see stage log")
image=json.loads(subprocess.check_output(["docker","image","inspect","grundschultafel:0.1.0-dev"],text=True))[0]
report={key:image[key] for key in ["Id","Architecture","Os","Size","RepoDigests"]}
runtime=json.loads(subprocess.check_output(["docker","run","--rm","--network","none","--read-only","grundschultafel:0.1.0-dev",
    "node","-e","console.log(JSON.stringify({node:process.version,next:require('next/package.json').version}))"],text=True))
report["runtime"]=runtime
(out/"grundschultafel-image.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report))
