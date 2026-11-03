"""Local synthetic ticket-sale fixtures, verified HTTP/TLS and private capabilities."""
import http.client
import json
from pathlib import Path
import re
import socket
import ssl
from urllib.parse import urlencode

GEO={"type":"FeatureCollection","features":[
    {"type":"Feature","properties":{"id":"one","name":"Synthetic One","strassen":["Synthetic Street"],"max":1},
     "geometry":{"type":"MultiLineString","coordinates":[[[7.0,50.0],[7.01,50.01]]]}},
    {"type":"Feature","properties":{"id":"two","name":"Synthetic Two","strassen":["Synthetic Lane"],"max":1},
     "geometry":{"type":"MultiLineString","coordinates":[[[7.01,50.0],[7.02,50.01]]]}}
]}

MAP_SOURCE="import json;from pathlib import Path;path=Path('/data/maps/bezirke.geojson');path.write_text("+repr(json.dumps(GEO))+")"
CONTRACT="""import json,sqlite3,hashlib
from pathlib import Path
db=sqlite3.connect('/data/losverkauf.db')
data={'version':db.execute('PRAGMA user_version').fetchone()[0],
      'foreignKeys':db.execute('PRAGMA foreign_key_check').fetchall(),
      'registrations':db.execute('SELECT id,bezirk_id,status FROM anmeldungen ORDER BY id').fetchall(),
      'persons':db.execute('SELECT id,anmeldung_id,pos FROM personen ORDER BY id').fetchall(),
      'mail':db.execute('SELECT anmeldung_id,art,ok FROM mail_log ORDER BY id').fetchall(),
      'queue':db.execute('SELECT id,anmeldung_id,art,status FROM mail_outbox ORDER BY id').fetchall(),
      'capabilityHashes':[(r[0],hashlib.sha256(r[1].encode()).hexdigest()) for r in db.execute('SELECT id,edit_token FROM anmeldungen ORDER BY id')],
      'mapSha256':hashlib.sha256(Path('/data/maps/bezirke.geojson').read_bytes()).hexdigest()}
print(json.dumps(data))
"""

class Client:
    def __init__(self,port,host="127.0.0.1",certificate=None):
        self.port,self.host,self.certificate,self.cookie=port,host,certificate,""
    def request(self,path,method="GET",data=None,payload=None,headers=None):
        if self.certificate:
            context=ssl.create_default_context(cafile=str(self.certificate))
            connection=http.client.HTTPSConnection(self.host,self.port,context=context,timeout=15)
            connection.sock=context.wrap_socket(socket.create_connection(("127.0.0.1",self.port),timeout=15),server_hostname=self.host)
        else:
            connection=http.client.HTTPConnection(self.host,self.port,timeout=15)
        sent={"Cookie":self.cookie,**(headers or {})}
        if payload is not None:
            data=json.dumps(payload)
            sent["Content-Type"]="application/json"
        elif data is not None:
            data=urlencode(data,doseq=True)
            sent["Content-Type"]="application/x-www-form-urlencoded"
        try:
            connection.request(method,path,data,sent)
            response=connection.getresponse()
            body=response.read()
            cookie=response.getheader("Set-Cookie")
            if cookie: self.cookie=cookie.split(";")[0]
            return response.status,body,{key.lower():value for key,value in response.getheaders()}
        finally:
            connection.close()
    def csrf(self,path="/admin/login"):
        status,body,_=self.request(path)
        assert status==200
        found=re.search(rb'name="csrf-token" content="([^"]+)"',body)
        assert found
        return found[1].decode()
    def parent(self,token,edit=None):
        path="/?t="+token+("&edit="+edit if edit else "")
        assert self.request(path)[0]==302
        return self.csrf("/")
    def login(self):
        nonce=self.csrf()
        status,_,headers=self.request("/admin/login","POST",
            data={"username":"synthetic.operator","pw":"synthetic-password","csrf_token":nonce})
        assert status==302 and "httponly" in headers.get("set-cookie","").lower()
        if self.certificate: assert "secure" in headers["set-cookie"].lower()
        return nonce

def register(client,nonce,district="one",name="Synthetic Parent"):
    return client.request("/api/anmeldung","POST",payload={"bezirk_id":district,
        "personen":[{"name":name,"klasse":"3a","telefon":"0123456789","email":"synthetic@example.invalid"}]},
        headers={"X-CSRF-Token":nonce})

def probe(client,parent_token,origin,capability=None):
    client.cookie=""
    assert client.request("/")[0]==403
    assert client.request("/admin")[0]==302
    nonce=client.parent(parent_token,capability)
    if capability:
        data=json.loads(client.request("/api/bezirke")[1])
        assert any(row["edit_token"]==capability for row in data["eigene"])
    assert client.request("/api/anmeldung","POST",payload={})[0]==403
    nonce=client.login()
    assert client.request("/admin/bezirk/one","POST",data={})[0]==403
    page=client.request("/admin",headers={"X-Forwarded-Host":"spoof.example.invalid","X-Forwarded-Proto":"http"})
    assert page[0]==200 and (origin+"/?t=").encode() in page[1]
    assert client.request("/admin/liste.pdf")[0]==200
    assert client.request("/admin/export.csv")[0]==200
    assert client.request("/static/vendor/leaflet/leaflet.js")[0]==200
    return {"parentTokenRequired":True,"personalAdminLogin":True,"csrfRequired":True,
            "existingCapabilityOwnership":bool(capability),"canonicalParentLink":True,
            "pdfAndCsv":True,"localLeaflet":True}
