"""Run existing Kompetenz-Manager tests inside the pinned offline container."""
import subprocess,argparse
from pathlib import Path
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument("--contracts-only",action="store_true")
args=parser.parse_args()
selected=["contract_tests","tests/test_code_hygiene.py"] if args.contracts_only else ["tests","contract_tests"]
command=["docker","run","--rm","--init","--network","none","--read-only","--cap-drop","ALL",
 "--security-opt","no-new-privileges:true","--memory","1536m","--cpus","2","--pids-limit","256",
 "--tmpfs","/tmp:size=512m,mode=1777","--tmpfs","/app/instance:size=64m,uid=10001,gid=10001,mode=700",
 "--tmpfs","/app/static/uploads:size=32m,uid=10001,gid=10001,mode=700",
 "-e","SECRET_KEY=synthetic-offline-test-session-key-not-for-deployment",
 "kompetenz-manager-tests:0.1.0-dev","python","-m","pytest","-q","-p","no:cacheprovider",*selected]
image=subprocess.check_output(["docker","image","inspect","--format","{{.Id}}","kompetenz-manager-tests:0.1.0-dev"],text=True).strip()
result=subprocess.run(command,capture_output=True,text=True,timeout=900)
name="kompetenz-contracts.log" if args.contracts_only else "kompetenz-functional.log"
target=root/("docs/implementation/evidence/"+name if result.returncode==0 else ".work/kompetenz-functional-failure.private.log")
target.write_text("imageId="+image+"\n$ "+" ".join(command)+"\n"+result.stdout+result.stderr+"\nexit_code="+str(result.returncode)+"\n")
print(result.stdout[-2500:]);print("exit",result.returncode)
raise SystemExit(result.returncode)
