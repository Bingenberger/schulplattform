"""Shared synthetic Schulhelfer fixture and local HTTP/TLS assertions."""
import http.client
import json
import re
import socket
import ssl
from urllib.parse import urlencode

SEED = """from datetime import date,datetime,timedelta
from app.setup_admin import setup
setup('synthetic-admin','synthetic-admin-password')
from app.database import SessionLocal
from app.models import Klasse,Event,Station,Shift
with SessionLocal() as db:
    klasse=Klasse(label='Synthetic 3a',school_year='2050/51',active=True)
    event=Event(name='Synthetic Helferfest',event_date=date(2050,6,1),registration_deadline=datetime(2050,5,1),status='open',retention_weeks=4)
    db.add_all([klasse,event]);db.flush()
    station=Station(event_id=event.id,type='helper',name='Synthetic Station',sort_order=0)
    db.add(station);db.flush()
    db.add(Shift(station_id=station.id,start_time=datetime(2050,6,1,10),duration_min=60,required_count=1,sort_order=0))
    db.commit()
"""

CONTRACT = """import json
from sqlalchemy import text
from app.database import engine
with engine.connect() as db:
    tables=['admin_user','klasse','event','station','shift','participant','booking','donation','email_log']
    result={name:[dict(row) for row in db.execute(text('SELECT * FROM '+name+' ORDER BY id')).mappings()] for name in tables}
    # Never print token, hashes, usernames, email addresses or credentials.
    result={name:[{key:row[key] for key in row if key in ('id','participant_id','event_id','shift_id','klasse_id','station_id','success','kind')} for row in rows] for name,rows in result.items()}
    result['schema']=db.exec_driver_sql('SELECT version_num FROM alembic_version').scalar()
    result['version']=db.exec_driver_sql('PRAGMA user_version').scalar()
    result['foreignKeys']=db.exec_driver_sql('PRAGMA foreign_key_check').fetchall()
    print(json.dumps(result))
"""

class Client:
    def __init__(self, port, host="127.0.0.1", certificate=None):
        self.port, self.host, self.certificate, self.cookie = port, host, certificate, ""

    def request(self, path, method="GET", data=None, headers=None):
        if self.certificate:
            context = ssl.create_default_context(cafile=str(self.certificate))
            connection = http.client.HTTPSConnection(self.host, self.port, context=context, timeout=10)
            connection.sock = context.wrap_socket(socket.create_connection(("127.0.0.1", self.port), timeout=10),
                                                   server_hostname=self.host)
        else:
            connection = http.client.HTTPConnection(self.host, self.port, timeout=10)
        sent = {"Cookie": self.cookie, **(headers or {})}
        if data is not None:
            sent["Content-Type"] = "application/x-www-form-urlencoded"
            data = urlencode(data, doseq=True)
        try:
            connection.request(method, path, data, sent)
            response = connection.getresponse()
            content = response.read()
            cookie = response.getheader("Set-Cookie")
            if cookie:
                self.cookie = cookie.split(";")[0]
            return response.status, content, {key.lower(): value for key, value in response.getheaders()}
        finally:
            connection.close()

    def login(self):
        status, _, headers = self.request("/admin/login", "POST",
            {"username": "synthetic-admin", "password": "synthetic-admin-password"})
        assert status == 303
        assert "httponly" in headers.get("set-cookie", "").lower()
        if self.certificate:
            assert "secure" in headers["set-cookie"].lower()

    def csrf(self):
        status, body, _ = self.request("/admin")
        assert status == 200
        match = re.search(rb'name="csrf_token" value="([^"]+)"', body)
        assert match
        return match[1].decode()


def probe(client, origin, participant_path=None):
    client.cookie = ""
    assert client.request("/")[0] == 200
    assert client.request("/admin")[0] == 303
    client.login()
    assert client.request("/admin/classes/new", "POST", {"label": "Rejected", "school_year": "2050/51"})[0] == 400
    assert client.request("/admin/events/1/export.pdf")[0] == 200
    if participant_path:
        client.cookie = ""
        status, body, headers = client.request(participant_path)
        assert status == 200 and b"Synthetic Parent" in body
        assert headers.get("referrer-policy") == "no-referrer"
        assert headers.get("cache-control") == "private, no-store"
    return {"publicIndex": True, "anonymousAdminDenied": True, "localAdminLogin": True,
            "csrfRequired": True, "pdfExport": True, "parentLinkPublic": bool(participant_path)}
