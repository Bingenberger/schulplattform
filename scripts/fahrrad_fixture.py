"""Synthetic bicycle data and HTTP probes; never log credentials or station tokens."""
import json,re
from urllib.parse import urlencode
from tafel_fixture import Client
class Browser(Client):
    def form(self,path,values,expected=303):
        return self.call("POST",path,urlencode(values).encode(),{"Content-Type":"application/x-www-form-urlencoded"},expected)
    def page(self,path,expected=200):return self.call("GET",path,expected=expected).decode()
    def login(self,email,password="synthetic-password"):
        html=self.page("/anmelden")
        token=re.search(r'name="csrf" value="([^"]+)"',html)[1]
        self.form("/anmelden",{"email":email,"passwort":password,"csrf":token})
    def csrf(self):return re.search(r'name="csrf" value="([^"]+)"',self.page("/verwaltung/konto"))[1]
SEED=r"""
import json,uuid
from datetime import UTC,date,datetime,timedelta
from app.db import sitzungen
from app.modelle import Schule,Benutzer,Strecke,Posten,Item,Gruppe,Kind,Lauf,PostenToken
from app.sicherheit import neues_token,passwort_hashen
result=[]
with sitzungen().intern_kontext() as s:
    for index in range(2):
        school=Schule(name='Synthetic School '+str(index),kurzname='fixture-'+str(index));s.add(school);s.flush()
        user=Benutzer(schule_id=school.id,email='fixture'+str(index)+'@example.invalid',
            passwort_hash=passwort_hashen('synthetic-password'),rolle='schuladmin')
        track=Strecke(schule_id=school.id,name='Synthetic Track '+str(index))
        station=Posten(strecke=track,name='Synthetic station',position=1)
        item=Item(posten=station,kurzbezeichnung='Synthetic observation',position=1)
        group=Gruppe(schule_id=school.id,name='Synthetic Group '+str(index),schuljahr='2026/27')
        group.kinder.append(Kind(startnummer=7))
        s.add_all([user,track,group]);s.flush()
        eventrun=Lauf(schule_id=school.id,strecke_id=track.id,gruppe_id=group.id,datum=date.today())
        s.add(eventrun);s.flush()
        token=PostenToken(lauf_id=eventrun.id,posten_id=station.id,token=neues_token(),gueltig_bis=datetime.now(UTC)+timedelta(days=1))
        s.add(token);s.flush()
        result.append({'school':school.id,'user':user.id,'track':track.id,'station':station.id,'item':item.id,
            'group':group.id,'run':eventrun.id,'token':token.token,'email':user.email})
print(json.dumps(result))
"""
CONTRACT=r"""
import json
from sqlalchemy import text
from app.db import engine
with engine().connect() as c:
    tables=['schule','benutzer','strecke','posten','item','gruppe','kind','lauf','posten_token','ereignis']
    rows={t:[list(row) for row in c.execute(text('SELECT * FROM '+t+' ORDER BY 1'))] for t in tables}
    print(json.dumps(rows,default=str,sort_keys=True))
"""
