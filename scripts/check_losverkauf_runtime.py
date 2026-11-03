"""Run isolated application runtime/security tests without network."""
from pathlib import Path
import subprocess
ROOT = Path(__file__).resolve().parents[1]
command=["docker","run","--rm","--read-only","--network","none","--cap-drop","ALL",
         "--security-opt","no-new-privileges:true","--memory","512m","--cpus","1","--pids-limit","128",
         "--tmpfs","/tmp:size=128m,mode=1777","losverkauf-tests:0.1.0-dev","python","-m","pytest","-q","-p","no:cacheprovider","tests"]
result=subprocess.run(command,capture_output=True,text=True,timeout=180)
(ROOT/"docs/implementation/evidence/losverkauf-runtime.log").write_text(
    "$ "+" ".join(command)+"\n"+result.stdout+result.stderr+f"\nexit_code={result.returncode}\n")
print(result.stdout[-4000:])
if result.returncode:
    raise SystemExit("App runtime checks failed")
