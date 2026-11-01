#!/usr/bin/env python3
"""Run a loopback-only real pilot or synthetic RP; state is never overwritten."""
import os,sys,json,subprocess
from pathlib import Path
base=Path(__file__).resolve().parent;state=Path(os.environ.get('AUDIT_STATE','/tmp/schulplattform-audit/integration'));root=Path(os.environ.get('AUDIT_REPOS','/tmp/schulplattform-audit/repos'))
realm=json.loads((state/'realm.json').read_text());env=os.environ.copy();env.update(REQUESTS_CA_BUNDLE=str(state/'caddy-root.crt'),NO_PROXY='localhost,127.0.0.1,::1,.localhost',no_proxy='localhost,127.0.0.1,::1,.localhost')
if sys.argv[1]=='b':
 env['PYTHONPATH']=str(base);subprocess.run(['/tmp/schulplattform-audit/test-venv/bin/gunicorn','--bind','127.0.0.1:25442','--workers','1','client_b:app'],env=env,check=True);sys.exit()
c=next(c for c in realm['clients'] if c['clientId']=='schulwissen')
env.update(SW_DEBUG='false',SW_SECRET_KEY=(state/'session-secret').read_text(),SW_ALLOWED_HOSTS='wissen.audit.localhost',SW_DATABASE_URL='postgresql://postgres:audit-local-only@127.0.0.1:25432/audit',SW_OEFFENTLICHE_URL='https://wissen.audit.localhost:25443',SW_OIDC_ISSUER='https://login.audit.localhost:25443/realms/school-audit',SW_OIDC_CLIENT_ID='schulwissen',SW_OIDC_CLIENT_SECRET=c['secret'],SW_HSTS_TAGE='0',SW_COOKIE_SECURE='true',SW_SMTP_HOST='127.0.0.1',SW_SMTP_PORT='25425',SW_SMTP_TLS='false',SW_ABSENDER='audit@example.invalid')
repo=root/'schulwissen';python=repo/'.venv/bin/python'
if sys.argv[1]=='init':
 for args in [['manage.py','migrate','--noinput'],['manage.py','rollen_einrichten']]:subprocess.run([str(python),*args],cwd=repo,env=env,check=True)
 code='''import os,django;os.environ.setdefault("DJANGO_SETTINGS_MODULE","schulwissen.einstellungen");django.setup()
from kern.models import Nutzer,OIDCIdentitaet,Dokument,Dokumenttyp,ROLLE_LEHRKRAFT
from django.contrib.auth.models import Group
u,created=Nutzer.objects.get_or_create(email="audit@example.invalid",defaults={"anzeigename":"Synthetic existing teacher"})
if created:u.set_password("synthetic-local-only");u.save()
u.groups.add(Group.objects.get(name=ROLLE_LEHRKRAFT))
OIDCIdentitaet.objects.get_or_create(issuer="https://login.audit.localhost:25443/realms/school-audit",subject="audit-user-001",defaults={"nutzer":u,"erstellt_von":u})
t,_=Dokumenttyp.objects.get_or_create(schluessel="audit",defaults={"name":"Audit"})
d,_=Dokument.objects.get_or_create(schluessel="audit-owned",defaults={"titel":"Synthetic ownership proof","dokumenttyp":t,"erstellt_von":u})
assert d.erstellt_von_id==u.pk
print("Synthetic existing local account linked; ownership and teacher group retained")
'''
 subprocess.run([str(python),'-c',code],cwd=repo,env=env,check=True)
elif sys.argv[1]=='mail':
 subprocess.run([str(python),'manage.py','shell','-c','from django.core.mail import send_mail; print("accepted",send_mail("Synthetic relay test","No personal data.","audit@example.invalid",["recipient@example.invalid"]))'],cwd=repo,env=env,check=True)
elif sys.argv[1]=='a':
 subprocess.run([str(repo/'.venv/bin/gunicorn'),'--bind','127.0.0.1:25441','--workers','1','schulwissen.wsgi:anwendung'],cwd=repo,env=env,check=True)
else:raise SystemExit('init|a|b|mail')
