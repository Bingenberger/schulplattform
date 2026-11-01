#!/usr/bin/env python3
"""Prepare only synthetic local realm/config. No real account/SMTP credentials."""
import os,json,secrets
from pathlib import Path
state=Path(os.environ.get('AUDIT_STATE','/tmp/schulplattform-audit/integration'));state.mkdir(mode=0o700,parents=True,exist_ok=True)
if (state/'realm.json').exists():raise SystemExit('State exists: refusing to overwrite bootstrap/secrets')
realm={'realm':'school-audit','enabled':True,'sslRequired':'external','registrationAllowed':False,'accessTokenLifespan':60,'roles':{'realm':[{'name':'client-b-access'}]},'users':[{'id':'audit-user-001','username':'audit','enabled':True,'email':'audit@example.invalid','emailVerified':True,'firstName':'Audit','lastName':'User','credentials':[{'type':'password','value':'synthetic-local-only','temporary':False}],'realmRoles':['client-b-access']},{'id':'audit-denied-001','username':'denied','enabled':True,'email':'denied@example.invalid','emailVerified':True,'firstName':'Denied','lastName':'User','credentials':[{'type':'password','value':'synthetic-local-only','temporary':False}]}],'clients':[]}
for cid,origin,callback in [('schulwissen','https://wissen.audit.localhost:25443','/anmelden/nextcloud/callback'),('audit-client-b','https://client.audit.localhost:25443','/callback')]:
 realm['clients'].append({'clientId':cid,'enabled':True,'publicClient':False,'secret':secrets.token_urlsafe(32),'standardFlowEnabled':True,'directAccessGrantsEnabled':False,'redirectUris':[origin+callback],'webOrigins':[origin],'attributes':{'pkce.code.challenge.method':'S256'},'protocolMappers':[{'name':'app-roles','protocol':'openid-connect','protocolMapper':'oidc-usermodel-realm-role-mapper','config':{'claim.name':'audit_roles','jsonType.label':'String','multivalued':'true','id.token.claim':'true','access.token.claim':'true','userinfo.token.claim':'true'}}]})
(state/'realm.json').write_text(json.dumps(realm,indent=2));os.chmod(state/'realm.json',0o600)
(state/'session-secret').write_text(secrets.token_urlsafe(48));os.chmod(state/'session-secret',0o600)
print('Synthetic realm prepared; local credentials documented in prototype README. Generated client/session secrets not printed.')
