# Stage 1: find and download the latest public releases
import re, json, datetime as dt, urllib.parse, os, subprocess
from common import *
os.makedirs(P('src'),exist_ok=True)
def gov_assets(path):
    html=http('https://www.gov.uk'+path).decode('utf-8','ignore')
    return sorted(set(re.findall(r'https://assets\.publishing\.service\.gov\.uk/[^"\\\s]+\.(?:csv|ods|xlsx)',html)))
def gov_latest(q,prefix):
    j=json.loads(http('https://www.gov.uk/api/search.json?'+urllib.parse.urlencode({'q':q,'filter_organisations':'ofsted','count':20,'order':'-public_timestamp'})))
    for r in j['results']:
        if r['link'].startswith(prefix) and '/announcements/' not in r['link']:
            a=gov_assets(r['link'])
            if a: return r['link'],a
    raise RuntimeError('no release found for '+q)
MON={m:i for i,m in enumerate(['january','february','march','april','may','june','july','august','september','october','november','december'],1)}
def date_in(name):
    m=re.search(r'(\d{1,2})_([A-Za-z]+)_(\d{4})',name)
    if m and m[2].lower() in MON: return (int(m[3]),MON[m[2].lower()],int(m[1]))
    return (0,0,0)
src={}
# CQC care directory (monthly)
try:
    html=http('https://www.cqc.org.uk/about-us/transparency/using-cqc-data').decode('utf-8','ignore')
    links=re.findall(r'href="(https://www\.cqc\.org\.uk/system/files/[^"]+HSCA_Active_Locations\.ods)"',html)
    url=sorted(links,key=date_in)[-1]; download(url,P('src','cqc.ods'))
    os.makedirs(P('src','cqcx'),exist_ok=True)
    subprocess.run(['soffice','--headless','--convert-to','csv:Text - txt - csv (StarCalc):44,34,UTF8,1,,0,false,true,false,false,false,-1','--outdir',P('src','cqcx'),P('src','cqc.ods')],check=True,timeout=2400,capture_output=True)
    src['cqc']={'url':url,'asOf':'-'.join(str(x).zfill(2) for x in date_in(url))}; log('CQC',url)
except Exception as e: src['cqc']={'error':str(e)}; log('CQC FAILED',e)
# Ofsted early years (quarterly)
try:
    a=gov_assets('/government/statistical-data-sets/childcare-providers-and-inspections-management-information')
    c=[u for u in a if u.endswith('.csv') and re.search(r'(childcare_providers_data_as_at|most_recent_inspections_data)',u,re.I)]
    url=sorted(c,key=date_in)[-1]; download(url,P('src','ey.csv'))
    src['ofey']={'url':url,'asOf':'-'.join(str(x).zfill(2) for x in date_in(url))}; log('EY',url)
except Exception as e: src['ofey']={'error':str(e)}; log('EY FAILED',e)
# Ofsted children's social care (annual) + ownership (annual)
try:
    link,a=gov_latest('"children\'s social care in England"','/government/statistics/childrens-social-care-in-england-')
    download([u for u in a if u.endswith('.ods')][0],P('src','csc.ods'))
    link2,a2=gov_latest('"ownership of children\'s social care providers"','/government/statistics/ownership-of-childrens-social-care-providers-in-england-')
    download([u for u in a2 if u.endswith('.ods')][0],P('src','own.ods'))
    src['ofcsc']={'url':link,'own':link2,'asOf':link[-4:]}; log('CSC',link,link2)
except Exception as e: src['ofcsc']={'error':str(e)}; log('CSC FAILED',e)
# Companies House basic company data (monthly)
try:
    html=http('https://download.companieshouse.gov.uk/en_output.html').decode()
    f=sorted(set(re.findall(r'BasicCompanyDataAsOneFile-\d{4}-\d{2}-\d{2}\.zip',html)))[-1]
    download('https://download.companieshouse.gov.uk/'+f,P('src','basic.zip'))
    src['ch']={'file':f,'asOf':f[26:36]}; log('CH',f)
except Exception as e: src['ch']={'error':str(e)}; log('CH FAILED',e)
# PSC snapshot + monthly accounts: listed here, streamed later
html=http('https://download.companieshouse.gov.uk/en_pscdata.html').decode()
psc=sorted(set(re.findall(r'psc-snapshot-\d{4}-\d{2}-\d{2}_\d+of\d+\.zip',html)))
src['psc']={'files':psc,'asOf':psc[0][13:23] if psc else None}
html=http('https://download.companieshouse.gov.uk/en_monthlyaccountsdata.html').decode()
acc=sorted(set(re.findall(r'Accounts_Monthly_Data-[A-Za-z]+\d{4}\.zip',html)),key=lambda n:(int(n[-8:-4]),MON[re.sub(r'\d','',n[22:-4]).lower()]))[-12:]
src['acc']={'files':acc,'asOf':acc[-1] if acc else None}
json.dump(src,open(P('sources.json'),'w'),indent=1); log('fetch done')
