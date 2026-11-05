"""Production configuration, Caddy generation and stack rendering without Docker."""
import copy
import json
from pathlib import Path

import pytest
import yaml

from schulplattform import config as cfg
from schulplattform.catalogue import APPS, APP_IDS, RELEASE_IMAGES
from schulplattform.proxy import production_caddyfile
from schulplattform.stack import Layout, Stack, host_address, subnet

DIGEST = "@sha256:" + "a" * 64


def sample(**changes):
    data = {"schema": 1,
            "platform": {"management_domain": "verwaltung.schule.example", "acme_email": "it@schule.example",
                         "acme_environment": "production", "public_ipv4": "80.67.169.12"},
            "smtp": {"mode": "relay", "host": "smtp.provider.example", "port": 587, "security": "starttls",
                     "username": "schule", "sender": "noreply@schule.example", "sender_name": "Grundschule"},
            "backup": {"schedule": "02:30", "retention_days": 14},
            "apps": {app: {"enabled": True, "hostname": f"{app}.schule.example"} for app in APP_IDS}}
    for path, value in changes.items():
        target = data
        keys = path.split(".")
        for key in keys[:-1]:
            target = target[key]
        target[keys[-1]] = value
    return data


class FakeRelease:
    version = "0.0.1"

    def image(self, name):
        return f"ghcr.io/bingenberger/{name}:0.0.1{DIGEST}"

    def install_compose(self, app_id, target):
        target.mkdir(parents=True, exist_ok=True)
        (target / "docker-compose.yml").write_text("services: {app: {image: x}}\n")

    def all_images(self, apps, mail_mode):
        return []


def test_valid_configuration_roundtrip(tmp_path):
    data = sample()
    path = tmp_path / "platform.toml"
    cfg.write(data, path)
    assert cfg.load(path) == data
    assert cfg.enabled_apps(data) == APP_IDS


@pytest.mark.parametrize("change,message", [
    ({"apps.gswb.hostname": "schulwissen.schule.example"}, "used twice"),
    ({"apps.gswb.hostname": "verwaltung.schule.example"}, "used twice"),
    ({"platform.public_ipv4": "10.0.0.5"}, "public address"),
    ({"platform.acme_environment": "custom"}, "acme_ca"),
    ({"apps.gswb.hostname": "Gross.Schule.example"}, "hostname"),
    ({"smtp": {"mode": "relay"}}, "required"),
])
def test_invalid_configuration_rejected(change, message):
    with pytest.raises(cfg.ConfigError, match=message):
        cfg.validate(sample(**change))


def test_custom_acme_allows_private_test_network():
    data = sample(**{"platform.acme_environment": "custom", "platform.public_ipv4": "10.0.2.15"})
    data["platform"]["acme_ca"] = "https://pebble.test:14000/dir"
    cfg.validate(data)


def test_configuration_file_must_not_be_world_writable(tmp_path):
    path = tmp_path / "platform.toml"
    cfg.write(sample(), path)
    path.chmod(0o666)
    with pytest.raises(cfg.ConfigError, match="writable"):
        cfg.load(path)


def test_production_caddyfile_uses_acme_and_strips_trust_headers():
    text = production_caddyfile([("wissen.schule.example", "schulwissen:8000"), ("rad.schule.example", None)],
                                ("verwaltung.schule.example", "dashboard:8000"), "it@schule.example", "production")
    assert "acme_ca https://acme-v02.api.letsencrypt.org/directory" in text
    assert "local_certs" not in text
    assert "request_header -X-Forwarded-*" in text and "request_header -Remote-User" in text
    assert 'respond "Wartung" 503' in text
    assert "reverse_proxy dashboard:8000" in text
    assert "/.well-known/schulplattform-check/" in text
    staging = production_caddyfile([], None, "it@schule.example", "staging")
    assert "acme-staging-v02" in staging


@pytest.mark.parametrize("args", [
    ([("a.example", "x:1")], None, "it@schule.example", "production"),          # invalid upstream port
    ([("a.example", "app:8000"), ("a.example", "app:8000")], None, "it@schule.example", "production"),
    ([], None, "not-an-email", "production"),
    ([], None, "it@schule.example", "custom"),                                   # custom without CA
])
def test_production_caddyfile_rejects_invalid_input(args):
    with pytest.raises(ValueError):
        production_caddyfile(*args)


def test_subnets_are_deterministic_and_disjoint():
    data = sample()
    nets = [subnet(data, APPS[a].index) for a in APP_IDS] + [subnet(data, 0)]
    assert len(set(nets)) == len(nets)
    assert host_address(data, APPS["gswb"].index, 2) == "10.231.1.2"


def render(tmp_path, data):
    layout = Layout(tmp_path / "root")
    stack = Stack(layout, data, FakeRelease())
    store = layout.secrets
    store.mkdir(parents=True, mode=0o700)
    (store / "smtp-password").write_text("x" * 40)
    (store / "smtp-password").chmod(0o600)
    domains = {app: data["apps"][app]["hostname"] for app in stack.apps}
    stack.render(domains)
    return layout, stack, domains


def test_render_overrides_use_configured_hostnames_and_fixed_proxy(tmp_path):
    data = sample()
    layout, stack, domains = render(tmp_path, data)
    for app in APP_IDS:
        override = yaml.load((layout.generated / f"{app}.yml").read_text(), Loader=_TagLoader)
        text = (layout.generated / f"{app}.yml").read_text()
        assert ".localhost" not in text and "local_certs" not in text, app
        assert f"sp-{app}-proxy" in text
        for service, image in APPS[app].images.items():
            assert override["services"][service]["image"].endswith(DIGEST)
        assert override["services"]["app"]["restart"] == "unless-stopped"
    helper = (layout.generated / "schulhelfer.yml").read_text()
    assert "BASE_URL: https://schulhelfer.schule.example" in helper
    assert "PROXY_IPS: 10.231.4.2" in helper and "SMTP_HOST: mailrelay" in helper
    env = (layout.runtime / "wissen.env").read_text()
    assert "SW_ALLOWED_HOSTS=schulwissen.schule.example,localhost" in env


def test_infrastructure_publishes_only_proxy_and_isolates_mail(tmp_path):
    layout, stack, _ = render(tmp_path, sample())
    infra = json.loads((layout.generated / "infra.yml").read_text())
    published = {name: svc.get("ports") for name, svc in infra["services"].items() if svc.get("ports")}
    assert published == {"proxy": ["80:80", "443:443"]}
    relay = infra["services"]["mailrelay"]
    assert set(relay["networks"]) == {"edge", "schulwissen-proxy", "schulhelfer-proxy", "losverkauf-proxy",
                                      "kompetenz-manager-proxy"}
    assert "10.231.4.0/24" in relay["environment"]["RELAY_NETWORKS"]
    assert all(infra["networks"][f"{a}-proxy"]["internal"] for a in APP_IDS)
    assert "/var/run/docker.sock" not in json.dumps(infra)
    assert "smtp-password" in json.dumps(relay["volumes"])
    assert infra["services"]["dashboard"]["read_only"] is True
    assert infra["networks"]["gswb-proxy"]["ipam"]["config"][0] == {"subnet": "10.231.1.0/24",
                                                                    "ip_range": "10.231.1.128/25"}
    assert infra["services"]["proxy"]["networks"]["gswb-proxy"]["ipv4_address"] == "10.231.1.2"
    assert any(v.endswith(":/etc/caddy/conf:ro") for v in infra["services"]["proxy"]["volumes"])


def test_secret_projections_are_stable_and_never_overwritten(tmp_path):
    data = sample()
    layout, stack, domains = render(tmp_path, data)
    key = (layout.runtime / "gswb-key").read_text()
    assert len(key) >= 32 and oct((layout.runtime / "gswb-key").stat().st_mode)[-3:] == "444"
    assert (layout.runtime / "losverkauf/admin-hash").read_text() == ""
    stack.render(domains)  # idempotent
    assert (layout.runtime / "gswb-key").read_text() == key
    (layout.runtime / "gswb-key").chmod(0o644)
    (layout.runtime / "gswb-key").write_text("tampered" * 8)
    with pytest.raises(Exception, match="mismatch"):
        stack.render(domains)


def test_relay_requires_password_when_username_configured(tmp_path):
    layout = Layout(tmp_path / "root")
    stack = Stack(layout, sample(), FakeRelease())
    with pytest.raises(Exception, match="SMTP password"):
        stack.render({app: f"{app}.schule.example" for app in APP_IDS})


def test_only_dns_verified_hosts_are_routed(tmp_path):
    layout, stack, domains = render(tmp_path, sample())
    caddy = (layout.generated / "caddy" / "Caddyfile").read_text()
    assert "schule.example {" not in caddy  # nothing verified yet
    (layout.domains / "status.json").write_text(json.dumps({
        "gswb": {"hostname": domains["gswb"], "dns": "ok"},
        "abgen": {"hostname": domains["abgen"], "dns": "pending"}}))
    stack.write_caddyfile(domains, stack.routed(domains))
    caddy = (layout.generated / "caddy" / "Caddyfile").read_text()
    assert "gswb.schule.example {" in caddy and "abgen.schule.example {" not in caddy


class _TagLoader(yaml.SafeLoader):
    pass


_TagLoader.add_multi_constructor("!", lambda loader, suffix, node: (
    loader.construct_sequence(node) if isinstance(node, yaml.SequenceNode) else
    loader.construct_mapping(node) if isinstance(node, yaml.MappingNode) else loader.construct_scalar(node)))


def test_release_images_cover_catalogue():
    for app, images in RELEASE_IMAGES.items():
        assert set(APPS[app].images.values()) <= {name for name, _ in images}


def test_router_uses_candidate_domains_during_transaction(tmp_path):
    from schulplattform.routing import Router
    layout, stack, domains = render(tmp_path, sample())
    (layout.domains / "current.json").write_text(json.dumps({"generation": "x", "domains": domains}))
    candidate = dict(domains, gswb="neu.schule.example")
    ok = lambda host: {"A": ["80.67.169.12"], "AAAA": []}
    router = Router(stack, None, resolve=ok, ask=None, domains=candidate)
    status = router.check_dns()
    assert status["gswb"]["hostname"] == "neu.schule.example" and status["gswb"]["dns"] == "ok"
    assert "gswb" in stack.routed(candidate)
    stack.write_caddyfile(candidate, stack.routed(candidate))
    assert "neu.schule.example {" in (layout.generated / "caddy" / "Caddyfile").read_text()


def test_kompetenz_worker_healthcheck_has_room_for_slow_vps(tmp_path):
    # Real VPS: the upstream check (full Flask import on 0.5 CPU) took ~5.7 s against a 5 s timeout.
    layout, _, _ = render(tmp_path, sample())
    override = yaml.load((layout.generated / "kompetenz-manager.yml").read_text(), Loader=_TagLoader)
    check = override["services"]["worker"]["healthcheck"]
    assert check["timeout"] == "30s" and check["start_period"] == "60s"


def test_resumed_apply_refreshes_overrides_before_starting_apps(tmp_path):
    from schulplattform.production import Platform
    layout, stack, domains = render(tmp_path, sample())
    stale = layout.generated / "kompetenz-manager.yml"
    stale.write_text("services: {}\n")
    platform = Platform.__new__(Platform)
    platform.stack = stack
    platform.current_domains = lambda: domains
    started = []
    stack.healthy = lambda app: app != "kompetenz-manager"
    stack.migrate = lambda app: None
    stack.start = lambda app: started.append((app, "timeout: 30s" in stale.read_text()))
    platform.step_apps(None)
    assert started == [("kompetenz-manager", True)]


def test_proxy_reloads_when_render_already_wrote_the_new_caddyfile(tmp_path):
    # Real server: 'apply --reconfigure' after switching to production wrote the Caddyfile in the
    # render step; the routes step saw no change and never reloaded Caddy, which kept staging.
    from schulplattform.routing import Router
    layout, stack, domains = render(tmp_path, sample())
    (layout.domains / "current.json").write_text(json.dumps({"generation": "x", "domains": domains}))
    stack.container = lambda project, service: {"Id": "proxy", "State": {"Running": True}}
    reloads = []
    stack.command = lambda argv, **kw: reloads.append(argv[4] if argv[1] == "exec" else argv[1])
    router = Router(stack, None, resolve=None, ask=None, domains=domains)
    router.apply_routes()                       # file already written by render(), CA not known: restart
    assert reloads == ["validate", "restart"]
    router.apply_routes()                       # loaded and unchanged: nothing
    assert reloads == ["validate", "restart"]
    stack.write_caddyfile(domains, {"gswb"})    # route change, same CA: reload is enough
    router.apply_routes()
    assert reloads[2:] == ["validate", "reload"]
    # Real server: staging -> production. A reload kept the staging certificates in Caddy's memory.
    stack.config = sample(**{"platform.acme_environment": "staging"})
    stack.write_caddyfile(domains, stack.routed(domains))
    router.apply_routes()
    assert reloads[4:] == ["validate", "restart"]


def test_kompetenz_fonts_directory_is_mounted_read_only_for_pdf_export(tmp_path):
    layout, _, _ = render(tmp_path, sample())
    override = yaml.load((layout.generated / "kompetenz-manager.yml").read_text(), Loader=_TagLoader)
    fonts = layout.runtime / "kompetenz-manager/fonts"
    assert fonts.is_dir()
    assert f"{fonts}:/usr/local/share/fonts:ro" in override["services"]["app"]["volumes"]
