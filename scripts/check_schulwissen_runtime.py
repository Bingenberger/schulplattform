"""Execute focused production-image checks without a database or network."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
source = """
import os, unittest, fcntl
from unittest.mock import patch, MagicMock
os.environ.update(SW_DEBUG="true", SW_SECRET_KEY="synthetic-runtime-check-secret-000",
                  SW_DATABASE_URL="postgresql://synthetic:synthetic@127.0.0.1/unused",
                  DJANGO_SETTINGS_MODULE="schulwissen.einstellungen", SW_PROXY_IPS="192.0.2.10")
import django
django.setup()
from django.test import RequestFactory
from django.http import HttpResponse
from django.db import OperationalError
from kern import health
from kern.proxy import TrustedProxyHeaders
from kern.export_limit import limited_pdf


class ContractTests(unittest.TestCase):
    def test_liveness_does_not_use_database(self):
        with patch("kern.health.connection") as connection:
            self.assertEqual(health.live(RequestFactory().get("/")).status_code, 200)
            connection.cursor.assert_not_called()

    def test_database_outage_is_not_ready(self):
        with patch("kern.health.connection") as connection:
            connection.cursor.side_effect = OperationalError("synthetic outage")
            self.assertEqual(health.ready(RequestFactory().get("/")).status_code, 503)

    def test_pending_migrations_are_not_ready(self):
        with patch("kern.health.connection"), patch("kern.health.MigrationExecutor") as executor:
            executor.return_value.migration_plan.return_value = [("synthetic", False)]
            self.assertEqual(health.ready(RequestFactory().get("/")).status_code, 503)
            executor.return_value.migration_plan.return_value = []
            self.assertEqual(health.ready(RequestFactory().get("/")).status_code, 200)

    def test_only_explicit_proxy_can_set_forwarded_metadata(self):
        middleware = TrustedProxyHeaders(lambda request: HttpResponse(str(request.is_secure())))
        untrusted = RequestFactory().get("/", REMOTE_ADDR="192.0.2.11", HTTP_X_FORWARDED_PROTO="https")
        self.assertEqual(middleware(untrusted).content, b"False")
        trusted = RequestFactory().get("/", REMOTE_ADDR="192.0.2.10", HTTP_X_FORWARDED_PROTO="https")
        self.assertEqual(middleware(trusted).content, b"True")

    def test_pdf_slot_rejects_concurrent_export_and_releases(self):
        view = limited_pdf(lambda request, **kwargs: HttpResponse("pdf"))
        descriptor = os.open("/tmp/schulwissen-pdf.lock", os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            response = view(RequestFactory().get("/"), format="pdf")
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response["Retry-After"], "5")
            self.assertEqual(view(RequestFactory().get("/"), format="json").status_code, 200)
        finally:
            os.close(descriptor)
        self.assertEqual(view(RequestFactory().get("/"), format="pdf").status_code, 200)

unittest.main(verbosity=2)
"""
command = ["docker", "run", "--rm", "-i", "--network", "none", "--read-only",
           "--tmpfs", "/tmp:size=64m,mode=1777", "--memory", "512m",
           "schulwissen:0.1.0-dev", "python", "-"]
result = subprocess.run(command, input=source, capture_output=True, text=True, timeout=90)
log = "$ " + " ".join(command) + "\n" + result.stdout + result.stderr + f"\nexit_code={result.returncode}\n"
(ROOT / "docs/implementation/evidence/schulwissen-runtime.log").write_text(log)
print(log)
raise SystemExit(result.returncode)
