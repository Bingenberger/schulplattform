"""Synthetic Kompetenz HTTP/forms and data fixture; no real pupils or email."""
import re,json
from urllib.parse import urlencode
from tafel_fixture import Client
class Browser(Client):
    def page(self,path):
        return self.call('GET',path).decode()
    def csrf(self,path='/login'):
        return re.search(r'name="_csrf_token"\s+value="([^"]+)"',self.page(path))[1]
    def form(self,path,data=None,expected=302,csrf=True,headers=None):
        data=dict(data or {})
        if csrf and '_csrf_token' not in data:data['_csrf_token']=self.csrf()
        headers={'Content-Type':'application/x-www-form-urlencoded',**(headers or {})}
        return self.call('POST',path,urlencode(data).encode(),headers,expected)
    def login(self,username,password='synthetic-teacher-123'):
        token=self.csrf()
        return self.form('/login',{'username':username,'password':password,'_csrf_token':token})
SEED=r"""
from app import app
from extensions import db
from models import User,Schueler,UserKlassenzuordnung,Bogen,Item,Beobachtung,SystemKonfiguration,Notification
from werkzeug.security import generate_password_hash
from pathlib import Path
from PIL import Image
import json
with app.app_context():
 users=[];students=[]
 for index,klasse in enumerate(('3a','1b')):
  user=User(username='fixture-teacher'+str(index),password_hash=generate_password_hash('synthetic-teacher-123'),
   role='teacher',email='teacher'+str(index)+'@example.invalid',mail_takt='sofort')
  student=Schueler(vorname='Synthetic',nachname='Child'+str(index),klasse=klasse,jahrgang=3 if index==0 else 1)
  db.session.add_all([user,student]);db.session.flush()
  db.session.add(UserKlassenzuordnung(user_id=user.id,klasse=klasse,rolle='klassenleitung'))
  users.append(user.id);students.append(student.id)
 bogen=Bogen(titel='Synthetic Observation');db.session.add(bogen);db.session.flush()
 item=Item(bogen_id=bogen.id,bereich='Reading',text='Synthetic competence');db.session.add(item);db.session.flush()
 protected=Path(app.config['PROTECTED_UPLOAD_FOLDER']);protected.mkdir(parents=True,exist_ok=True)
 Image.new('RGB',(16,16),'blue').save(protected/'synthetic.png')
 Image.new('RGB',(16,16),'green').save(Path(app.instance_path)/'schullogo.png')
 observation=Beobachtung(schueler_id=students[0],item_id=item.id,wert=3,kommentar='Synthetic preserved observation',foto_pfad='synthetic.png')
 db.session.add(observation)
 db.session.add(SystemKonfiguration(schuljahr='2026/2027'))
 db.session.commit()
 print(json.dumps({'users':users,'students':students,'observation':observation.id,'item':item.id}))
"""
CONTRACT=r"""
from app import app
from extensions import db
from sqlalchemy import inspect,text
import json
with app.app_context():
 names=set(inspect(db.engine).get_table_names())-{'runtime_session','auth_rate_limit','km_runtime_state'}
 result={}
 for name in sorted(names):
  rows=db.session.execute(text('SELECT * FROM "'+name+'" ORDER BY 1')).mappings().all()
  result[name]=[dict(row) for row in rows]
 print(json.dumps(result,default=str))
"""
