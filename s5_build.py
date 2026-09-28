import pandas as pd, json, re, sys, math, collections, datetime as dt, os, glob
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from norm import norm
from common import P as PATH, log
TODAY=dt.date.today()
SRCS=json.load(open(PATH('sources.json')))
OKSRC=lambda k:'error' not in SRCS.get(k,{})
def iso(x):
    if x is None or (isinstance(x,float) and math.isnan(x)) or x is pd.NaT: return None
    if isinstance(x,(pd.Timestamp,dt.datetime,dt.date)): return str(x)[:10]
    s=str(x).strip()
    m=re.match(r'(\d{2})/(\d{2})/(\d{4})',s)
    if m: return f'{m[3]}-{m[2]}-{m[1]}'
    return s[:10] if re.match(r'\d{4}-\d{2}-\d{2}',s) else None
def nz(x): return None if x is None or (isinstance(x,float) and math.isnan(x)) else x
def slug(s): return re.sub(r'[^a-z0-9]+','-',str(s).lower()).strip('-')[:60]
PE=re.compile(r'\b(CAPITAL|PARTNERS|EQUITY|INVEST|INVESTMENTS|HOLDCO|MIDCO|BIDCO|TOPCO|FUND|LLP)\b')
# ---------- Companies House ----------
ch=pd.read_pickle(PATH('ch_all.pkl'))
RECS=ch.to_dict('records')
CH={r['CompanyNumber']:r for r in RECS}
byname=collections.defaultdict(list)
for r in RECS: byname[r['n']].append(r)
psc=json.load(open(PATH('psc_all.json'))); P=collections.defaultdict(list)
for p in psc: P[p['cn']].append(p)
PP=collections.defaultdict(list)
for p in json.load(open(PATH('psc_parents.json'))): PP[p['cn']].append(p)
def regnorm(r):
    r=re.sub(r'[^0-9A-Z]','',str(r or '').upper()); m=re.match(r'^([A-Z]{2})?(\d+)$',r)
    return ((m[1] or '')+m[2].zfill(8-len(m[1] or ''))) if m else None
PF=json.load(open(PATH('owner_portfolio.json')))
def okey(name,dob):
    n=re.sub(r'^(MR|MRS|MS|MISS|DR|PROF|SIR|DAME|LADY|LORD)\.? ','',re.sub(r'[^A-Z ]','',str(name).upper())).split()
    return (n[0]+' '+n[-1] if n else '')+'|'+(f"{dob['year']}-{dob.get('month',0):02d}" if dob else '')
ACC={}
for f_ in sorted(glob.glob(PATH('acc','*.json'))):
    for k_,v_ in json.load(open(f_)).items():
        if k_ not in ACC or v_['end']>ACC[k_]['end']: ACC[k_]=v_
def accf(cn):
    a_=ACC.get(cn) if cn else None
    if not a_: return dict(emp=None,turn=None,na=None,cash=None,accEnd=None,op=None)
    return dict(emp=a_.get('emp'),turn=a_.get('turnover'),na=a_.get('na',a_.get('eq')),cash=a_.get('cash'),accEnd=a_.get('end'),op=a_.get('op'))
def age(dob):
    if not dob: return None
    return TODAY.year-dob['year']-(1 if dob.get('month',1)>TODAY.month else 0)
def pick(name, prefer_sic):
    c=byname.get(norm(name),[])
    if not c: return None,'No match'
    act=[x for x in c if str(x['CompanyStatus']).startswith('Active')] or c
    if len(act)>1:
        s=[x for x in act if any(k in str(x.get('SICCode.SicText_1',''))+str(x.get('SICCode.SicText_2','')) for k in prefer_sic)]
        if len(s)==1: return s[0],'Name + SIC match'
        return sorted(act,key=lambda x:str(x['IncorporationDate']))[-1],'Name match (ambiguous)'
    return act[0],'Exact name match'
def chfields(r, how):
    if r is None: return dict(cn=None,chn=None,chs=None,inc=None,sic=None,accCat=None,acc=None,conf=None,chgO=None,chgT=None,chm=how,rpc=None)
    g=lambda k:nz(r.get(k))
    num=lambda k:int(float(g(k))) if g(k) not in (None,'') else 0
    sic='; '.join(str(g(k)) for k in ['SICCode.SicText_1','SICCode.SicText_2'] if g(k) and str(g(k))!='None Supplied')
    return dict(cn=r['CompanyNumber'],chn=r['CompanyName'],chs=r['CompanyStatus'],inc=iso(g('IncorporationDate')),sic=sic or None,accCat=g('Accounts.AccountCategory'),acc=iso(g('Accounts.NextDueDate')),conf=iso(g('ConfStmtNextDueDate')),chgO=num('Mortgages.NumMortOutstanding'),chgT=num('Mortgages.NumMortCharges'),chm=how,rpc=g('RegAddress.PostCode'))
def pscf(cn):
    ps=P.get(cn,[]) if cn else []
    ind=[p for p in ps if p['kind'].startswith('individual')]
    corp=[p for p in ps if 'corporate' in p['kind'] or 'legal-person' in p['kind']]
    via=False
    if not ind and corp:
        for c_ in corp:
            par=[p for p in PP.get(regnorm(c_.get('reg')),[]) if p['kind'].startswith('individual')]
            if par: ind=par; via=True; break
    maj=[p for p in ind if any(('50-to-75' in n) or ('75-to-100' in n) for n in p['noc'])]
    base=maj or ind
    ages=[(age(p['dob']),p['name']) for p in base if p.get('dob')]
    oAge,oName=(max(ages) if ages else (None,None))
    pf=max([PF.get(okey(p['name'],p['dob']),0) for p in base if p.get('dob')] or [0]) or None
    since=min([p['on'] for p in ind if p.get('on')] or [None]) if ind else None
    cname=corp[0]['name'] if corp else None
    return dict(oAge=oAge,oName=(oName.title()+(' (via '+cname.title()+')' if via else '')) if oName else None,pscN=len(ind),pSince=since,corp=cname,pf=pf)
F=['id','src','name','prov','sector','kind','units','cap','capU','q','qs','qmin','rDate','reg','region','la','pc','phone','mgr','own','ult','cn','chn','chs','inc','sic','accCat','acc','conf','chgO','chgT','chm','oAge','oName','pscN','pSince','corp','ev','url','regions','sites']
rows=[]
# ---------- CQC (full register, provider level) ----------
CQ=json.load(open(PATH('cqc_prov.json'))) if OKSRC('cqc') else {'rows':[],'buyers':{}}; cqc_buyers=CQ['buyers']
for t in CQ['rows']:
    cn=t['cn']; r=CH.get(cn) if cn else None
    c=chfields(r,'Company number (CQC register)' if r else ('No company number' if not cn else 'Company number not in bulk data'))
    if not r and cn: c['cn']=cn
    p=pscf(c['cn']); own=t['own']
    if own=='Company' and p['corp']: own='Group-owned' if PE.search(str(p['corp']).upper()) else 'Holding co'
    if t['units']>=40: own='Group-owned'
    if own=='Company' and not c['cn']: own='Unmatched'
    rows.append(dict(t,**{k:v for k,v in c.items() if k not in('rpc','cn')},cn=c['cn'],**p,**accf(c['cn']),own=own,ult=p['corp'],capU=t['capU'] if t['cap'] else 'locations',cap=t['cap'] if t['cap'] else t['units'],ev=None))
# ---------- Ofsted children's social care ----------
csc_buyers=[]; ey_buyers=[]
if OKSRC('ofcsc'):
  a=pd.read_pickle(PATH('csc_prov.pkl')); o=pd.read_pickle(PATH('own_prov.pkl')); ol=pd.read_pickle(PATH('own_lvl.pkl'))
  OT=dict(zip(ol['Owner'],ol['Overall providers']))
  a=a.merge(o[['URN','Owner name','Places [Note 1]']],on='URN',how='left')
  a['Places [Note 1]']=pd.to_numeric(a['Places [Note 1]'],errors='coerce'); a['Places']=pd.to_numeric(a['Places'],errors='coerce')
  a['Places']=a['Places'].where(a['Places'].fillna(0)>0, a['Places [Note 1]'])
  a.loc[(a['Provision type']=='Independent Fostering Agency')&(a['Places'].fillna(0)==0),'Places']=40
  a=a[(a['Sector']=='Private')&(~a['Provision type'].isin(['Boarding School','Further Education College with Residential Accommodation',"Secure children's home",'Secure Training Centre','Voluntary Adoption Agency','Adoption Support Agency']))]
  EVP={"Children's home":300000,"Children's Home":300000,'Residential special school (registered as a children\'s home)':250000,'Residential Special School':200000,'Independent Fostering Agency':35000,'Supported Accommodation':40000,'Residential Family Centre':150000,'Residential Holiday Scheme for Disabled Children':50000}
  QO={'Outstanding':100,'Good':80,'Requires improvement to be good':45,'Inadequate':15,'Consistently strong service delivery':90,'Inconsistent quality of service delivery':50,'Serious or widespread weaknesses':15}
  SHORT={'Requires improvement to be good':'Requires improvement','Consistently strong service delivery':'Strong','Inconsistent quality of service delivery':'Inconsistent','Serious or widespread weaknesses':'Serious weaknesses'}
  for org,g in a.groupby('Organisation which owns the provider'):
      types=collections.Counter(g['Provision type'].str.replace("Children's Home","Children's home"))
      places=int(g['Places'].fillna(0).sum())
      ev=int(sum(EVP.get(t,50000)*(p or 0) for t,p in zip(g['Provision type'],g['Places'].fillna(0))))
      qv=[]; qlab=collections.Counter()
      for _,x in g.iterrows():
          v=nz(x['Overall experiences and progress of children and young people']) or nz(x['Supported accommodation outcome'])
          if v: qv.append(QO.get(v)); qlab[SHORT.get(v,v)]+=1
      dates=[iso(d) for d in g['Latest full inspection date'] if iso(d)]
      ownr=nz(g['Owner name'].dropna().iloc[0]) if g['Owner name'].notna().any() else None
      r,how=pick(org,['8790','8810','8899','8730'])
      c=chfields(r,how); p=pscf(c['cn'])
      grp = ownr and norm(ownr)!=norm(org) and OT.get(ownr,0)>len(g)
      own='Group-owned' if grp or (p['corp'] and PE.search(str(p['corp']).upper())) else ('Holding co' if p['corp'] else ('Company' if c['cn'] else 'Unmatched'))
      sites=';'.join(f"{t}|{la}|{int(pl) if pl==pl else ''}|{SHORT.get(q,q) if q==q and q else ''}" for t,la,pl,q in zip(g['Provision type'],g['Local authority'],g['Places'],g['Overall experiences and progress of children and young people'].fillna(g['Supported accommodation outcome'])))[:700] if len(g)>1 else None
      regs=collections.Counter(g['Government office region'])
      rows.append(dict(id='csc-'+slug(org),src='ofcsc',name=org.strip(),prov=org.strip(),sector="Children's social care",kind=' · '.join(f"{n} {t}" for t,n in types.most_common()),units=len(g),cap=places,capU='places',q=' · '.join(f"{n} {k}" for k,n in qlab.most_common()) or 'Not yet inspected',qs=round(sum(qv)/len(qv)) if qv else None,qmin=min(qv) if qv else None,rDate=min(dates) if dates else None,reg=iso(min(g['Registration date'])),region=regs.most_common(1)[0][0],la=', '.join(sorted(set(g['Local authority'])))[:200],pc=c.get('rpc'),phone=None,mgr=None,own=own,ult=ownr if grp else p['corp'],**{k:v for k,v in c.items() if k!='rpc'},**p,**accf(c['cn']),ev=ev,url=None,regions=', '.join(k for k,_ in regs.most_common()),sites=sites))
  # consolidators
  reg_by_owner=a.groupby('Owner name')['Government office region'].agg(lambda s:dict(collections.Counter(s)))
  for _,x in ol.sort_values('Overall providers',ascending=False).iterrows():
      if x['Overall providers']<5 or x['Sector [Note 2]']!='Private': continue
      csc_buyers.append(dict(n=x['Owner'],prov=int(x['Overall providers']),places=int(x['Overall places']),types=x['Types of provision'],regions=reg_by_owner.get(x['Owner'],{})))
# ---------- Ofsted early years ----------
if OKSRC('ofey'):
  ey=pd.read_pickle(PATH('ey.pkl')); ey=ey[ey['Provider type'].str.contains('non-domestic',na=False)&(ey['Provider status']=='Active')]
  NOT=re.compile(r'\b(COMMITTEE|PRE-?SCHOOL ASSOCIATION|SCHOOL|ACADEMY|ACADEMIES|CHURCH|PARISH|COUNCIL|UNIVERSITY|COLLEGE|NHS|DIOCES|CIO|CHARIT|FOUNDATION|PTA|PTFA|FRIENDS OF|COMMUNITY ASSOCIATION|TRUST|YMCA|C\.?I\.?C\.?|SOCIETY|MANAGEMENT GROUP|PLAYGROUP ASSOCIATION|HOSPITAL|BOROUGH|COUNTY)\b',re.I)
  CO=re.compile(r'\b(LTD|LIMITED|LLP|PLC)\b',re.I)
  REIF=['EYR REIF: Most recent: Inclusion','EYR REIF: Most recent: Curriculum and teaching','EYR REIF: Most recent: Achievement','EYR REIF: Most recent: Behaviour, attitudes and establishing routines',"EYR REIF: Most recent: Children's welfare and wellbeing",'EYR REIF: Most recent: Leadership and governance']
  RV={'Exceptional':100,'Strong standard':85,'Expected standard':70,'Needs attention':40,'Urgent improvement':15}
  OE={'1':100,'2':80,'3':45,'4':15,'1.0':100,'2.0':80,'3.0':45,'4.0':15}
  LAB={100:'Outstanding',80:'Good',45:'Requires improvement',15:'Inadequate'}
  EVE={'Full day care':12000,'Sessional day care':4000,'Out-of-school day care':2000}
  ey['places']=pd.to_numeric(ey['Places including estimates'],errors='coerce').fillna(0)
  for rp,g in ey.groupby('Registered person URN'):
      name=str(g['Registered person name'].iloc[0])
      fdc=g[g['Provider subtype']=='Full day care']
      places=int(g['places'].sum())
      if NOT.search(name): continue
      if len(g)>=10: ey_buyers.append(dict(n=name,prov=len(g),places=places,types=f"{len(fdc)} full day care",regions=dict(collections.Counter(g['Region']))))
      if fdc.empty or places<30: continue
      qv=[]; qlab=collections.Counter(); dates=[]
      for _,x in g.iterrows():
          rv=[RV[x[c]] for c in REIF if x.get(c) in RV]
          if rv: v=round(sum(rv)/len(rv)); lab='Needs attention' if min(rv)<=40 else ('Strong' if v>=85 else 'Expected'); d=iso(x['EYR REIF: Most recent: Inspection date'])
          else:
              o_=str(x.get('EYR OEIF/CIF: Most recent: Overall effectiveness','')); v=OE.get(o_); lab=LAB.get(v); d=iso(x['EYR OEIF: Most recent: Full inspection date'])
          if v: qv.append(v); qlab[lab]+=1
          if d: dates.append(d)
      iscomp=bool(CO.search(name))
      r,how=pick(name,['8891','8510']) if iscomp else (None,'Individual / partnership')
      c=chfields(r,how); p=pscf(c['cn'])
      own='Individual / partnership' if not iscomp else ('Group-owned' if p['corp'] and PE.search(str(p['corp']).upper()) else ('Holding co' if p['corp'] else ('Company' if c['cn'] else 'Unmatched')))
      if len(g)>=40: own='Group-owned'
      ev=int(sum(EVE.get(s,3000)*pl for s,pl in zip(g['Provider subtype'],g['places'])))
      regs=collections.Counter(g['Region'])
      first=g.iloc[0]
      sites=';'.join(f"{n}|{la}|{int(pl)}|{st}|{u}" for n,la,pl,st,u in zip(g['Provider name'],g['Local authority'],g['places'],g['Provider subtype'],g['Provider URN']))[:900] if len(g)>1 else None
      rows.append(dict(id='ey-'+rp,src='ofey',name=name if len(g)>1 else str(first['Provider name']),prov=name,sector='Nursery / early years',kind=' · '.join(f"{n} {k.lower()}" for k,n in collections.Counter(g['Provider subtype']).most_common()),units=len(g),cap=places,capU='places',q=' · '.join(f"{n} {k}" for k,n in qlab.most_common()) or 'Not yet inspected',qs=round(sum(qv)/len(qv)) if qv else None,qmin=min(qv) if qv else None,rDate=min(dates) if dates else None,reg=min(iso(d) for d in g['Registration date']),region=regs.most_common(1)[0][0],la=', '.join(sorted(set(g['Local authority'])))[:200],pc=str(first['Provider postcode']) if len(g)==1 else c.get('rpc'),phone=None,mgr=None,own=own,ult=p['corp'],**{k:v for k,v in c.items() if k!='rpc'},**p,**accf(c['cn']),ev=ev,url='https://reports.ofsted.gov.uk/provider/16/'+str(first['Provider URN']) if len(g)==1 else None,regions=', '.join(k for k,_ in regs.most_common()),sites=sites))
ey_buyers.sort(key=lambda x:-x['prov'])
# ---------- Companies House only (health and social care SICs) ----------
seen=set(r['cn'] for r in rows if r.get('cn'))
SECT=[('8623','Dental'),('873','Care homes'),('871','Care homes'),('872','Supported living / specialist care'),('8790','Supported living / specialist care'),('881','Homecare / supported living'),('8899','Social care services'),('8891','Nursery / early years'),('86102','Care homes'),('8610','Independent hospitals'),('8690','Other healthcare'),('8621','Primary care'),('8622','Independent clinics')]
cand=pd.read_pickle(PATH('ch_cand.pkl'))
for x in cand.to_dict('records'):
    cn=x['CompanyNumber'].strip()
    if cn in seen: continue
    sic=str(x.get('SICCode.SicText_1') or '')
    sec=next((l for k,l in SECT if sic.startswith(k)),'Health and social care')
    c=chfields(CH.get(cn),'Companies House (SIC search)'); p=pscf(cn)
    own='Group-owned' if p['corp'] and PE.search(str(p['corp']).upper()) else ('Holding co' if p['corp'] else 'Company')
    rows.append(dict(id='ch-'+cn,src='chhsc',name=x['CompanyName'].title() if x['CompanyName'].isupper() else x['CompanyName'],prov=x['CompanyName'],sector=sec,kind=sic,units=1,cap=None,capU=None,q='Not matched to a regulator register',qs=None,qmin=None,rDate=None,reg=None,region=None,la=x.get('RegAddress.PostTown'),pc=c.get('rpc'),phone=None,mgr=None,own=own,ult=p['corp'],**{k:v for k,v in c.items() if k!='rpc'},**p,**accf(cn),ev=None,url=None,regions=None,sites=None))

print(collections.Counter(r['src'] for r in rows)); print(collections.Counter((r['src'],r['sector']) for r in rows).most_common(30)); print(collections.Counter((r['src'],r['own']) for r in rows))
print('owner age known',collections.Counter((r['src'],r['oAge'] is not None) for r in rows))
# ---------- Companies House API enrichment ----------
API=json.load(open(PATH('api_out.json'))) if os.path.exists(PATH('api_out.json')) else {'officers':{},'match':{}}
def dirstr(offs):
    offs=sorted([o for o in offs if o.get('n')],key=lambda o:o.get('on') or '')
    return ';'.join(f"{re.sub(r',',' ',o['n']).title().strip()}|{age(o['dob']) if o.get('dob') else ''}|{o.get('on') or ''}" for o in offs[:6]) or None
def diroldest(offs):
    c=[(age(o['dob']),o['n']) for o in offs if o.get('dob')]
    return max(c) if c else (None,None)
for r in rows:
    r.setdefault('oSrc','psc' if r.get('oAge') is not None else None); r.setdefault('dirs',None)
    m=API['match'].get(r['id'])
    if not r.get('cn') and m:
        pr=m['prof'] or {}; acc_=pr.get('accounts') or {}
        r.update(cn=m['cn'],chn=pr.get('company_name'),chs=(pr.get('company_status') or '').title(),inc=pr.get('date_of_creation'),sic='; '.join(pr.get('sic_codes') or []),acc=(acc_.get('next_accounts') or {}).get('due_on') or acc_.get('next_due'),accCat=((acc_.get('last_accounts') or {}).get('type') or '').replace('-',' ').upper() or None,conf=(pr.get('confirmation_statement') or {}).get('next_due'),chm='API search: exact name' if m['exact'] else 'API search: partial name (verify)',pc=r.get('pc') or (pr.get('registered_office_address') or {}).get('postal_code'))
        ind=[p for p in m['psc'] if (p.get('kind') or '').startswith('individual')]; corp=[p for p in m['psc'] if 'corporate' in (p.get('kind') or '') or 'legal' in (p.get('kind') or '')]
        maj=[p for p in ind if any(('50-to-75' in n) or ('75-to-100' in n) for n in p['noc'])] or ind
        ages=[(age(p['dob']),p['name']) for p in maj if p.get('dob')]
        if ages: a_,n_=max(ages); r.update(oAge=a_,oName=n_.title(),oSrc='psc')
        r.update(pscN=len(ind),pSince=min([p['on'] for p in ind if p.get('on')] or [None]),corp=corp[0]['name'] if corp else None)
        if r['own'] in ('Unmatched',): r['own']='Holding co' if corp else 'Company'
        if m.get('officers'): r['dirs']=dirstr(m['officers'])
    offs=API['officers'].get(r.get('cn') or '')
    if offs is not None and offs:
        r['dirs']=dirstr(offs)
        if r.get('oAge') is None:
            a_,n_=diroldest(offs)
            if a_: r.update(oAge=a_,oName=re.sub(r',',' ',n_).title().strip(),oSrc='director')
# ---------- carry forward sources that failed this month ----------
PREV={}
for f_ in glob.glob(PATH('prev','udir','l*.json')):
    d_=json.load(open(f_)); d_=d_.get('data',d_)
    for x in d_['rows']: PREV[x[0]]=dict(zip(d_['fields'],x))
for f_ in glob.glob(PATH('prev','udir','d*.json')):
    d_=json.load(open(f_)); d_=d_.get('data',d_)
    for x in d_['rows']:
        if x[0] in PREV: PREV[x[0]].update(dict(zip(d_['fields'],x)))
for k_ in ['cqc','ofcsc','ofey']:
    if not OKSRC(k_):
        keep_=[r for r in PREV.values() if r.get('src')==k_]; rows+=keep_; log('carried forward',k_,len(keep_))
_reg=set(r.get('cn') for r in rows if r['src']!='chhsc' and r.get('cn'))
rows=[r for r in rows if not (r['src']=='chhsc' and r.get('cn') in _reg)]
RPE={'Care homes':35000,'Homecare / supported living':28000,'Supported living / specialist care':45000,'Dental':90000,'Independent hospitals':110000,'Independent clinics':110000,'Community health':70000,'Primary care':90000,'Nursery / early years':30000,'Social care services':35000}
MULT={'Homecare / supported living':0.6,'Dental':1.0,'Independent hospitals':1.0,'Independent clinics':1.0,'Supported living / specialist care':1.0,'Care homes':1.0}
PC={'E':'','N':''}
for r in rows:
    if r.get('ev') is None:
        sec=r['sector']; basis=None
        if sec=='Care homes' and r.get('capU')=='beds' and r.get('cap'): ev=r['cap']*50000; basis=f"{r['cap']} beds × £50k"
        elif r.get('turn'): ev=r['turn']*MULT.get(sec,0.8); basis=f"turnover × {MULT.get(sec,0.8)}"
        elif r.get('emp'): rev=r['emp']*RPE.get(sec,50000); ev=rev*MULT.get(sec,0.8); basis=f"{r['emp']:.0f} staff × £{RPE.get(sec,50000)//1000}k revenue × {MULT.get(sec,0.8)}"
        else: ev=(r.get('units') or 1)*500000; basis='£500k per location (no size data)'
        r['ev']=int(ev); r['evb']=basis
    else:
        r['evb']={'ofcsc':'places × sector value per place','ofey':'places × £12k full day care / £4k sessional'}.get(r['src'],'model')
    if r['src']=='ofcsc' and r.get('emp') is None: pass
# trim the tail: tiny operators are not mandates
def keep(r):
    if r['src'] in ('ofcsc','ofey'): return True
    if r['own'] in ('Individual','Partnership') and r['sector']!='Dental': return r['ev']>=750000
    if r.get('emp') is not None and r['emp']<5 and not (r.get('capU')=='beds' and (r.get('cap') or 0)>=15): return False
    return r['ev']>=750000 or (r.get('oAge') or 0)>=60 and r['ev']>=500000
before=len(rows); rows=[r for r in rows if keep(r)]; print('trimmed',before,'->',len(rows))
F=F+['ni','web','brand','emp','turn','na','cash','accEnd','op','pf','evb','oSrc','dirs']
json.dump(dict(built=str(TODAY),F=F,rows=[[r.get(f) for f in F] for r in rows],buyers=dict(ofcsc=csc_buyers[:150],ofey=ey_buyers[:120],cqc=cqc_buyers)),open(PATH('universe.json'),'w'),default=str)
