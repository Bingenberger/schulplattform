from schulplattform.installer import blockers


def test_foreign_docker_and_nginx_are_never_adopted_implicitly():
    host = dict(os='ubuntu', version='24.04', architecture='x86_64', root=True,
        dockerInstalled=True, services={'nginx': 'active'}, ports={'80': 'free', '443': 'free'},
        memory={'MemTotal': 16 * 1024**3}, diskFreeBytes=250 * 1000**3, ntpSynchronized='yes')
    assert any('takeover' in reason for reason in blockers(host))
