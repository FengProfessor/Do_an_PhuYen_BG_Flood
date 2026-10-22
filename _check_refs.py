import re, json, sys, time
from pathlib import Path
import urllib.request
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
text=Path(r'D:\VTP\_extract.txt').read_text(encoding='utf-8')
refs=[]
for line in text.splitlines():
    m=re.match(r'P0(39[8-9]|4[0-3][0-9])\t[^\t]+\t\[(\d+)\]\s+(.*)', line)
    if m:
        refs.append((int(m.group(2)),m.group(3)))
for n,entry in refs:
    doi_m=re.search(r'https?://doi\.org/([^\s]+)',entry)
    if not doi_m:
        print(f'[{n}] NO_DOI | {entry[:120]}')
        continue
    doi=doi_m.group(1).rstrip('.,;)')
    try:
        req=urllib.request.Request('https://api.crossref.org/works/'+doi,headers={'User-Agent':'CodexThesisAudit/1.0'})
        with urllib.request.urlopen(req,timeout=20) as resp:
            msg=json.loads(resp.read().decode('utf-8'))['message']
        title=(msg.get('title') or [''])[0]
        year=((msg.get('published-print') or msg.get('published-online') or msg.get('issued') or {}).get('date-parts') or [[None]])[0][0]
        authors='; '.join(' '.join(x for x in [a.get('given',''),a.get('family','')] if x) for a in msg.get('author',[])[:4])
        print(f'[{n}] OK {doi} | {year} | {title} | {authors}')
    except Exception as e:
        print(f'[{n}] ERR {doi} | {e}')

