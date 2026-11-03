"""Synthetic abgen fixtures; passwords and capabilities never enter public evidence."""
from tafel_fixture import Client
class Browser(Client):
    def call(self,method,path,body=None,headers=None,expected=200,csrf=True):
        headers=dict(headers or {})
        if method not in ("GET","HEAD","OPTIONS") and csrf:headers.setdefault("X-Abgen-Request","1")
        try:return super().call(method,path,body,headers,expected)
        except AssertionError:raise AssertionError("abgen HTTP contract failed; private payload withheld") from None
    def login(self,email,password):
        return self.call("POST","/api/auth/login",{"email":email,"password":password})
SEED=r"""
const {createPostgresStorage}=await import('./apps/server/dist/repositories/postgres.js');
const {hashPassword}=await import('./apps/server/dist/auth/password.js');
const fs=await import('node:fs');
const storage=createPostgresStorage(fs.readFileSync('/run/secrets/database_url','utf8').trim(),'/app/data/assets');
try{
 if(!await storage.ready())throw Error('Explicit migration required');
 if(await storage.users.countUsers()!==0)throw Error('Synthetic fixture requires empty accounts');
 await storage.users.createUser({id:(await import('node:crypto')).randomUUID(),email:fixture.email,
 displayName:'Synthetic Admin',passwordHash:await hashPassword(fixture.password),role:'admin',
 mustChangePassword:false,active:true});
 console.log('Synthetic personal acceptance account created');
}finally{await storage.close();}
"""
