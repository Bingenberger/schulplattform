#!/usr/bin/env python3
"""Output synthetic identities and explicit workload plans, never real accounts."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--adults',type=int,default=24);p.add_argument('--children',type=int,default=400);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
people=[{'external_id':f'audit-adult-{i:03}','email':f'adult-{i:03}@example.invalid','name':f'Testlehrkraft {i}'} for i in range(a.adults)]+[{'external_id':f'audit-child-{i:03}','display_name':f'Testkind {i}','class':f'audit-{i//25}'} for i in range(a.children)]
(a.output/'identities.json').write_text(json.dumps(people,indent=2))
plan={'origins':{'schulwissen':'https://wissen.test','leseflux':'https://lesen.test','gswb':'https://woerter.test','schulhelfer':'https://helfer.test'},'think_seconds':[4,8],'actions':[{'name':'wissen-read','app':'schulwissen','method':'GET','path':'/','weight':4,'header_env':{'Cookie':'AUDIT_SW_COOKIE'},'expected':[200]},{'name':'lesen-health','app':'leseflux','method':'GET','path':'/api/health','weight':1,'expected':[200]},{'name':'woerter-read','app':'gswb','method':'GET','path':'/api/word/Auditwort0000','weight':3,'expected':[200]},{'name':'helfer-public','app':'schulhelfer','method':'GET','path':'/','weight':2,'expected':[200]}]}
(a.output/'read-plan.json').write_text(json.dumps(plan,indent=2))
print('Synthetic fixture specifications generated. App import/mapping and authenticated write scenarios require app adapters; health route is not reading training work.')
