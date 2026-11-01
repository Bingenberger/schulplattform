"""Synthetic second RP, NOT an app integration or production identity service."""
import os,json,time,secrets
from pathlib import Path
from flask import Flask,session,redirect,url_for,abort,jsonify,request
from authlib.integrations.flask_client import OAuth
state=Path(os.environ.get('AUDIT_STATE','/tmp/schulplattform-audit/integration'))
realm=json.loads((state/'realm.json').read_text());config=next(c for c in realm['clients'] if c['clientId']=='audit-client-b')
issuer='https://login.audit.localhost:25443/realms/school-audit'
app=Flask(__name__);app.secret_key=(state/'session-secret').read_text();app.config.update(SESSION_COOKIE_NAME='audit_client_b',SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SECURE=True,SESSION_COOKIE_SAMESITE='Lax')
oauth=OAuth(app);oidc=oauth.register('idp',client_id=config['clientId'],client_secret=config['secret'],server_metadata_url=issuer+'/.well-known/openid-configuration',client_kwargs={'scope':'openid profile email','code_challenge_method':'S256'})
@app.get('/public')
def public():return 'synthetic public client route'
@app.get('/login')
def login():
 session['nonce']=secrets.token_urlsafe(32)
 return oidc.authorize_redirect('https://client.audit.localhost:25443/callback',nonce=session['nonce'])
@app.get('/callback')
def callback():
 token=oidc.authorize_access_token(claims_options={'iss':{'essential':True,'value':issuer}});claims=token['userinfo']
 if claims.get('iss')!=issuer or claims.get('nonce')!=session.pop('nonce',None):abort(403)
 if 'client-b-access' not in claims.get('audit_roles',[]):abort(403)
 session.clear();session.update(sub=claims['sub'],exp=claims['exp'],csrf=secrets.token_urlsafe(32))
 return redirect('/api/private')
@app.get('/api/private')
def private():
 if not session.get('sub') or session.get('exp',0)<=time.time():abort(401)
 return jsonify(subject=session['sub'],test_client=True)
@app.post('/logout')
def logout():
 if not secrets.compare_digest(request.headers.get('X-CSRF-Token',''),session.get('csrf','unavailable')):abort(403)
 session.clear();return '',204
