"""Single source of truth for the ten integrated apps.

Everything the production stack derives per app (images, routing, public URL
variables, proxy trust, mail target, secrets, migrations, checks) is declared
here instead of being spread across code paths. App variable names are the
apps' own (adapter principle); nothing is renamed to platform-wide names.

Override templates mirror the overrides proven in the local ten-app pilot
(schulplattform/pilot.py); only host, origin, proxy address, mail target,
image references and restart policy are parameterised.
"""
from dataclasses import dataclass, field

REGISTRY = "ghcr.io/bingenberger"

APP_IDS = ("gswb", "schulwissen", "zackboing", "schulhelfer", "losverkauf", "grundschultafel",
           "fahrradausbildung", "leseflux", "kompetenz-manager", "abgen", "fundkiste", "schuleva", "schulkasse",
           "schulanmeldung")

# Published image name -> Dockerfile target (None = default/last stage).
RELEASE_IMAGES = {
    "gswb": (("gswb", None),),
    "schulwissen": (("schulwissen", None),),
    "zackboing": (("zackboing", "runtime"),),
    "schulhelfer": (("schulhelfer", "final"),),
    "losverkauf": (("losverkauf", "final"),),
    "grundschultafel": (("grundschultafel", "runtime"),),
    "fahrradausbildung": (("fahrradausbildung", "runtime"),),
    "leseflux": (("leseflux", "runtime"),),
    "kompetenz-manager": (("kompetenz-manager", "runtime"),),
    "abgen": (("abgen", "runtime"), ("abgen-pdf", "pdf")),
    "fundkiste": (("fundkiste", "final"),),
    "schuleva": (("schuleva", "final"),),
    "schulkasse": (("schulkasse", "final"),),
    "schulanmeldung": (("schulanmeldung", "final"),),
}

# Platform infrastructure images (pinned upstream digests, already used in the pilot).
INFRASTRUCTURE = {
    "postgres16": "postgres:16-alpine@sha256:0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab",
    "postgres18": "postgres:18.6-alpine@sha256:10a5c69a83035ab5239f5620d708520e8b28f5aa1f2b20143e6024532edadfb5",
    "caddy": "caddy:2.11.7-alpine@sha256:e70b164da81ef698b3ad19af799ea6086ce6d9e48ed4079eb9fe26f6fbf14ee5",
    "mailpit": "axllent/mailpit:v1.33.0@sha256:9b3a463be15354c0f0eba91697d80e3e0d8a5623ef0e627cacc836bc17fd5231",
}

# Platform-owned images published from this repository.
PLATFORM_IMAGES = ("schulplattform-dashboard", "schulplattform-relay")

MAIL_PORT = 1025  # both the relay and the sink listen here on the app proxy networks

# Variables whose value is derived from the hostname (shown in the domain change preview).
DOMAIN_VARIABLES = {"gswb": (), "schulwissen": ("SW_ALLOWED_HOSTS", "SW_OEFFENTLICHE_URL"),
                    "zackboing": ("ZACKBOING_PUBLIC_URL",), "schulhelfer": ("BASE_URL",),
                    "losverkauf": ("BASE_URL",), "grundschultafel": ("BASE_URL",),
                    "fahrradausbildung": ("FP_OEFFENTLICHE_URL",), "leseflux": ("CORS_ORIGIN",),
                    "kompetenz-manager": ("APP_BASE_URL",), "abgen": ("WEB_ORIGIN",),
                    "fundkiste": ("FUNDKISTE_BASE_URL",), "schuleva": ("BASE_URL",),
                    "schulkasse": (), "schulanmeldung": ("SL_OFFICE_PUBLIC_BASE_URL",)}


@dataclass(frozen=True)
class Check:
    method: str
    path: str
    expected: int
    headers: tuple = ()


@dataclass(frozen=True)
class App:
    id: str
    index: int                    # fixed position -> deterministic proxy subnet
    port: int
    ready: str
    services: tuple               # long-running services managed by the platform, primary first
    database_services: tuple = () # started (and healthy) before migrations
    images: dict = field(default_factory=dict)  # compose service -> release image name
    compose_env: dict = field(default_factory=dict)  # interpolation variable -> runtime-relative path
    secrets: tuple = ()           # (runtime-relative path, kind) kind: random:<store-name> | empty | url:<template>
    migrations: tuple = ()        # argv lists run with "compose run --rm --no-deps <service>"
    migration_service: str = "app"
    mail: bool = False
    checks: tuple = ()
    override: str = ""            # YAML template, see render_override()
    extra_files: dict = field(default_factory=dict)  # runtime-relative path -> template text
    # Documented local first access, console only. ("run"|"exec", argv with {name}/{email}/{display})
    # or ("host-hash", (hash-file[, name-file]), env-name-for-username) for Werkzeug hash projections.
    setup: tuple = ()
    drain: str = ""               # "" | "quiz" | "worksheet"
    # Operator-provided host directories (runtime-relative), created empty and mounted read-only.
    host_dirs: tuple = ()


POSTGRES_INIT = """#!/bin/sh
set -eu
export APP_DB_PASSWORD="$(cat /run/secrets/app_db_password)"
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
\\getenv app_password APP_DB_PASSWORD
CREATE ROLE schulwissen LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'app_password';
CREATE DATABASE schulwissen OWNER schulwissen;
REVOKE ALL ON DATABASE postgres FROM PUBLIC;
REVOKE ALL ON DATABASE template1 FROM PUBLIC;
SQL
"""

_PROXY_NETWORK = """networks:
  proxy:
    external: true
    name: {proxy_network}
"""

APPS = {app.id: app for app in [
    App("gswb", 1, 8000, "/health/ready", ("app",),
        images={"app": "gswb"},
        compose_env={"GSWB_SECRET_FILE": "gswb-key", "GSWB_EDITOR_HASH_FILE": "gswb-editor"},
        secrets=(("gswb-key", "random:gswb-key"), ("gswb-editor", "empty"), ("gswb-editor-name", "empty")),
        migrations=(("python", "-m", "grundschul_woerterbuch.migrate"),),
        checks=(Check("GET", "/review", 401, (("X-Forwarded-User", "admin"), ("Remote-User", "admin"))),
                Check("POST", "/review/synthetic/approve", 401, (("X-Forwarded-User", "admin"),)),
                Check("GET", "/", 200)),
        setup=("host-hash", ("gswb-editor", "gswb-editor-name"), "EDITOR_USERNAME"),
        override="""services:
  app:
    image: {image_app}
    ports: !reset []
    restart: unless-stopped
    networks:
      default: {{}}
      proxy:
        aliases: [gswb]
""" + _PROXY_NETWORK),
    App("schulwissen", 2, 8000, "/health/ready", ("app",), database_services=("db",),
        images={"app": "schulwissen"},
        compose_env={"POSTGRES_PASSWORD": "!unused"},
        secrets=(("postgres-admin", "random:postgres-admin"), ("postgres-app", "random:postgres-app"),
                 ("wissen-key", "random:wissen-key"),
                 ("wissen-db", "url:postgresql://schulwissen:{postgres-app}@db:5432/schulwissen")),
        migrations=(("python", "manage.py", "platform_migrate"),),
        mail=True,
        checks=(Check("GET", "/", 302),),
        setup=("run", ("python", "manage.py", "admin_anlegen", "{email}")),
        extra_files={"schulwissen-init-postgres.sh": POSTGRES_INIT,
                     "wissen.env": ("SW_SECRET_KEY_FILE=/run/secrets/session_key\n"
                                    "SW_DATABASE_URL_FILE=/run/secrets/database_url\n"
                                    "SW_ALLOWED_HOSTS={host},localhost\n"
                                    "SW_OEFFENTLICHE_URL={origin}\n"
                                    "SW_SMTP_HOST={mail_host}\nSW_SMTP_PORT={mail_port}\nSW_SMTP_TLS=false\n")},
        override="""services:
  db:
    image: {postgres16}
    restart: unless-stopped
    environment: !override
      POSTGRES_USER: postgres
      POSTGRES_DB: postgres
      POSTGRES_PASSWORD_FILE: /run/secrets/admin_password
    secrets: [admin_password, app_db_password]
    volumes:
      - {runtime}/schulwissen-init-postgres.sh:/docker-entrypoint-initdb.d/01-app.sh:ro
    healthcheck:
      test: [CMD-SHELL, "pg_isready -h 127.0.0.1 -U postgres -d postgres"]
  app:
    image: {image_app}
    restart: unless-stopped
    ports: !reset []
    env_file: !override
      - {runtime}/wissen.env
    environment: !override
      SW_MEDIEN_VERZEICHNIS: /medien
      SW_WORKER: "2"
      FORWARDED_ALLOW_IPS: {proxy_ip}
      SW_PROXY_IPS: {proxy_ip}
    secrets: [session_key, database_url]
    networks:
      default: {{}}
      proxy:
        aliases: [schulwissen]
    healthcheck:
      test: [CMD, python, -c, "import urllib.request; urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8000/health/ready', headers={{'Host': 'localhost'}}), timeout=2)"]
      interval: 5s
      timeout: 3s
      retries: 20
secrets:
  admin_password:
    file: {runtime}/postgres-admin
  app_db_password:
    file: {runtime}/postgres-app
  session_key:
    file: {runtime}/wissen-key
  database_url:
    file: {runtime}/wissen-db
""" + _PROXY_NETWORK),
    App("zackboing", 3, 3000, "/health/ready", ("app",),
        images={"app": "zackboing"},
        migrations=(("node", "server/migrate.js"),),
        checks=(Check("GET", "/api/admin/users", 401), Check("POST", "/_platform/prepare-stop", 403)),
        setup=("run", ("node", "server/bootstrap.js")),
        drain="quiz",
        override="""services:
  app:
    image: {image_app}
    restart: unless-stopped
    ports: !reset []
    environment:
      ZACKBOING_PUBLIC_URL: {origin}
      ZACKBOING_PROXY_IPS: {proxy_ip}
    networks:
      default: {{}}
      proxy:
        aliases: [zackboing]
""" + _PROXY_NETWORK),
    App("schulhelfer", 4, 8000, "/health/ready", ("app",),
        images={"app": "schulhelfer"},
        compose_env={"SCHULHELFER_SECRET_FILE": "helfer-key"},
        secrets=(("helfer-key", "random:helfer-key"),),
        migrations=(("python", "-m", "app.migrate"),),
        mail=True,
        checks=(Check("GET", "/admin", 303), Check("GET", "/", 200)),
        setup=("run", ("python", "-m", "app.setup_admin")),
        override="""services:
  app:
    image: {image_app}
    restart: unless-stopped
    ports: !reset []
    environment:
      BASE_URL: {origin}
      PROXY_IPS: {proxy_ip}
      SMTP_HOST: {mail_host}
      SMTP_PORT: "{mail_port}"
      SMTP_STARTTLS: "false"
      SMTP_USE_TLS: "false"
      SMTP_FROM: {mail_from}
    networks:
      default: {{}}
      proxy:
        aliases: [schulhelfer]
""" + _PROXY_NETWORK),
    App("losverkauf", 5, 8000, "/health/ready", ("app",),
        images={"app": "losverkauf"},
        compose_env={"LOSVERKAUF_SECRETS_DIR": "losverkauf"},
        secrets=(("losverkauf/session-key", "random:lose-key"), ("losverkauf/parent-token", "random:lose-parent"),
                 ("losverkauf/admin-name", "empty"), ("losverkauf/admin-hash", "empty")),
        migrations=(("python", "-m", "los_migrate"),),
        mail=True,
        checks=(Check("GET", "/admin", 302), Check("GET", "/", 403)),
        setup=("host-hash", ("losverkauf/admin-hash", "losverkauf/admin-name"), None),
        override="""services:
  app:
    image: {image_app}
    restart: unless-stopped
    ports: !reset []
    environment:
      BASE_URL: {origin}
      PROXY_IPS: {proxy_ip}
      SMTP_HOST: {mail_host}
      SMTP_PORT: "{mail_port}"
      SMTP_SICHERHEIT: keine
      MAIL_FROM: {mail_from}
    networks:
      default: {{}}
      proxy:
        aliases: [losverkauf]
""" + _PROXY_NETWORK),
    App("grundschultafel", 6, 3000, "/health/ready", ("app",),
        images={"app": "grundschultafel"},
        compose_env={"TAFEL_SECRET_FILE": "tafel-key"},
        secrets=(("tafel-key", "random:tafel-key"),),
        migrations=(("node", "scripts/migrate.mjs"),),
        checks=(Check("GET", "/api/admin/users", 401),),
        setup=("exec", ("node", "scripts/bootstrap.mjs", "{name}")),
        override="""services:
  app:
    image: {image_app}
    restart: unless-stopped
    ports: !reset []
    environment:
      BASE_URL: {origin}
      GALLERY_ORIGIN: ""
      TAFEL_YOUTUBE_ENABLED: "0"
    networks:
      default: {{}}
      proxy:
        aliases: [grundschultafel]
""" + _PROXY_NETWORK),
    App("fahrradausbildung", 7, 8000, "/health/ready", ("app",), database_services=("db",),
        images={"app": "fahrradausbildung"},
        compose_env={"FP_SECRETS_DIR": "fahrrad"},
        secrets=(("fahrrad/db-admin", "random:rad-db-admin"), ("fahrrad/db-app", "random:rad-db-app"),
                 ("fahrrad/database-url", "url:postgresql+psycopg://fahrrad:{rad-db-app}@db:5432/fahrrad")),
        migrations=(("python", "-m", "app.migrate"),),
        checks=(Check("GET", "/verwaltung/", 303), Check("GET", "/p/demo", 200)),
        setup=("exec", ("python", "-m", "app.kommandos", "systemadmin-anlegen", "{email}")),
        override="""services:
  db:
    restart: unless-stopped
  app:
    image: {image_app}
    restart: unless-stopped
    ports: !reset []
    environment:
      FP_OEFFENTLICHE_URL: {origin}
      FP_COOKIE_SECURE: "true"
      FP_KARTEN_KACHELN: ""
      FP_PROXY_IPS: {proxy_ip}
    networks:
      default: {{}}
      proxy:
        aliases: [fahrradausbildung]
""" + _PROXY_NETWORK),
    App("leseflux", 8, 3001, "/health/ready", ("app",), database_services=("postgres",),
        images={"app": "leseflux"},
        compose_env={"LESEFLUX_SECRETS_DIR": "leseflux"},
        secrets=(("leseflux/db-admin", "random:lese-db-admin"), ("leseflux/db-app", "random:lese-db-app"),
                 ("leseflux/jwt-key", "random:lese-jwt"),
                 ("leseflux/database-url", "url:postgresql://leseflux:{lese-db-app}@postgres:5432/leseflux"
                                           "?connection_limit=5&pool_timeout=3&connect_timeout=3")),
        migrations=(("node", "scripts/platform-migrate.cjs"), ("node", "scripts/content.cjs")),
        checks=(Check("GET", "/api/auth/me", 401), Check("GET", "/child/login", 200)),
        setup=("run", ("node", "scripts/setup-admin.cjs", "{email}", "{display}")),
        override="""services:
  postgres:
    restart: unless-stopped
  app:
    image: {image_app}
    restart: unless-stopped
    ports: !reset []
    environment:
      CORS_ORIGIN: {origin}
      COOKIE_SECURE: "true"
      TRUSTED_PROXY_IPS: {proxy_ip}
    networks:
      default: {{}}
      proxy:
        aliases: [leseflux]
""" + _PROXY_NETWORK),
    App("kompetenz-manager", 9, 8000, "/health/ready", ("app", "worker"),
        images={"app": "kompetenz-manager", "worker": "kompetenz-manager"},
        compose_env={"KM_SECRET_FILE": "kompetenz-key"},
        secrets=(("kompetenz-key", "random:kompetenz-key"),),
        migrations=(("python", "-m", "km_migrate"),),
        mail=True,
        checks=(Check("GET", "/login", 200), Check("GET", "/admin", 302), Check("GET", "/setup", 403)),
        setup=("run", ("python", "km_setup.py", "{name}")),
        # Fonts referenced by ODT templates for the PDF export (LibreOffice/fontconfig search path).
        host_dirs=("kompetenz-manager/fonts",),
        override="""services:
  app:
    image: {image_app}
    restart: unless-stopped
    ports: !reset []
    volumes:
      - {runtime}/kompetenz-manager/fonts:/usr/local/share/fonts:ro
    environment:
      DATABASE_URL: sqlite:////app/instance/schule.db
      SESSION_COOKIE_SECURE: "1"
      REMEMBER_COOKIE_SECURE: "1"
      APP_BASE_URL: {origin}
      TRUSTED_PROXY_IPS: {proxy_ip}
      MAIL_SERVER: {mail_host}
      MAIL_PORT: "{mail_port}"
      MAIL_SECURITY: none
      MAIL_FROM: {mail_from}
    networks:
      default: {{}}
      proxy:
        aliases: [kompetenz-manager]
  worker:
    image: {image_worker}
    restart: unless-stopped
    environment:
      DATABASE_URL: sqlite:////app/instance/schule.db
      APP_BASE_URL: {origin}
      MAIL_SERVER: {mail_host}
      MAIL_PORT: "{mail_port}"
      MAIL_SECURITY: none
      MAIL_FROM: {mail_from}
    networks: [default, proxy]
    # The upstream check imports the whole Flask app; on 0.5 CPU that takes ~5.7 s on a real
    # VPS and exceeded the upstream 5 s timeout, so 'up --wait' failed with a working worker.
    healthcheck:
      interval: 60s
      timeout: 30s
      start_period: 60s
      retries: 3
""" + _PROXY_NETWORK),
    App("abgen", 10, 3000, "/api/health/ready", ("app", "pdf"), database_services=("postgres",),
        images={"app": "abgen", "pdf": "abgen-pdf"},
        compose_env={"ABGEN_SECRETS_DIR": "abgen"},
        secrets=(("abgen/db-admin", "random:abgen-db-admin"), ("abgen/db-app", "random:abgen-db-app"),
                 ("abgen/database-url", "url:postgresql://abgen:{abgen-db-app}@postgres:5432/abgen")),
        migrations=(("node", "apps/server/dist/db/migrate.js"),),
        checks=(Check("GET", "/api/auth/me", 401),
                Check("POST", "/_platform/prepare-stop", 404, (("X-Abgen-Request", "1"),))),
        setup=("exec", ("node", "apps/server/dist/setup.js", "{email}", "{display}")),
        drain="worksheet",
        override="""services:
  app:
    image: {image_app}
    restart: unless-stopped
    ports: !reset []
    environment:
      WEB_ORIGIN: {origin}
      COOKIE_SECURE: "true"
      ALLOW_REGISTRATION: "false"
      DATABASE_URL_FILE: /run/secrets/database_url
      INTERNAL_WEB_ORIGIN: http://abgen-web:3000
      PDF_SERVICE_URL: http://pdf:3001
    networks:
      default:
        aliases: [abgen-web]
      proxy:
        aliases: [abgen]
  pdf:
    image: {image_pdf}
    restart: unless-stopped
    environment:
      WEB_ORIGIN: http://abgen-web:3000
  postgres:
    image: {postgres18}
    restart: unless-stopped
""" + _PROXY_NETWORK),
    App("fundkiste", 11, 8000, "/health/ready", ("app",),
        images={"app": "fundkiste"},
        migrations=(("python", "fk_migrate.py"),),
        checks=(Check("GET", "/api/items", 200), Check("GET", "/team/ungueltiger-schluessel", 404)),
        setup=("run", ("python", "fk_setup.py")),
        override="""services:
  app:
    image: {image_app}
    restart: unless-stopped
    ports: !reset []
    environment:
      FUNDKISTE_BASE_URL: {origin}
    networks:
      default: {{}}
      proxy:
        aliases: [fundkiste]
""" + _PROXY_NETWORK),
    App("schuleva", 12, 8000, "/health/ready", ("app",),
        images={"app": "schuleva"},
        compose_env={"SCHULEVA_SECRET_FILE": "schuleva-key"},
        secrets=(("schuleva-key", "random:schuleva-key"),),
        migrations=(("python", "-m", "app.migrate"),),
        checks=(Check("GET", "/admin/login", 200), Check("GET", "/admin/users", 303)),
        setup=("run", ("python", "-m", "app.cli", "create-admin")),
        override="""services:
  app:
    image: {image_app}
    restart: unless-stopped
    ports: !reset []
    environment:
      BASE_URL: {origin}
      PROXY_IPS: {proxy_ip}
    networks:
      default: {{}}
      proxy:
        aliases: [schuleva]
""" + _PROXY_NETWORK),
    App("schulkasse", 13, 8000, "/health/ready", ("app",),
        images={"app": "schulkasse"},
        compose_env={"SCHULKASSE_SECRET_FILE": "schulkasse-key"},
        # The key also encrypts the 2FA secrets: an import must carry the old one (altserver tool does).
        secrets=(("schulkasse-key", "random:schulkasse-key"),),
        migrations=(("python", "-m", "schulkasse", "migrate"),),
        checks=(Check("GET", "/anmelden", 200), Check("GET", "/", 302)),
        setup=("run", ("python", "-m", "schulkasse", "create-admin", "--benutzername", "{name}",
                       "--anzeigename", "{display}")),
        override="""services:
  app:
    image: {image_app}
    restart: unless-stopped
    ports: !reset []
    environment:
      SCHULKASSE_COOKIE_SECURE: "1"
      SCHULKASSE_PROXY_IPS: {proxy_ip}
    networks:
      default: {{}}
      proxy:
        aliases: [schulkasse]
""" + _PROXY_NETWORK),
    App("schulanmeldung", 14, 8000, "/health/ready", ("app", "worker"),
        images={"app": "schulanmeldung", "worker": "schulanmeldung"},
        compose_env={"SL_OFFICE_SECRET_FILE": "schulanmeldung-key"},
        secrets=(("schulanmeldung-key", "random:schulanmeldung-key"),),
        migrations=(("flask", "--app", "app", "db", "upgrade"),),
        mail=True,
        checks=(Check("GET", "/login", 200), Check("GET", "/", 302)),
        setup=("run", ("flask", "--app", "app", "create-admin", "--username", "{name}")),
        override="""services:
  app:
    image: {image_app}
    restart: unless-stopped
    ports: !reset []
    environment:
      SL_OFFICE_PUBLIC_BASE_URL: {origin}
      SL_OFFICE_PROXY_IPS: {proxy_ip}
      SL_OFFICE_MAIL_SERVER: {mail_host}
      SL_OFFICE_MAIL_PORT: "{mail_port}"
      SL_OFFICE_MAIL_USE_TLS: "0"
      SL_OFFICE_MAIL_FROM: {mail_from}
    networks:
      default: {{}}
      proxy:
        aliases: [schulanmeldung]
  worker:
    image: {image_worker}
    restart: unless-stopped
    environment:
      SL_OFFICE_PUBLIC_BASE_URL: {origin}
      SL_OFFICE_MAIL_SERVER: {mail_host}
      SL_OFFICE_MAIL_PORT: "{mail_port}"
      SL_OFFICE_MAIL_USE_TLS: "0"
      SL_OFFICE_MAIL_FROM: {mail_from}
    networks: [default, proxy]
""" + _PROXY_NETWORK),
]}

assert tuple(APPS) == APP_IDS and len({a.index for a in APPS.values()}) == len(APPS)
assert set(RELEASE_IMAGES) == set(APPS)
