#!/usr/bin/env python3
"""Real browser proof on local test stack; outputs only sanitized assertions."""
import json,os,time,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
out=[]
def record(name,passed,detail=''):
 out.append({'test':name,'passed':passed,'detail':detail});print(json.dumps(out[-1]))
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--no-proxy-server'])
 context=browser.new_context(ignore_https_errors=True);page=context.new_page()
 page.goto('https://wissen.audit.localhost:25443/anmelden/nextcloud')
 page.locator('#username').fill('audit');page.locator('#password').fill('synthetic-local-only');page.locator('#kc-login').click();page.wait_for_url('https://wissen.audit.localhost:25443/**',timeout=60000)
 record('A native OIDC login', '/anmelden' not in page.url, 'Schulwissen callback completed through Caddy/Keycloak')
 page.goto('https://client.audit.localhost:25443/login');page.wait_for_url('**/api/private',timeout=60000)
 record('A -> B SSO without entering password again',page.locator('body').inner_text().find('audit-user-001')>=0,'B is synthetic Flask/Authlib RP, not second real app')
 response=page.request.get('https://client.audit.localhost:25443/public');record('B public route',response.status==200)
 # End IdP session through a top-level RP-initiated logout, without modifying a real account.
 page.goto('https://login.audit.localhost:25443/realms/school-audit/protocol/openid-connect/logout')
 button=page.locator('#kc-logout')
 if button.count():button.click();page.wait_for_timeout(1000)
 response=page.request.get('https://wissen.audit.localhost:25443/')
 record('A local session survives IdP logout (observed gap)',response.status==200,'200 after IdP logout; no implemented global revocation claim')
 denied=browser.new_context(ignore_https_errors=True);d=denied.new_page()
 r=d.request.get('https://client.audit.localhost:25443/api/private');record('direct B API without session denied',r.status==401)
 d.goto('https://client.audit.localhost:25443/login');d.locator('#username').fill('denied');d.locator('#password').fill('synthetic-local-only');d.locator('#kc-login').click();d.wait_for_url('https://client.audit.localhost:25443/callback**',timeout=60000)
 record('B user without grant rejected',d.locator('body').inner_text().find('Forbidden')>=0)
 r=d.request.get('https://client.audit.localhost:25443/api/private');record('B direct API after rejected login denied',r.status==401)
 # The imported realm has 60 second access tokens. No wait-based capability claim for A.
 time.sleep(65)
 r=page.request.get('https://client.audit.localhost:25443/api/private');record('B local session ends by ID-token expiry',r.status==401)
 browser.close()
Path(os.environ.get('AUDIT_RESULT','/tmp/schulplattform-audit/integration/browser-results.json')).write_text(json.dumps(out,indent=2))
assert all(x['passed'] for x in out)
