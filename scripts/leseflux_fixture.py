"""Synthetic Leseflux HTTP client; cookies and child capabilities stay private."""
from tafel_fixture import Client
class Browser(Client):
    def call(self,method,path,body=None,headers=None,expected=200,csrf=True):
        headers=dict(headers or {})
        if csrf and method not in ("GET","HEAD","OPTIONS"):headers.setdefault("X-Leseflux-Request","1")
        return super().call(method,path,body,headers,expected)
ADMIN=r"""
const {load}=require('./scripts/credentials.cjs');load(['DATABASE_URL']);
const {PrismaClient}=require('@prisma/client'),argon2=require('argon2');
const p=new PrismaClient({log:[]});
(async()=>{const user=await p.user.create({data:{role:'ADMIN',email:'fixture-admin@example.invalid',
displayName:'Synthetic Admin',passwordHash:await argon2.hash('synthetic-admin-123')}});
console.log(JSON.stringify({id:user.id}));})().finally(()=>p.$disconnect()).catch(()=>process.exitCode=1);
"""
CONTRACT=r"""
const {load}=require('./scripts/credentials.cjs');load(['DATABASE_URL']);
const {PrismaClient}=require('@prisma/client');const p=new PrismaClient({log:[]});
(async()=>{const tables=['User','Class','Group','GroupMember','UserProgress','Diagnostic','DiagnosticItem','DiagnosticResult',
'DiagnosticAnswer','Text','TextQuestion','FlashWord','ClozeTemplate','ClozeGap','SessionTemplate','TrainingSession','ExerciseRun','AuditLog','SystemSetting'];
const rows={};
for(const name of tables)rows[name]=await p.$queryRawUnsafe('SELECT * FROM "'+name+'" ORDER BY 1');
console.log(JSON.stringify(rows));})().finally(()=>p.$disconnect()).catch(()=>process.exitCode=1);
"""
