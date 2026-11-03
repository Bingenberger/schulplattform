"""Synthetic schulwissen HTTP/media fixture, with native document and area rights."""
from urllib.parse import urlencode
from tafel_fixture import Client
class Browser(Client):
    def login(self,email,password):
        self.call("GET","/anmelden")
        self.call("POST","/anmelden",urlencode({"username":email,"password":password,
            "csrfmiddlewaretoken":self.cookies["csrftoken"]}).encode(),
            {"Content-Type":"application/x-www-form-urlencoded",
             "Origin":("https://"+self.host if self.ca else "http://127.0.0.1")+":"+str(self.port)},302)
    def form(self,path,data=None,expected=302,csrf=True,origin=None):
        payload=dict(data or {})
        if csrf:
            self.call("GET","/anmelden",expected=302 if "sessionid" in self.cookies else 200)
            payload["csrfmiddlewaretoken"]=self.cookies["csrftoken"]
        return self.call("POST",path,urlencode(payload).encode(),
            {"Content-Type":"application/x-www-form-urlencoded","Origin":origin or
             (("https://"+self.host if self.ca else "http://127.0.0.1")+":"+str(self.port))},expected)
SEED=r"""
import os,json
os.environ.setdefault('DJANGO_SETTINGS_MODULE','schulwissen.einstellungen')
import django
django.setup()
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.db import transaction
from eintragstypen.dienste import Rohsatz,pruefen,speichern
from kern.models import Nutzer,Dokumenttyp,Dokument,Wissensbereich,Zugangsregel,Anhang,ROLLE_ADMINISTRATION,ROLLE_LEHRKRAFT
with transaction.atomic():
 users=[]
 for index,role in enumerate([ROLLE_ADMINISTRATION,ROLLE_LEHRKRAFT,ROLLE_LEHRKRAFT]):
  user=Nutzer.objects.create_user(email=fixture['prefix']+str(index)+'@example.invalid',
      anzeigename='Synthetic Restore '+str(index),password=fixture['password'])
  user.groups.add(Group.objects.get(name=role))
  if index==0:
   user.is_staff=True;user.is_superuser=True;user.save(update_fields=['is_staff','is_superuser'])
  users.append(user)
 typ=Dokumenttyp.objects.create(schluessel=fixture['prefix'],name='Synthetic restore type',eintragstypen=['grundlagenkapitel'])
 bereich=Wissensbereich.objects.create(schluessel=fixture['prefix'],name='Synthetic private area',kollegiumsweit=False)
 doc=Dokument.objects.create(schluessel=fixture['prefix'],titel='Synthetic protected restore document',
      dokumenttyp=typ,bereich=bereich,kollegiumsweit=False,erstellt_von=users[1])
 Zugangsregel.objects.create(bereich=bereich,nutzer=users[1],lesen=True,bearbeiten=True)
 Zugangsregel.objects.create(dokument=doc,nutzer=users[1],lesen=True,bearbeiten=True)
 entry=speichern(doc,pruefen(doc,Rohsatz(kennung='S-01',eintragstyp='grundlagenkapitel',
      titel='Synthetic preserved knowledge',daten={'text':'Synthetic private restore content'})),nutzer=users[1])
 attachment=Anhang.objects.create(dokument=doc,eintrag=entry,datei=ContentFile(b'Synthetic private attachment bytes\n',name='synthetic.txt'),
      dateiname='synthetic.txt',mimetype='text/plain',erstellt_von=users[1])
 print(json.dumps({'users':[{'id':u.pk,'email':u.email,'roleIds':list(u.groups.values_list('id',flat=True))} for u in users],
  'documentId':doc.pk,'documentSlug':doc.schluessel,'entryId':entry.pk,'attachmentId':attachment.pk,
  'mediaPath':attachment.datei.name,'areaId':bereich.pk}))
"""
