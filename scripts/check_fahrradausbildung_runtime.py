"""Real PG fixture only; existing functional tests may create/drop its dedicated test DB."""
import argparse,json,os,secrets,subprocess,time
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument("--browser",action="store_true");parser.add_argument("--browser-filter",default="test_posten_frontend or test_posten_offline or im_browser or kartenstil_ohne_bilder or hoher_zoom_bleibt or qr_codes_im_pdf");args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[1];out=ROOT/"docs/implementation/evidence"
project="sp-fahrrad-tests-"+secrets.token_hex(5)
private=ROOT/".work"/project;private.mkdir(mode=0o700)
password=secrets.token_hex(32)
secret=private/"db-admin";secret.write_text(password);secret.chmod(0o444)
envfile=private/"test-env"
envfile.write_text("FP_TEST_DATABASE_URL=postgresql+psycopg://postgres:"+password+"@db:5432/fahrrad_test\n")
envfile.chmod(0o600)
def run(cmd,**kwargs):return subprocess.run(cmd,capture_output=True,text=True,timeout=900,**kwargs)
PG="postgres:16-alpine@sha256:0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab"
network=project;db=project+"-db"
try:
    subprocess.run(["docker","network","create",*([] if args.browser else ["--internal"]),network],check=True,capture_output=True)
    subprocess.run(["docker","run","-d","--name",db,"--network",network,"--network-alias","db","--memory","512m","--cpus","1","--pids-limit","128",
        "-e","POSTGRES_PASSWORD_FILE=/run/secrets/db-admin","-v",str(secret)+":/run/secrets/db-admin:ro",PG],check=True,capture_output=True)
    for _ in range(100):
        result=run(["docker","exec",db,"pg_isready","-h","127.0.0.1","-U","postgres"])
        if result.returncode==0:break
        time.sleep(.2)
    else:raise RuntimeError("Test DB not ready")
    command=["docker","run","--rm","--init","--network",network,"--read-only","--cap-drop","ALL","--security-opt","no-new-privileges:true",
        "--memory",("1536m" if args.browser else "1024m"),"--cpus","2","--pids-limit",("512" if args.browser else "192"),"--tmpfs","/tmp:size=256m,mode=1777",
        "--env-file",str(envfile),("fahrradausbildung-browser-tests:0.1.0-dev" if args.browser else "fahrradausbildung-tests:0.1.0-dev"),
        "python","-m","pytest","-q","-p","no:cacheprovider","tests","contract_tests",
        ]
    if args.browser:command+=["-k",args.browser_filter]
    if not args.browser:command+=["--ignore=tests/test_posten_frontend.py","--ignore=tests/test_posten_offline.py","-k","not im_browser and not kartenstil_ohne_bilder and not hoher_zoom_bleibt"]
    logfile=out/("fahrrad-browser-functional.log" if args.browser else "fahrrad-functional.log")
    if args.browser:
        collected=run(command+["--collect-only"])
        assert collected.returncode==0
        nodes=[line.strip() for line in collected.stdout.splitlines() if line.startswith("tests/") and "::" in line]
        assert nodes
        prefix=command[:command.index("tests")]
        failed=False
        with logfile.open("w") as log:
            log.write("$ "+" ".join(command+["--collect-only"])+"\n"+collected.stdout+"\n")
            for offset in range(0,len(nodes),4):
                batch=prefix+nodes[offset:offset+4]
                result=run(batch)
                log.write("$ "+" ".join(batch)+"\n"+result.stdout+result.stderr+"\nexit_code="+str(result.returncode)+"\n")
                log.flush()
                print("Browser batch",offset//4+1,"exit",result.returncode,flush=True)
                if result.returncode:
                    failed=True
                    break
        if failed:raise SystemExit("Browser batch failed; see retained fixture evidence")
        print("PASS",len(nodes),"browser/QR contracts in isolated batches",flush=True)
    else:
        result=run(command)
        logfile.write_text("$ "+" ".join(command)+"\n"+result.stdout+result.stderr+"\nexit_code="+str(result.returncode)+"\n")
        print(result.stdout[-5000:]);print("exit",result.returncode)
        if result.returncode:raise SystemExit(1)
finally:
    run(["docker","stop",db])
