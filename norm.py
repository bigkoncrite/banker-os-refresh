import re
def norm(s):
    s=str(s or '').upper().strip()
    s=re.sub(r'\bTRADING AS\b.*$','',s)
    s=s.replace('&',' AND ')
    s=re.sub(r'[^A-Z0-9 ]',' ',s)
    s=re.sub(r'\b(LTD|LIMITED|L T D|PLC|LLP|CIC|C I C|COMPANY|CO)\b',' ',s)
    s=re.sub(r'^THE\b',' ',s)
    return re.sub(r'\s+',' ',s).strip()
