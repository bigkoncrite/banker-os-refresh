# Stage 3: PSC snapshot -> owners for targets, parents of holding companies, owner portfolios
import zipfile, json, re, glob, os, shutil
from multiprocessing import Pool
from concurrent.futures import ThreadPoolExecutor
from common import *
S=json.load(open(P('sources.json'))); os.makedirs(P('psc'),exist_ok=True)
def dl(f): download('https://download.companieshouse.gov.uk/'+f,P('psc',f),timeout=1800)
with ThreadPoolExecutor(4) as ex: list(ex.map(dl,S['psc']['files']))
log('PSC downloaded',len(S['psc']['files']))
def regnorm(r):
    r=re.sub(r'[^0-9A-Z]','',str(r or '').upper()); m=re.match(r'^([A-Z]{2})?(\d+)$',r)
    return ((m[1] or '')+m[2].zfill(8-len(m[1] or ''))) if m else None
def okey(name,dob):
    n=re.sub(r'^(MR|MRS|MS|MISS|DR|PROF|SIR|DAME|LADY|LORD)\.? ','',re.sub(r'[^A-Z ]','',str(name).upper())).split()
    return (n[0]+' '+n[-1] if n else '')+'|'+(f"{dob['year']}-{dob.get('month',0):02d}" if dob else '')
def rec(cn,d): return {'cn':cn,'kind':d.get('kind',''),'name':d.get('name',''),'dob':d.get('date_of_birth'),'on':d.get('notified_on'),'noc':d.get('natures_of_control',[]),'reg':(d.get('identification') or {}).get('registration_number')}
T=None; PAR=None; OWN=None
def pass1(path):
    out=[]; z=zipfile.ZipFile(path)
    with z.open(z.namelist()[0]) as f:
        for line in f:
            cn=line[19:27].decode('ascii','ignore')
            if cn not in T: continue
            d=json.loads(line).get('data',{})
            if d.get('ceased_on') or 'statement' in d.get('kind','') or 'exemption' in d.get('kind',''): continue
            out.append(rec(cn,d))
    return out
def pass2(path):
    par=[]; cnt={}; z=zipfile.ZipFile(path)
    with z.open(z.namelist()[0]) as f:
        for line in f:
            if b'"ceased_on"' in line: continue
            cn=line[19:27].decode('ascii','ignore'); isp=cn in PAR
            if not isp and b'individual-person' not in line: continue
            d=json.loads(line).get('data',{})
            if isp and 'statement' not in d.get('kind',''): par.append(rec(cn,d))
            if d.get('kind','').startswith('individual') and d.get('date_of_birth'):
                k=okey(d.get('name',''),d['date_of_birth'])
                if k in OWN: cnt.setdefault(k,set()).add(cn)
    return par,{k:list(v) for k,v in cnt.items()}
def init1(t):
    global T; T=t
def init2(p,o):
    global PAR,OWN; PAR=p; OWN=o
files=sorted(glob.glob(P('psc','*.zip')))
with Pool(8,initializer=init1,initargs=(set(json.load(open(P('targets.json')))),)) as pool: res=pool.map(pass1,files)
ps=[x for r in res for x in r]; json.dump(ps,open(P('psc_all.json'),'w'))
parents=set(filter(None,(regnorm(p.get('reg')) for p in ps if p.get('reg'))))
owners=set(okey(p['name'],p['dob']) for p in ps if p['kind'].startswith('individual') and p.get('dob'))
with Pool(8,initializer=init2,initargs=(parents,owners)) as pool: res=pool.map(pass2,files)
json.dump([x for r in res for x in r[0]],open(P('psc_parents.json'),'w'))
cnt={}
for r in res:
    for k,v in r[1].items(): cnt.setdefault(k,set()).update(v)
json.dump({k:len(v) for k,v in cnt.items()},open(P('owner_portfolio.json'),'w'))
shutil.rmtree(P('psc')); log('PSC records',len(ps),'parents',len(parents))
