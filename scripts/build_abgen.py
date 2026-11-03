"""Build abgen independently, with frozen bases and no platform dependencies."""
import json, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/"docs/implementation/evidence"
reports={}
for target,tag in [("runtime","abgen:0.1.0-dev"),("pdf","abgen-pdf:0.1.0-dev"),("tests","abgen-tests:0.1.0-dev")]:
    command=["docker","build","--platform","linux/amd64","--target",target,"-t",tag,"."]
    with (out/("abgen-build-"+target+".log")).open("w") as log:
        log.write("$ "+" ".join(command)+"\n");log.flush()
        result=subprocess.run(command,cwd=ROOT/".work/apps/abgen",stdout=log,stderr=subprocess.STDOUT,timeout=900)
        log.write("\nexit_code="+str(result.returncode)+"\n")
    if result.returncode:raise SystemExit("Build failed; see stage log")
    raw=json.loads(subprocess.check_output(["docker","image","inspect",tag],text=True))[0]
    report={key:raw[key] for key in ["Id","Architecture","Os","Size","RepoDigests"]}
    report["node"]=subprocess.check_output(["docker","run","--rm","--read-only","--network","none",tag,"node","--version"],text=True).strip()
    reports[target]=report
(out/"abgen-images.json").write_text(json.dumps(reports,indent=2)+"\n")
print(json.dumps(reports))
