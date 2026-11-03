"""Bounded local amd64 build from existing uv.lock; never publish."""
import argparse,json,subprocess
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument("--browser",action="store_true");args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[1];out=ROOT/"docs/implementation/evidence"
for stage in (("runtime","tests","browser-tests") if args.browser else ("runtime","tests")):
    tag="fahrradausbildung"+("-"+stage if stage!="runtime" else "")+":0.1.0-dev"
    cmd=["docker","build","--platform","linux/amd64","--memory","1536m","--target",stage,"-t",tag,"."]
    with (out/("fahrrad-build-"+stage+".log")).open("w") as log:
        log.write("$ "+" ".join(cmd)+"\n");log.flush()
        result=subprocess.run(cmd,cwd=ROOT/".work/apps/fahrradausbildung",stdout=log,stderr=subprocess.STDOUT,timeout=1200)
        log.write("\nexit_code="+str(result.returncode)+"\n")
    if result.returncode:raise SystemExit("Fahrrad build failed; see stage log")
image=json.loads(subprocess.check_output(["docker","image","inspect","fahrradausbildung:0.1.0-dev"],text=True))[0]
metadata={key:image[key] for key in ("Id","Size","Architecture","Os","RepoDigests")}
metadata["runtime"]=json.loads(subprocess.check_output(["docker","run","--rm","--network","none","--read-only",
    "fahrradausbildung:0.1.0-dev","python","-c",
    "import json,sys,importlib.metadata as m;print(json.dumps({'python':sys.version.split()[0],**{p:m.version(p) for p in ['fastapi','uvicorn','sqlalchemy','psycopg','weasyprint']}}))"],text=True))
(out/"fahrrad-image.json").write_text(json.dumps(metadata,indent=2)+"\n")
print(json.dumps(metadata))
