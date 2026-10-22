from docx import Document
from pathlib import Path
import re, sys, zipfile
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
p=Path(r'D:\VTP\Do_an_tot_nghiep_PhuYen_BG_Flood_SAR.docx')
d=Document(p)
nums=[]
for para in d.paragraphs:
    nums += [int(x) for x in re.findall(r'\[(\d+)\]', para.text)]
print('INLINE_SHAPES', len(d.inline_shapes))
print('CITATIONS_USED', sorted(set(nums)))
print('CITATION_COUNTS', {n:nums.count(n) for n in sorted(set(nums))})
print('MAX', max(nums) if nums else None)
with zipfile.ZipFile(p) as z:
    media=[n for n in z.namelist() if n.startswith('word/media/')]
    print('MEDIA_FILES',len(media))
    for n in media: print(n, z.getinfo(n).file_size)
