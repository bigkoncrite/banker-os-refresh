import pandas as pd, re, collections, json
a=pd.read_csv(CSV,dtype=str,low_memory=False)
a=a[(a['Dormant (Y/N)']=='N')&~a['Provider Type/Sector'].isin(['NHS Healthcare Organisation','Primary Medical Services'])]
a=a[~a['Location Primary Inspection Category'].isin(['GP Practices','Prison Healthcare','Hospice services','Out of hours'])]
NOT=re.compile(r'\b(?:COUNCIL|NHS|HOSPICE|CHARIT|FOUNDATION TRUST|BOROUGH|COUNTY|CITY OF|UNIVERSITY|MINISTRY|MOD\b|SOCIETY|ASSOCIATION|C\.?I\.?C\.?)\b',re.I)
a=a[~a['Provider Name'].str.contains(NOT,na=False)&a['Provider Charity Number'].isna()]
a['pstart']=pd.to_datetime(a['Provider HSCA start date'],format='%m/%d/%Y',errors='coerce')
a['beds']=pd.to_numeric(a['Care homes beds'],errors='coerce').fillna(0)
CAT={'Residential social care':'Care homes','Community based adult social care services':'Homecare / supported living','Dentists':'Dental','Independent consulting doctors':'Independent clinics','Acute hospital - Independent specialist':'Independent hospitals','Acute hospital - Independent non-specialist':'Independent hospitals','Community health - NHS & Independent':'Community health','Mental health - community & hospital - independent':'Mental health (independent)','Residential substance misuse':'Substance misuse','Community substance misuse':'Substance misuse','Ambulance service':'Ambulance / transport','Urgent care services & mobile doctors':'Urgent care','Remote clinical advice':'Remote clinical','Slimming Clinics':'Independent clinics'}
a['cat']=a['Location Primary Inspection Category'].map(CAT).fillna('Other healthcare')
QS={'Outstanding':100,'Good':80,'Requires improvement':45,'Inadequate':15}
rows=[]; buyers=collections.defaultdict(list)
for pid,g in a.groupby('Provider ID'):
    f=g.iloc[0]; n=len(g); cats=collections.Counter(g['cat']); main=cats.most_common(1)[0][0]
    if main=='Independent clinics' and n<2: continue
    if pd.notna(f['pstart']) and f['pstart']>(pd.Timestamp.today()-pd.DateOffset(years=5)) and g['Location Latest Overall Rating'].isin(QS).sum()==0: continue
    rat=[r for r in g['Location Latest Overall Rating'] if r in QS]
    qv=[QS[r] for r in rat]; lab=collections.Counter(rat)
    pubs=pd.to_datetime(g['Publication Date'],format='%m/%d/%Y',errors='coerce').dropna()
    regs=collections.Counter(g['Location Region'])
    sites=';'.join(f"{r['Location Name']}|{r['Location Local Authority']}|{int(r['beds']) if r['beds'] else ''}|{r['Location Latest Overall Rating'] if r['Location Latest Overall Rating']==r['Location Latest Overall Rating'] else ''}|{r['Location ID']}" for _,r in g.iterrows())[:900] if n>1 else None
    cn=f['Provider Companies House Number']; cn=str(cn).strip().upper().zfill(8) if isinstance(cn,str) and cn.strip() else None
    own={'Organisation':'Company','Individual':'Individual','Partnership':'Partnership'}.get(f['Provider Ownership Type'],f['Provider Ownership Type'])
    rows.append(dict(id='cqp-'+pid,src='cqc',name=f['Brand Name'].replace('BRAND ','') if isinstance(f['Brand Name'],str) and n>1 and False else (f['Provider Name'] if n>1 else f['Location Name']),prov=f['Provider Name'],sector=main,kind=' · '.join(f"{v} {k.lower()}" for k,v in cats.most_common()),units=n,
      cap=int(g['beds'].sum()) or None,capU='beds' if g['beds'].sum() else ('locations'),q=' · '.join(f"{v} {k}" for k,v in lab.most_common()) or 'Not yet rated',qs=round(sum(qv)/len(qv)) if qv else None,qmin=min(qv) if qv else None,
      rDate=str(pubs.min().date()) if len(pubs) else None,reg=str(f['pstart'].date()) if pd.notna(f['pstart']) else None,region=regs.most_common(1)[0][0],la=', '.join(sorted(set(g['Location Local Authority'].dropna())))[:200],
      pc=f['Location Postal Code'] if n==1 else f['Provider Postal Code'],phone=f['Location Telephone Number'] if n==1 else (f['Provider Telephone Number'] if isinstance(f['Provider Telephone Number'],str) else None),
      mgr=(f['Registered manager'] if n==1 and isinstance(f['Registered manager'],str) else None),ni=f['Provider Nominated Individual Name'] if isinstance(f['Provider Nominated Individual Name'],str) else None,
      web=f['Provider Web Address'] if isinstance(f['Provider Web Address'],str) else (f['Location Web Address'] if isinstance(f['Location Web Address'],str) else None),
      own=own,cn=cn,url=('https://www.cqc.org.uk/location/'+f['Location ID']) if n==1 else ('https://www.cqc.org.uk/provider/'+pid),regions=', '.join(k for k,_ in regs.most_common()),sites=sites,brand=f['Brand Name'] if isinstance(f['Brand Name'],str) and f['Brand Name']!='-' else None))
    if n>=8: buyers[main].append(dict(n=f['Provider Name'],prov=n,places=int(g['beds'].sum()),types=main,regions=dict(regs)))
json.dump(dict(rows=rows,buyers={k:sorted(v,key=lambda x:-x['prov'])[:120] for k,v in buyers.items()}),open(OUT,'w'),default=str)

