from schulplattform.installer import blockers


def test_foreign_docker_and_nginx_are_never_adopted_implicitly():
    host = dict(os='ubuntu', version='24.04', architecture='x86_64', root=True,
        dockerInstalled=True, services={'nginx': 'active'}, ports={'80': 'free', '443': 'free'},
        memory={'MemTotal': 16 * 1024**3}, diskFreeBytes=250 * 1000**3, ntpSynchronized='yes')
    assert any('takeover' in reason for reason in blockers(host))


def test_inventory_runs_and_sizing_only_warns(monkeypatch):
    import schulplattform.installer as installer
    monkeypatch.setattr(installer, "_clock_skew", lambda: 2.0)
    host = installer.inventory()
    assert {"platformOwnsDocker", "clockSkewSeconds", "ports"} <= set(host)
    small = dict(host, os="ubuntu", version="24.04", architecture="x86_64", root=True, dockerInstalled=False,
                 services={}, ports={"80": "free", "443": "free"}, ntpSynchronized="no",
                 memory={"MemTotal": 8 * 1024**3, "SwapTotal": 0}, diskFreeBytes=10**9)
    assert installer.blockers(small) == []
    assert any("16 GB" in w for w in installer.warnings(small))
    assert installer.blockers(dict(small, clockSkewSeconds=120.0))
    assert installer.blockers(dict(small, clockSkewSeconds=None))
