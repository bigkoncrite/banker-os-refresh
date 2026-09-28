import os, re, json, subprocess, datetime as dt, urllib.request, urllib.parse
W=os.environ.get('WORK','.')
def P(*a): return os.path.join(W,*a)
UA={'User-Agent':'Mozilla/5.0 (BankerOS refresh)'}
def http(url,timeout=60):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=timeout) as r: return r.read()
def download(url,dest,timeout=3000):
    subprocess.run(['curl','-sSL','-A',UA['User-Agent'],'-m',str(timeout),'-o',dest,url],check=True)
    if os.path.getsize(dest)<1000: raise RuntimeError('download too small: '+url)
    return dest
def log(*a):
    msg=' '.join(str(x) for x in a); print(msg,flush=True)
    with open(P('log.txt'),'a') as f: f.write(dt.datetime.now().strftime('%H:%M:%S ')+msg+'\n')
def status(key,val):
    p=P('status.json'); s=json.load(open(p)) if os.path.exists(p) else {}
    s[key]=val; json.dump(s,open(p,'w'),indent=1)
