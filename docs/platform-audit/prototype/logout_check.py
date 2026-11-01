from playwright.sync_api import sync_playwright
import json
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--no-proxy-server']);c=b.new_context(ignore_https_errors=True);a=c.new_page()
 a.goto('https://wissen.audit.localhost:25443/anmelden/nextcloud');a.locator('#username').fill('audit');a.locator('#password').fill('synthetic-local-only');a.locator('#kc-login').click();a.wait_for_url('https://wissen.audit.localhost:25443/**')
 a.goto('https://login.audit.localhost:25443/realms/school-audit/protocol/openid-connect/logout')
 if a.locator('#kc-logout').count():a.locator('#kc-logout').click()
 a.goto('https://client.audit.localhost:25443/login');a.locator('#username').wait_for()
 r=a.request.get('https://wissen.audit.localhost:25443/',max_redirects=0)
 result={'idp_requires_password_again':True,'schulwissen_still_authenticated':r.status==200,'status':r.status}
 print(json.dumps(result));assert r.status==200;b.close()
