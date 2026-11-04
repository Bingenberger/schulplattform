"""Host provisioning helpers without touching the machine."""
from types import SimpleNamespace

from schulplattform.host import Provisioner


def fake(outputs):
    def run(argv, check=True, input=None, timeout=1800, env=None):
        key = argv[-1]
        code, out = outputs.get(key, (1, ""))
        return SimpleNamespace(returncode=code, stdout=out)
    return run


def test_installed_accepts_held_packages(tmp_path):
    p = Provisioner(tmp_path, runner=fake({
        "docker-ce": (0, "hold ok installed|5:29.1.3-1~ubuntu.24.04~noble"),
        "ufw": (0, "install ok installed|0.36.2-6"),
        "gone": (0, "deinstall ok config-files|1.0"),
    }))
    assert p.installed("docker-ce") == "5:29.1.3-1~ubuntu.24.04~noble"
    assert p.installed("ufw") == "0.36.2-6"
    assert p.installed("gone") is None
    assert p.installed("missing") is None


def test_ssh_ports_include_socket_activated_sshd(tmp_path):
    listing = ('LISTEN 0 4096 0.0.0.0:22 0.0.0.0:* users:(("systemd",pid=1,fd=50))\n'
               'LISTEN 0 128 0.0.0.0:2200 0.0.0.0:* users:(("sshd",pid=900,fd=3))\n')
    p = Provisioner(tmp_path, runner=fake({"-ltnp": (0, listing), "--value": (0, "[::]:22 (Stream)\n")}))
    assert p.ssh_ports() == [22, 2200]


def test_ssh_port_of_current_session_is_kept(tmp_path, monkeypatch):
    monkeypatch.setenv("SSH_CONNECTION", "192.0.2.5 50000 198.51.100.4 2222")
    p = Provisioner(tmp_path, runner=fake({}))
    assert p.ssh_ports() == [2222]
