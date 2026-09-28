# Stage 7: chunk for the book, diff against last month, write the publish plan
import json, os, glob, math, collections, datetime as dt, shutil
from common import P, log
TODAY=dt.date.today(); GEN='g'+TODAY.strftime('%Y%m%d')
U=json.load(open(P('universe.json'))); F=U['F']
def cln(v): return None if isinstance(v,float) and (math.isnan(v) or math.isinf(v)) else v
R=[{f:cln(v) for f,v in zip(F,r)} for r in U['rows']]
HEAVY=['kind','q','sites','dirs','sic','chn','chgT','pSince','ni','web','brand','turn','op','evb','la','ult','corp','regions','url']
L=[f for f in F if f not in ('kind','q','sites','dirs','sic','chn','chgT','pSince','ni','web','brand','turn','op','evb','ult','corp','url')]
D=['id']+HEAVY
def lean(r):
    x=dict(r); x['la']=(r.get('la') or '')[:60] or None; x['regions']=(r.get('regions') or '')[:80] or None
    for k in ('emp','na','cash'):
        if x.get(k) is not None: x[k]=round(x[k])
    return [x.get(f) for f in L]
out=P('out'); shutil.rmtree(out,ignore_errors=True); os.makedirs(out)
R.sort(key=lambda r:(r['src'],r.get('region') or '',r['id']))
chunks=[]; cur=[]; size=0
for r in R:
    b=len(json.dumps([r.get(f) for f in D],ensure_ascii=False).encode())+len(json.dumps(lean(r),ensure_ascii=False).encode())
    if cur and size+b>330000: chunks.append(cur); cur=[]; size=0
    cur.append(r); size+=b
chunks.append(cur)
writes=[]
for i,c in enumerate(chunks):
    for kind,rows,fields in (('l',[lean(r) for r in c],L),('d',[[r.get(f) for f in D] for r in c],D)):
        fn=f'{GEN}{kind}{i:02d}'; json.dump({'fields':fields,'rows':rows},open(f'{out}/{fn}.json','w'),separators=(',',':'),ensure_ascii=False); writes.append(fn)
json.dump(U['buyers'],open(f'{out}/{GEN}buyers.json','w'),separators=(',',':'),ensure_ascii=False); writes.append(GEN+'buyers')
# ---- changes since last refresh ----
prev_ix={}; pf=P('prev','udir','index.json')
if os.path.exists(pf): prev_ix=json.load(open(pf)); prev_ix=prev_ix.get('data',prev_ix)
pre=prev_ix.get('prefix','')
PREV={}
for f in glob.glob(P('prev','udir',pre+'l[0-9][0-9].json')):
    d=json.load(open(f)); d=d.get('data',d)
    for x in d['rows']: PREV[x[0]]=dict(zip(d['fields'],x))
for f in glob.glob(P('prev','udir',pre+'d[0-9][0-9].json')):
    d=json.load(open(f)); d=d.get('data',d)
    for x in d['rows']:
        if x[0] in PREV: PREV[x[0]].update(dict(zip(d['fields'],x)))
worked=set(os.path.basename(f)[:-5] for f in glob.glob(P('prev','cqc','*.json')))
NOW={r['id']:r for r in R}; items=[]
today=str(TODAY)
for i,n in NOW.items():
    o=PREV.get(i)
    if not o: continue
    w=[]; sev=0
    if o.get('own')!='Group-owned' and n.get('own')=='Group-owned': w.append('now part of a larger group (possible acquisition)'); sev=max(sev,3)
    if o.get('oName') and n.get('oName') and '(via' not in o['oName']+n['oName'] and o['oName']!=n['oName']: w.append(f"controlling owner changed: {o['oName']} → {n['oName']}"); sev=max(sev,3)
    if o.get('chs') and n.get('chs') and o['chs']!=n['chs']: w.append(f"company status: {o['chs']} → {n['chs']}"); sev=max(sev,3)
    if (n.get('chgO') or 0)>(o.get('chgO') or 0): w.append(f"new charge registered ({o.get('chgO') or 0} → {n['chgO']} outstanding)"); sev=max(sev,2)
    if (n.get('chgO') or 0)<(o.get('chgO') or 0): w.append(f"charge satisfied ({o.get('chgO')} → {n.get('chgO') or 0} outstanding)"); sev=max(sev,2)
    if n.get('acc') and n['acc']<today and not (o.get('acc') and o['acc']<prev_ix.get('built','0')): w.append(f"accounts overdue (due {n['acc']})"); sev=max(sev,2)
    if o.get('qmin') is not None and n.get('qmin') is not None and o['qmin']!=n['qmin']: w.append('rating fell below good' if n['qmin']<o['qmin'] and n['qmin']<=45 else ('rating improved' if n['qmin']>o['qmin'] else 'rating changed')); sev=max(sev,2)
    if (o.get('units') or 0)!=(n.get('units') or 0): w.append(f"settings {o.get('units')} → {n.get('units')}"); sev=max(sev,1)
    if o.get('emp') and n.get('emp') and abs(n['emp']-o['emp'])>=max(5,0.25*o['emp']): w.append(f"headcount {round(o['emp'])} → {round(n['emp'])}"); sev=max(sev,1)
    if w: items.append({'id':i,'name':n.get('name'),'src':n.get('src'),'what':w,'sev':sev,'worked':i in worked})
for i in worked:
    if i in PREV and i not in NOW: items.append({'id':i,'name':PREV[i].get('name'),'src':PREV[i].get('src'),'what':['no longer on the register or below the size threshold'],'sev':3,'worked':True})
items.sort(key=lambda x:(not x['worked'],-x['sev']))
new=[i for i in NOW if PREV and i not in PREV]
ch={'at':today,'prevAt':prev_ix.get('built'),'counts':{'new':len(new),'gone':len([i for i in PREV if i not in NOW]),'changed':len(items)},'items':items[:1400]}
while len(json.dumps(ch).encode())>240000: ch['items']=ch['items'][:int(len(ch['items'])*0.85)]
json.dump(ch,open(f'{out}/{GEN}changes.json','w'),separators=(',',':'),ensure_ascii=False); writes.append(GEN+'changes')
S=json.load(open(P('sources.json')))
asof=' · '.join(x for x in [
 f"CQC register ({S['cqc'].get('asOf')})" if 'error' not in S['cqc'] else 'CQC carried forward',
 f"Ofsted children's social care ({S['ofcsc'].get('asOf')})" if 'error' not in S['ofcsc'] else "Ofsted children's social care carried forward",
 f"Ofsted early years ({S['ofey'].get('asOf')})" if 'error' not in S['ofey'] else 'Ofsted early years carried forward',
 f"Companies House ({S['ch'].get('asOf')}), PSC ({S['psc'].get('asOf')}), accounts to {S['acc'].get('asOf','').replace('Accounts_Monthly_Data-','').replace('.zip','')}"])
ix={'prefix':GEN,'chunks':len(chunks),'buyers':GEN+'buyers','changes':GEN+'changes','built':today,'asOf':asof,'counts':dict(collections.Counter(r['src'] for r in R)),'sources':{k:('error' not in v) for k,v in S.items() if isinstance(v,dict)}}
json.dump(ix,open(f'{out}/index.json','w'))
batches=[]; curb=[]; sz=0
for fn in writes:
    s_=os.path.getsize(f'{out}/{fn}.json')
    if curb and (sz+s_>900000 or len(curb)>=8): batches.append(curb); curb=[]; sz=0
    curb.append(fn); sz+=s_
batches.append(curb)
old=[f[:-5] for f in [os.path.basename(x) for x in glob.glob(P('prev','udir','*.json'))] if f!='index.json']
plan={'gen':GEN,'dir':out,'batches':batches,'index':f'{out}/index.json','delete_after':sorted(old)}
json.dump(plan,open(P('plan.json'),'w'),indent=1)
log('publish plan',len(chunks),'chunks',len(writes),'docs',len(batches),'batches; changes',len(items),'new',len(new))
