# Stage 2: parse registers, scan Companies House, decide target company numbers
import pandas as pd, json, re, zipfile, glob, os, collections
from common import *
from norm import norm
S=json.load(open(P('sources.json')))
def load_ods(f,s):
    x=pd.read_excel(f,engine='odf',sheet_name=s,header=None)
    for i in range(12):
        if x.iloc[i].notna().sum()>5: break
    df=x.iloc[i+1:].copy(); df.columns=x.iloc[i].tolist(); return df.reset_index(drop=True)
def sheet(f,prefix):
    names=pd.ExcelFile(f,engine='odf').sheet_names
    return next(n for n in names if n.startswith(prefix))
names=set()
if 'error' not in S['ofcsc']:
    try:
        a=load_ods(P('src','csc.ods'),sheet(P('src','csc.ods'),'Provider_level_at')); a.to_pickle(P('csc_prov.pkl'))
        o=load_ods(P('src','own.ods'),sheet(P('src','own.ods'),'Provider_level_at')); o.to_pickle(P('own_prov.pkl'))
        ol=load_ods(P('src','own.ods'),sheet(P('src','own.ods'),'Ownership_level_at')); ol.to_pickle(P('own_lvl.pkl'))
        names|=set(norm(x) for x in a[a['Sector']=='Private']['Organisation which owns the provider'].dropna())
        log('CSC parsed',len(a))
    except Exception as e: S['ofcsc']={'error':'parse: '+str(e)}; log('CSC parse FAILED',e)
if 'error' not in S['ofey']:
    try:
        raw=open(P('src','ey.csv'),encoding='utf-8-sig',errors='ignore').read().splitlines()
        hdr=next(i for i,l in enumerate(raw[:10]) if 'Provider URN' in l)
        ey=pd.read_csv(P('src','ey.csv'),skiprows=hdr,encoding='utf-8-sig',encoding_errors='ignore',low_memory=False)
        ey=ey.loc[:,~ey.columns.str.startswith('Unnamed')]
        ey.columns=[c.replace('Provider type','Provider type').strip() for c in ey.columns]
        ren={c:c for c in ey.columns}
        for c in ey.columns:  # tolerate older capitalisation
            lc=c.lower()
            for want in ['Provider type','Provider subtype','Provider status','Registered person URN','Registered person name','Provider name','Provider postcode','Local authority','Registration date','Places including estimates']:
                if lc==want.lower(): ren[c]=want
        ey=ey.rename(columns=ren); ey.to_pickle(P('ey.pkl'))
        names|=set(norm(x) for x in ey[ey['Provider type'].str.contains('non-domestic',na=False)]['Registered person name'].dropna())
        log('EY parsed',len(ey))
    except Exception as e: S['ofey']={'error':'parse: '+str(e)}; log('EY parse FAILED',e)
names.discard('')
cqc_cns=set()
if 'error' not in S['cqc']:
    try:
        f=[x for x in glob.glob(P('src','cqcx','*.csv')) if x.endswith('HSCA_Active_Locations.csv')][0]
        exec(open(os.path.join(os.path.dirname(__file__),'cqc_agg.py')).read(),{'CSV':f,'OUT':P('cqc_prov.json'),'__name__':'cqc'})
        cqc_cns=set(r['cn'] for r in json.load(open(P('cqc_prov.json')))['rows'] if r['cn'])
        log('CQC providers',len(json.load(open(P('cqc_prov.json')))['rows']))
    except Exception as e: S['cqc']={'error':'parse: '+str(e)}; log('CQC parse FAILED',e)
json.dump(S,open(P('sources.json'),'w'),indent=1)
# Companies House single pass
want=['CompanyName','CompanyNumber','CompanyStatus','CompanyCategory','IncorporationDate','Accounts.AccountCategory','Accounts.NextDueDate','Mortgages.NumMortCharges','Mortgages.NumMortOutstanding','SICCode.SicText_1','SICCode.SicText_2','SICCode.SicText_3','SICCode.SicText_4','RegAddress.PostCode','RegAddress.PostTown','ConfStmtNextDueDate']
SIC=re.compile(r'^(86|87|88)\d{3}')
z=zipfile.ZipFile(P('src','basic.zip')); fn=z.namelist()[0]; keep=[]
with z.open(fn) as fh:
    for ch in pd.read_csv(fh,chunksize=400000,dtype=str,usecols=lambda c:c.strip() in want):
        ch.columns=[c.strip() for c in ch.columns]; ch['CompanyNumber']=ch['CompanyNumber'].str.strip()
        ch['n']=ch['CompanyName'].map(norm)
        s4=ch[['SICCode.SicText_1','SICCode.SicText_2','SICCode.SicText_3','SICCode.SicText_4']].fillna('')
        hsc=s4.apply(lambda r:any(SIC.match(x) for x in r),axis=1)&ch['CompanyStatus'].eq('Active')
        keep.append(ch[ch['n'].isin(names)|ch['CompanyNumber'].isin(cqc_cns)|hsc])
ch=pd.concat(keep).drop_duplicates('CompanyNumber'); ch.to_pickle(P('ch_all.pkl')); log('CH rows kept',len(ch))
# Companies House-only candidates: health and social care SIC, 10+ years, non-micro, not charities
ch['inc']=pd.to_datetime(ch['IncorporationDate'],dayfirst=True,errors='coerce')
cut=pd.Timestamp.today()-pd.DateOffset(years=10)
OK={'TOTAL EXEMPTION FULL','UNAUDITED ABRIDGED','SMALL','FULL','MEDIUM','GROUP','AUDITED ABRIDGED','TOTAL EXEMPTION SMALL'}; big={'SMALL','FULL','MEDIUM','GROUP','AUDITED ABRIDGED'}
sic1=ch['SICCode.SicText_1'].fillna('').str[:5]
care=sic1.str.match(r'^(?:87|881|8899|8891|86102|86230)')
NOTN=re.compile(r'\b(?:CHARIT|TRUST|C\.?I\.?C|FOUNDATION|ASSOCIATION|SOCIETY|NHS|COUNCIL|HOSPICE)\b',re.I)
sicany=ch[['SICCode.SicText_1','SICCode.SicText_2','SICCode.SicText_3','SICCode.SicText_4']].fillna('').apply(lambda r:any(SIC.match(x) for x in r),axis=1)
m=sicany&ch['CompanyStatus'].eq('Active')&(ch['inc']<=cut)&ch['Accounts.AccountCategory'].isin(OK)&(care|ch['Accounts.AccountCategory'].isin(big))&ch['CompanyCategory'].fillna('').str.contains('Private Limited|Limited Liability Partnership')&~ch['CompanyName'].str.contains(NOTN)
cand=ch[m]; cand.to_pickle(P('ch_cand.pkl'))
targets=set(ch[ch['n'].isin(names)]['CompanyNumber'])|cqc_cns|set(cand['CompanyNumber'])
json.dump(sorted(targets),open(P('targets.json'),'w')); log('candidates',len(cand),'targets',len(targets))
