"""Replay the exported Leseflux patch from its audited base and compare trees."""
import hashlib,json,secrets,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
row=next(item for item in json.loads((root/"patches/index.json").read_text()) if item["app"]=="leseflux")
target=root/".work"/("leseflux-replay-"+secrets.token_hex(5))
source=root/".work/apps/leseflux"
def git(*args,cwd=None):
 return subprocess.check_output(["git",*args],cwd=cwd or root,text=True,stderr=subprocess.PIPE).strip()
git("clone","--quiet","--no-hardlinks","--no-checkout",str(source),str(target))
git("checkout","--quiet","--detach",row["baseCommit"],cwd=target)
git("-c","user.name=Local Patch Verification","-c","user.email=verification@example.invalid",
 "am","--quiet",str(root/row["patch"]),cwd=target)
actual=git("rev-parse","HEAD^{tree}",cwd=target);expected=git("rev-parse","HEAD^{tree}",cwd=source)
assert actual==expected and not git("status","--porcelain",cwd=target)
report={"app":"leseflux","baseCommit":row["baseCommit"],"implementationCommit":row["implementationCommit"],
 "patchSha256":hashlib.sha256((root/row["patch"]).read_bytes()).hexdigest(),"replayedTree":actual,
 "treeMatches":True,"cleanReplay":True}
(root/"docs/implementation/evidence/leseflux-patch-replay.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report))
