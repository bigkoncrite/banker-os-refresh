# Stage 4: latest filed accounts (iXBRL bulk, last 12 months) for target companies
import zipfile, re, json, os, subprocess
from concurrent.futures import ThreadPoolExecutor
from common import *
S=json.load(open(P('sources.json'))); T=set(json.load(open(P('targets.json')))); os.makedirs(P('acc'),exist_ok=True)
TAGS={'TurnoverRevenue':'turnover','Revenue':'turnover','AverageNumberEmployeesDuringPeriod':'emp','NetAssetsLiabilities':'na','Equity':'eq','CashBankOnHand':'cash','OperatingProfitLoss':'op','ProfitLoss':'pl'}
ctx_re=re.compile(r'<xbrli:context[^>]*id="([^"]+)"[^>]*>(.*?)</xbrli:context>',re.S|re.I)
nf_re=re.compile(r'<ix:nonFraction([^>]*)>(.*?)</ix:nonFraction>',re.S|re.I)
def attr(a,k):
    m=re.search(r'\b'+k+r'="([^"]*)"',a); return m.group(1) if m else None
def parse(txt):
    ctx={}
    for cid,body in ctx_re.findall(txt):
        if re.search(r'segment|explicitMember|typedMember',body,re.I): continue
        d=re.findall(r'<xbrli:(?:endDate|instant)>\s*([0-9-]{10})',body)
        if d: ctx[cid]=max(d)
    best={}
    for a,v in nf_re.findall(txt):
        nm=(attr(a,'name') or '').split(':')[-1]
        if nm not in TAGS: continue
        c=attr(a,'contextRef')
        if c not in ctx: continue
        raw=re.sub(r'<[^>]+>','',v).strip().replace(',','').replace(' ','')
        try: num=0.0 if raw in ('','-') else float(raw)
        except: continue
        sc=attr(a,'scale'); num*=10**int(sc) if sc and sc.lstrip('-').isdigit() else 1
        if attr(a,'sign')=='-': num=-num
        k=TAGS[nm]; d=ctx[c]
        if k not in best or d>best[k][0]: best[k]=(d,num)
    if not best: return None
    end=max(d for d,_ in best.values())
    return {'end':end,**{k:v for k,(d,v) in best.items() if d==end}}
def month(f):
    p=P('acc',f)
    try:
        download('https://download.companieshouse.gov.uk/'+f,p,timeout=3000)
        out={}; z=zipfile.ZipFile(p)
        for n in z.namelist():
            parts=os.path.basename(n).split('_')
            if len(parts)<4 or parts[2] not in T: continue
            try: r=parse(z.read(n).decode('utf-8','ignore'))
            except Exception: r=None
            if r: out[parts[2]]=r
        json.dump(out,open(p+'.json','w')); log('accounts',f,len(out))
    except Exception as e: log('accounts FAILED',f,e)
    finally:
        try: os.remove(p)
        except: pass
with ThreadPoolExecutor(3) as ex: list(ex.map(month,S['acc']['files']))
