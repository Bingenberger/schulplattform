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
    assert set(relay["networks"]) == {"edge"} | {f"{a}-proxy" for a in APP_IDS if APPS[a].mail}
    assert {"schulwissen-proxy", "losverkauf-proxy", "schulanmeldung-proxy"} <= set(relay["networks"])
    assert "fundkiste-proxy" not in relay["networks"]          # apps without mail stay isolated
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
    stack.outdated = lambda app: False
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


def test_fernet_secret_is_a_valid_key_and_stays_stable(tmp_path):
    from cryptography.fernet import Fernet
    layout, stack, _ = render(tmp_path, sample())
    projection = layout.runtime / "sl-journal/master-key"
    key = projection.read_text().strip()
    Fernet(key.encode())                                    # raises if the format is wrong
    stack.materialize_secrets()
    assert projection.read_text().strip() == key            # never regenerated
    assert (layout.secrets / "journal-master-key").read_text() == key


def test_upgrade_adds_new_apps_to_an_existing_installation(tmp_path):
    # 0.1.1 -> 0.2.0 on the real server: platform.toml and the domain store only know the ten
    # original apps; after 'configure' enables the new ones, 'apply --reconfigure' must add their
    # domain records, overrides and secrets without touching the existing ones.
    from schulplattform.production import Platform
    old_apps = APP_IDS[:10]
    new_apps = APP_IDS[10:]
    assert set(new_apps) == {"fundkiste", "schuleva", "schulkasse", "schulanmeldung", "sl-journal", "bildergalerie"}
    old = sample()
    old["apps"] = {app: old["apps"][app] for app in old_apps}
    path = tmp_path / "platform.toml"
    cfg.write(old, path)

    def platform_for(config):
        platform = Platform.__new__(Platform)
        platform.config = cfg.load(path) if config is None else config
        platform.layout = Layout(tmp_path / "root")
        platform.layout.prepare()
        platform.stack = Stack(platform.layout, platform.config, FakeRelease())
        platform._domains = None
        return platform

    before = platform_for(None)
    secret = lambda: (before.layout.runtime / "gswb-key").read_text()
    (before.layout.secrets / "smtp-password").write_text("x" * 40)
    (before.layout.secrets / "smtp-password").chmod(0o600)
    domains = before.current_domains()
    assert set(domains) == set(old_apps)
    before.stack.render(domains)
    gswb_key = secret()

    cfg.write(sample(), path)                      # what the wizard writes after 'configure'
    after = platform_for(None)
    domains = after.current_domains()
    assert set(domains) == set(APP_IDS)
    assert all(domains[app] == f"{app}.schule.example" for app in new_apps)
    after.stack.render(domains)
    for app in new_apps:
        assert (after.layout.generated / f"{app}.yml").is_file()
    assert secret() == gswb_key                    # existing secrets are kept
    stored = json.loads((after.layout.domains / "current.json").read_text())["domains"]
    assert set(stored) == set(APP_IDS)


def test_status_points_out_hostnames_changed_only_in_configure(tmp_path):
    # Real server: 'configure' set zackboing.gsndk.de, but the platform kept serving quiz.gsndk.de
    # without saying so; the change needs 'domain-change'.
    import types
    from schulplattform.installer import _domain_notes
    layout, stack, domains = render(tmp_path, sample(**{"apps.zackboing.hostname": "zackboing.schule.example"}))
    active = dict(domains, zackboing="quiz.schule.example")
    platform = types.SimpleNamespace(stack=stack, config=stack.config, layout=layout)
    notes = _domain_notes(platform, active)
    assert notes == ["Hinweis: zackboing läuft unter quiz.schule.example, platform.toml nennt "
                     "zackboing.schule.example. Umstellen mit: ./install.sh domain-change zackboing "
                     "zackboing.schule.example"]
    assert _domain_notes(platform, domains) == []
    (layout.domains / "pending.json").write_text(json.dumps({
        "status": "recovery-required", "old": {"domains": active}, "candidate": {"domains": domains}}))
    assert "nicht abgeschlossen" in _domain_notes(platform, domains)[0]


def test_apply_moves_a_healthy_app_to_its_new_release_image(tmp_path):
    # Real server (0.2.0 -> 0.2.1): losverkauf stayed on 0.1.0 because step_apps only restarted
    # unhealthy apps; the fixed image never ran.
    from schulplattform.production import Platform
    layout, stack, domains = render(tmp_path, sample())
    current = FakeRelease().image("losverkauf")
    old = "ghcr.io/bingenberger/losverkauf:0.1.0@sha256:" + "b" * 64
    def container(app, service):
        image = old if app == "losverkauf" else FakeRelease().image(APPS[app].images[service])
        return {"Config": {"Image": image}, "Image": "sha256:" + "c" * 64}
    stack.container = container
    stack.command = lambda argv, **kw: "[]"
    assert stack.outdated("losverkauf") and not stack.outdated("gswb")
    assert current.endswith("a" * 64)
    platform = Platform.__new__(Platform)
    platform.stack = stack
    platform.current_domains = lambda: domains
    stack.healthy = lambda app: True
    calls = []
    stack.migrate = lambda app: calls.append(("migrate", app))
    stack.start = lambda app: calls.append(("start", app))
    platform.step_apps(None)
    assert calls == [("migrate", "losverkauf"), ("start", "losverkauf")]
    assert platform.probe_apps(None) is False          # still the old container in this fake


def test_confirmed_import_counts_as_first_access(tmp_path, monkeypatch, capsys):
    # Real server: status listed imported apps under "Erstzugang … offen" although their old
    # accounts had come along.
    import types
    from schulplattform import installer, importer, production
    state = tmp_path / "state"
    state.mkdir()
    (state / "bootstrap.json").write_text(json.dumps({"appSetup": {"zackboing": False, "gswb": False}}))
    fake = types.SimpleNamespace(layout=types.SimpleNamespace(state=state))
    monkeypatch.setattr(installer, "verify_bundle", lambda bundle, key: None)
    monkeypatch.setattr(production, "Platform", lambda *a, **kw: fake)
    monkeypatch.setattr(importer, "run_import", lambda platform, app, archive, confirm=False: {"mode": "x"})
    common = ["--bundle", str(tmp_path), "--trusted-key", str(tmp_path / "k")]
    installer._main(["import", "gswb", "a.tar.gpg", "--dry-run", *common])
    assert json.loads((state / "bootstrap.json").read_text())["appSetup"]["gswb"] is False
    installer._main(["import", "zackboing", "a.tar.gpg", "--confirm-replace", *common])
    assert json.loads((state / "bootstrap.json").read_text())["appSetup"] == {"zackboing": True, "gswb": False}


def test_tafel_gallery_and_video_search_stay_off_until_configured(tmp_path):
    layout, stack, domains = render(tmp_path, sample(**{"apps.bildergalerie.enabled": False}))
    override = yaml.load((layout.generated / "grundschultafel.yml").read_text(), Loader=_TagLoader)
    app = override["services"]["app"]
    assert app["environment"]["GALLERY_ORIGIN"] == "" and app["environment"]["TAFEL_YOUTUBE_ENABLED"] == "0"
    key = layout.runtime / "tafel-youtube-key"
    assert key.read_text() == ""
    assert f"{key}:/run/secrets/youtube-key:ro" in app["volumes"]
    assert app["environment"]["YOUTUBE_API_KEY_FILE"] == "/run/secrets/youtube-key"
    # Other apps never see these settings.
    assert "GALLERY_ORIGIN" not in (layout.generated / "schulhelfer.yml").read_text()


def test_tafel_gallery_and_video_search_follow_configuration_and_key(tmp_path):
    data = sample(**{"apps.grundschultafel.gallery_origin": "https://pix.example.org"})
    cfg.validate(data)
    layout, stack, domains = render(tmp_path, data)
    from schulplattform.appsetup import _replace_projection
    _replace_projection(layout.runtime / "tafel-youtube-key", "AIza" + "x" * 35)
    stack.render(domains)                                   # 'empty' projection keeps the operator's key
    assert (layout.runtime / "tafel-youtube-key").read_text() == "AIza" + "x" * 35
    app = yaml.load((layout.generated / "grundschultafel.yml").read_text(), Loader=_TagLoader)["services"]["app"]
    assert app["environment"]["GALLERY_ORIGIN"] == "https://pix.example.org"
    assert app["environment"]["TAFEL_YOUTUBE_ENABLED"] == "1"
    _replace_projection(layout.runtime / "tafel-youtube-key", "")
    stack.render(domains)
    app = yaml.load((layout.generated / "grundschultafel.yml").read_text(), Loader=_TagLoader)["services"]["app"]
    assert app["environment"]["TAFEL_YOUTUBE_ENABLED"] == "0"


@pytest.mark.parametrize("app,origin,message", [
    ("grundschultafel", "http://pix.example.org", "gallery_origin"),
    ("grundschultafel", "https://pix.example.org/pfad", "gallery_origin"),
    ("gswb", "https://pix.example.org", "only supported"),
])
def test_gallery_origin_is_validated(app, origin, message):
    with pytest.raises(cfg.ConfigError, match=message):
        cfg.validate(sample(**{f"apps.{app}.gallery_origin": origin}))


def test_gallery_origin_survives_toml_roundtrip(tmp_path):
    data = sample(**{"apps.grundschultafel.gallery_origin": "https://pix.example.org"})
    path = tmp_path / "platform.toml"
    cfg.write(data, path)
    assert cfg.load(path)["apps"]["grundschultafel"]["gallery_origin"] == "https://pix.example.org"


def _tafel_env(tmp_path, data):
    layout, _, _ = render(tmp_path, data)
    override = yaml.load((layout.generated / "grundschultafel.yml").read_text(), Loader=_TagLoader)
    return override["services"]["app"]["environment"], layout


def test_tafel_uses_the_platforms_own_woerterbuch_by_default(tmp_path):
    env, layout = _tafel_env(tmp_path, sample())
    assert env["WOERTERBUCH_ORIGIN"] == "https://gswb.schule.example"
    assert "WOERTERBUCH_ORIGIN" not in (layout.generated / "gswb.yml").read_text()
    # No shared network: the board reaches gswb over its public origin only.
    networks = yaml.load((layout.generated / "grundschultafel.yml").read_text(), Loader=_TagLoader)["networks"]
    assert [n["name"] for n in networks.values()] == ["sp-grundschultafel-proxy"]


def test_woerterbuch_stays_off_without_gswb(tmp_path):
    env, _ = _tafel_env(tmp_path / "a", sample(**{"apps.gswb.enabled": False}))
    assert env["WOERTERBUCH_ORIGIN"] == ""


@pytest.mark.parametrize("value,expected", [("", ""), ("https://woerterbuch.example.org", "https://woerterbuch.example.org")])
def test_explicit_woerterbuch_origin_overrides_the_default(tmp_path, value, expected):
    data = sample(**{"apps.grundschultafel.woerterbuch_origin": value})
    cfg.validate(data)
    env, _ = _tafel_env(tmp_path, data)
    assert env["WOERTERBUCH_ORIGIN"] == expected
    path = tmp_path / "platform.toml"
    cfg.write(data, path)
    assert cfg.load(path)["apps"]["grundschultafel"]["woerterbuch_origin"] == value


@pytest.mark.parametrize("app,origin,message", [
    ("grundschultafel", "http://woerterbuch.example.org", "woerterbuch_origin"),
    ("grundschultafel", "https://woerterbuch.example.org/api", "woerterbuch_origin"),
    ("grundschultafel", "https://user@woerterbuch.example.org", "woerterbuch_origin"),
    ("schulhelfer", "https://woerterbuch.example.org", "only supported"),
])
def test_woerterbuch_origin_is_validated(app, origin, message):
    with pytest.raises(cfg.ConfigError, match=message):
        cfg.validate(sample(**{f"apps.{app}.woerterbuch_origin": origin}))


def _run_wizard(tmp_path, existing, answers):
    import os, pty, threading
    master, slave = pty.openpty()
    out = []
    reader = threading.Thread(target=lambda: _drain(master, out), daemon=True)
    reader.start()
    os.write(master, "".join(a + "\n" for a in answers).encode())
    try:
        return cfg.wizard(tmp_path / "platform.toml", existing, os.ttyname(slave))
    finally:
        os.close(slave)


def _drain(fd, out):
    import os
    try:
        while chunk := os.read(fd, 4096):
            out.append(chunk)
    except OSError:
        pass


@pytest.mark.parametrize("stored,typed,expected", [
    (None, "", None),                                         # default: own gswb
    ("", "", ""),                                             # "aus" is kept
    (None, "aus", ""),
    (None, "https://woerterbuch.example.org", "https://woerterbuch.example.org"),
])
def test_wizard_asks_for_the_woerterbuch(tmp_path, stored, typed, expected):
    existing = sample()
    if stored is not None:
        existing["apps"]["grundschultafel"]["woerterbuch_origin"] = stored
    # 6 platform questions, then per app: install + hostname (+ gallery, woerterbuch for the board)
    answers = [""] * 6
    for app in APP_IDS:
        answers += ["", ""]
        if app == "grundschultafel":
            answers += ["", typed]
    answers += [""] * 12
    data = _run_wizard(tmp_path, existing, answers)
    assert data["apps"]["grundschultafel"].get("woerterbuch_origin") == expected


def test_tafel_uses_the_platforms_own_gallery_with_token(tmp_path):
    env, layout = _tafel_env(tmp_path, sample())
    assert env["GALLERY_ORIGIN"] == "https://bildergalerie.schule.example"
    assert env["GALLERY_TOKEN_FILE"] == "/run/secrets/gallery-token"
    tafel = yaml.load((layout.generated / "grundschultafel.yml").read_text(), Loader=_TagLoader)["services"]["app"]
    gallery = yaml.load((layout.generated / "bildergalerie.yml").read_text(), Loader=_TagLoader)["services"]["app"]
    token = layout.runtime / "gallery-api-token"
    assert f"{token}:/run/secrets/gallery-token:ro" in tafel["volumes"]
    assert f"{token}:/run/secrets/api-token:ro" in gallery["volumes"]
    assert len(token.read_text()) >= 32 and oct(token.stat().st_mode & 0o777) == "0o444"
    assert gallery["environment"]["GALLERY_PUBLIC"] == "true"
    assert gallery["environment"]["GALLERY_AI_KEY_FILE"] == ""                    # AI metadata off by default
    assert (layout.runtime / "gallery-ai-key").read_text() == ""
    networks = yaml.load((layout.generated / "bildergalerie.yml").read_text(), Loader=_TagLoader)["networks"]
    assert [n["name"] for n in networks.values()] == ["sp-bildergalerie-proxy"]


def test_external_gallery_never_receives_the_platform_token(tmp_path):
    env, _ = _tafel_env(tmp_path, sample(**{"apps.grundschultafel.gallery_origin": "https://pix.example.org"}))
    assert env["GALLERY_ORIGIN"] == "https://pix.example.org" and env["GALLERY_TOKEN_FILE"] == ""


def test_own_gallery_named_explicitly_still_gets_the_token(tmp_path):
    data = sample(**{"apps.grundschultafel.gallery_origin": "https://bildergalerie.schule.example"})
    env, _ = _tafel_env(tmp_path, data)
    assert env["GALLERY_TOKEN_FILE"] == "/run/secrets/gallery-token"


def test_gallery_can_be_switched_off_for_the_board(tmp_path):
    data = sample(**{"apps.grundschultafel.gallery_origin": ""})
    cfg.validate(data)
    env, _ = _tafel_env(tmp_path, data)
    assert env["GALLERY_ORIGIN"] == "" and env["GALLERY_TOKEN_FILE"] == ""


def test_private_gallery_and_dashboard_tile(tmp_path):
    data = sample(**{"apps.bildergalerie.public": False})
    cfg.validate(data)
    layout, _, _ = render(tmp_path, data)
    gallery = yaml.load((layout.generated / "bildergalerie.yml").read_text(), Loader=_TagLoader)["services"]["app"]
    assert gallery["environment"]["GALLERY_PUBLIC"] == "false"
    with pytest.raises(cfg.ConfigError, match="only supported for bildergalerie"):
        cfg.validate(sample(**{"apps.gswb.public": True}))


def test_gallery_ai_key_switches_metadata_on(tmp_path):
    layout, stack, domains = render(tmp_path, sample())
    from schulplattform.appsetup import _replace_projection
    _replace_projection(layout.runtime / "gallery-ai-key", '{"type": "service_account", "project_id": "p"}')
    stack.render(domains)
    gallery = yaml.load((layout.generated / "bildergalerie.yml").read_text(), Loader=_TagLoader)["services"]["app"]
    assert gallery["environment"]["GALLERY_AI_KEY_FILE"] == "/run/secrets/ai-key"


def test_gallery_ai_key_command_checks_the_file(tmp_path):
    import json as _json
    from types import SimpleNamespace
    from schulplattform.appsetup import set_gallery_ai_key
    from schulplattform.state import StateError
    layout, stack, domains = render(tmp_path / "p", sample())
    calls = []
    stack.compose = lambda *argv, **kw: calls.append(argv)
    platform = SimpleNamespace(stack=stack, layout=layout, current_domains=lambda: domains)
    bad = tmp_path / "bad.json"
    for content in ("kein json", _json.dumps({"type": "authorized_user"}), _json.dumps([1])):
        bad.write_text(content)
        with pytest.raises(StateError):
            set_gallery_ai_key(platform, bad)
    assert (layout.runtime / "gallery-ai-key").read_text() == "" and not calls
    good = tmp_path / "key.json"
    good.write_text(_json.dumps({"type": "service_account", "project_id": "p", "private_key": "-----BEGIN-----"}))
    assert set_gallery_ai_key(platform, good) is True
    assert _json.loads((layout.runtime / "gallery-ai-key").read_text())["project_id"] == "p"
    assert calls[-1][0] == "bildergalerie" and "--force-recreate" in calls[-1]
    assert set_gallery_ai_key(platform, None) is False
    assert (layout.runtime / "gallery-ai-key").read_text() == ""


def test_relative_paths_count_from_the_operators_directory(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from schulplattform import installer
    (tmp_path / "archiv.tar.gpg").write_bytes(b"x")
    monkeypatch.setenv("SP_CALLER_CWD", str(tmp_path))
    args = SimpleNamespace(action="import", target=["bildergalerie", "archiv.tar.gpg"], bundle=Path("releases/0.3.0"),
                           trusted_key=None, key_file=None, config=Path("/etc/schulplattform/platform.toml"))
    installer._resolve_caller_paths(args)
    assert args.target == ["bildergalerie", str(tmp_path / "archiv.tar.gpg")]
    assert args.bundle == Path("releases/0.3.0")          # not in the caller's directory: unchanged
    assert args.config == Path("/etc/schulplattform/platform.toml")
