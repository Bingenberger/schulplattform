#!/usr/bin/env python3
"""Disposable Ubuntu 24.04 KVM guests for installer acceptance (test harness only).

  vm.py create NAME [--ssh-port 2222]   fresh copy-on-write disk from the verified cloud image, boot
  vm.py ssh NAME -- CMD...              run a command as root in the guest
  vm.py push NAME SRC DST               copy a file or directory into the guest (tar over ssh)
  vm.py pull NAME SRC DST               copy a file out of the guest
  vm.py destroy NAME                    stop and delete the guest

The guest uses QEMU user networking: outbound internet like a server, guest
address 10.0.2.15, SSH forwarded to host loopback only. Nothing is published
beyond 127.0.0.1.
"""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / ".work/vm"
BASE = WORK / "dl/noble-server-cloudimg-amd64.img"
IMAGE = "sp-vm-qemu:1"
KEY = WORK / "id_ed25519"


def sh(argv, **kwargs):
    return subprocess.run(argv, check=True, text=True, **kwargs)


def ssh_argv(name, port):
    return ["ssh", "-i", str(KEY), "-p", str(port), "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=5", "-o", "ServerAliveInterval=15", "ubuntu@127.0.0.1"]


def meta(name):
    return json.loads((WORK / name / "vm.json").read_text())


def working_dns():
    """Host upstream resolvers that answer; QEMU user networking only uses the first one."""
    sys.path.insert(0, str(ROOT))
    from schulplattform.dnscheck import query
    servers = []
    for line in Path("/run/systemd/resolve/resolv.conf").read_text().splitlines():
        if line.startswith("nameserver "):
            server = line.split()[1]
            try:
                if query(server, "archive.ubuntu.com", "A", timeout=2):
                    servers.append(server)
            except OSError:
                pass
    return servers


def create(name, ssh_port, memory, cpus, disk):
    directory = WORK / name
    if directory.exists():
        raise SystemExit(f"{name} exists; destroy it first")
    directory.mkdir(parents=True)
    if not KEY.exists():
        sh(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(KEY)])
    (directory / "user-data").write_text(
        "#cloud-config\n"
        f"hostname: {name}\n"
        "users:\n  - name: ubuntu\n    sudo: ALL=(ALL) NOPASSWD:ALL\n    shell: /bin/bash\n"
        f"    ssh_authorized_keys: [\"{(KEY.with_suffix('.pub')).read_text().strip()}\"]\n"
        "ssh_pwauth: false\npackage_update: false\n")
    (directory / "meta-data").write_text(f"instance-id: {name}-{int(time.time())}\nlocal-hostname: {name}\n")
    container = f"sp-vm-{name}"
    mounts = ["-v", f"{directory}:/vm", "-v", f"{BASE}:/base.img:ro"]
    sh(["docker", "run", "--rm", *mounts, IMAGE, "sh", "-c",
        f"qemu-img create -q -f qcow2 -F qcow2 -b /base.img /vm/disk.qcow2 {disk} && "
        "cloud-localds /vm/seed.iso /vm/user-data /vm/meta-data"])
    dns = [arg for server in working_dns() for arg in ("--dns", server)]
    # Own bridge so the guest's docker0 (Docker default 172.17.0.0/16) cannot shadow the SSH client address.
    if subprocess.run(["docker", "network", "inspect", "sp-vm-net"], capture_output=True).returncode:
        sh(["docker", "network", "create", "--subnet", "10.251.251.0/24", "sp-vm-net"], stdout=subprocess.DEVNULL)
    dns += ["--network", "sp-vm-net"]
    sh(["docker", "run", "-d", "--name", container, "--device", "/dev/kvm", *dns, *mounts,
        "-p", f"127.0.0.1:{ssh_port}:{ssh_port}", IMAGE,
        "qemu-system-x86_64", "-enable-kvm", "-cpu", "host", "-m", memory, "-smp", str(cpus),
        "-drive", "file=/vm/disk.qcow2,if=virtio,cache=unsafe", "-drive", "file=/vm/seed.iso,if=virtio,format=raw",
        "-netdev", f"user,id=n0,hostfwd=tcp::{ssh_port}-:22", "-device", "virtio-net-pci,netdev=n0",
        "-nographic", "-serial", "file:/vm/console.log", "-monitor", "none"], stdout=subprocess.DEVNULL)
    (directory / "vm.json").write_text(json.dumps({"container": container, "port": ssh_port}))
    deadline = time.time() + 300
    while time.time() < deadline:
        result = subprocess.run(ssh_argv(name, ssh_port) + ["cloud-init status --wait >/dev/null 2>&1; echo ready"],
                                capture_output=True, text=True)
        if "ready" in result.stdout:
            print(f"{name}: ready on 127.0.0.1:{ssh_port}")
            return
        time.sleep(5)
    raise SystemExit(f"{name}: guest did not become reachable; see {directory}/console.log")


def run(name, command, check=True):
    port = meta(name)["port"]
    script = "sudo -n bash -lc " + shlex.quote(command)
    result = subprocess.run(ssh_argv(name, port) + [script])
    if check and result.returncode:
        raise SystemExit(result.returncode)
    return result.returncode


def push(name, source, destination):
    port = meta(name)["port"]
    source = Path(source)
    tar = subprocess.Popen(["tar", "-C", str(source.parent), "-cf", "-", source.name], stdout=subprocess.PIPE)
    subprocess.run(ssh_argv(name, port) + [f"sudo -n mkdir -p {shlex.quote(destination)} && "
                                           f"sudo -n tar -C {shlex.quote(destination)} -xf -"], stdin=tar.stdout, check=True)
    tar.wait()


def pull(name, source, destination):
    port = meta(name)["port"]
    with open(destination, "wb") as out:
        subprocess.run(ssh_argv(name, port) + [f"sudo -n cat {shlex.quote(source)}"], stdout=out, check=True)


def destroy(name):
    directory = WORK / name
    if (directory / "vm.json").exists():
        subprocess.run(["docker", "rm", "-f", meta(name)["container"]], capture_output=True)
    if directory.exists():
        sh(["docker", "run", "--rm", "-v", f"{WORK}:/w", IMAGE, "rm", "-rf", f"/w/{name}"])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["create", "ssh", "push", "pull", "destroy"])
    parser.add_argument("name")
    parser.add_argument("args", nargs="*")
    parser.add_argument("--ssh-port", type=int, default=2222)
    parser.add_argument("--memory", default="12G")
    parser.add_argument("--cpus", type=int, default=6)
    parser.add_argument("--disk", default="80G")
    args = parser.parse_args()
    if args.action == "create":
        create(args.name, args.ssh_port, args.memory, args.cpus, args.disk)
    elif args.action == "ssh":
        sys.exit(run(args.name, " ".join(args.args), check=False))
    elif args.action == "push":
        push(args.name, *args.args)
    elif args.action == "pull":
        pull(args.name, *args.args)
    else:
        destroy(args.name)


if __name__ == "__main__":
    main()
