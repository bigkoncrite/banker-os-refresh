# Stage 6: Companies House API for directors (where owner age unknown) and unmatched owners
import json, time, re, os, base64, urllib.request, urllib.parse, threading
from concurrent.futures import ThreadPoolExecutor
from common import P, log
from norm import norm
KEY=os.environ.get('CH_API_KEY','').strip()
if not KEY: log('no CH_API_KEY; skipping API stage'); raise SystemExit
AUTH='Basic '+base64.b64encode((KEY+':').encode()).decode()
MAX_OFF=int(os.environ.get('MAX_OFFICERS','3500')); MAX_MATCH=int(os.environ.get('MAX_MATCH','500'))
last=[0.0]; LK=threading.Lock(); calls=[0]
def get(path):
    for attempt in range(5):
        with LK:
            w=0.505-(time.time()-last[0])
            if w>0: time.sleep(w)
            last[0]=time.time(); calls[0]+=1
        try:
            req=urllib.request.Request('https://api.company-information.service.gov.uk'+path,headers={'Authorization':AUTH})
            with urllib.request.urlopen(req,timeout=30) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code==404: return None
            if e.code==401: raise SystemExit('Companies House API key rejected (401)')
            time.sleep(60 if e.code==429 else 3)
        except Exception: time.sleep(3)
    return None
U=json.load(open(P('universe.json'))); F=U['F']; R=[dict(zip(F,r)) for r in U['rows']]
need=[r['cn'] for r in R if r.get('cn') and r.get('oAge') is None and r.get('own')!='Group-owned'][:MAX_OFF]
unm=[r for r in R if not r.get('cn') and r.get('own') in ('Unmatched','Company')][:MAX_MATCH]
out={'officers':{},'match':{}}
def officers(cn):
    d=get(f'/company/{cn}/officers?items_per_page=35')
    if not d: return []
    return [{'n':o.get('name'),'dob':o.get('date_of_birth'),'on':o.get('appointed_on'),'role':o.get('officer_role')} for o in d.get('items',[]) if not o.get('resigned_on') and o.get('officer_role') in ('director','llp-member','llp-designated-member','member')]
def job(cn): out['officers'][cn]=officers(cn)
with ThreadPoolExecutor(4) as ex: list(ex.map(job,need))
def mjob(r):
    q=re.sub(r'\bT/A\b.*$','',r['prov'] or '',flags=re.I)
    s=get('/search/companies?'+urllib.parse.urlencode({'q':q,'items_per_page':10})) or {}
    items=[it for it in s.get('items',[]) if it.get('company_status')=='active']
    best=next((it for it in items if norm(it.get('title'))==norm(q)),None) or next((it for it in items if norm(q) and norm(q) in norm(it.get('title'))),None)
    rec=None
    if best:
        cn=best['company_number']; prof=get(f'/company/{cn}') or {}
        psc=get(f'/company/{cn}/persons-with-significant-control?items_per_page=25') or {}
        rec={'cn':cn,'exact':norm(best.get('title'))==norm(q),'prof':{k:prof.get(k) for k in ['company_name','company_status','date_of_creation','sic_codes','accounts','confirmation_statement','registered_office_address']},
             'psc':[{'kind':p.get('kind'),'name':p.get('name'),'dob':p.get('date_of_birth'),'on':p.get('notified_on'),'noc':p.get('natures_of_control',[])} for p in psc.get('items',[]) if not p.get('ceased_on')],'officers':officers(cn)}
    out['match'][r['id']]=rec
with ThreadPoolExecutor(4) as ex: list(ex.map(mjob,unm))
json.dump(out,open(P('api_out.json'),'w')); log('API calls',calls[0],'officers',len(need),'match',len(unm))
