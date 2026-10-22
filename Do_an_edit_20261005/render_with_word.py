"""Use the packaged render_docx rasterizer with native Word for PDF conversion.

Bundled LibreOffice is unavailable on this Windows runtime. This adapter never
uses installed LibreOffice and does not change the managed renderer package.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

WORK=Path(r"D:\VTP\Do_an_edit_20261005")
SKILL=Path(r"C:\Users\CuongHM\.codex\plugins\cache\openai-primary-runtime\documents\26.909.12148\skills\documents")
POPLER=Path(r"C:\Users\CuongHM\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin")
os.environ['PATH']=str(POPLER)+os.pathsep+os.environ.get('PATH','')
spec=importlib.util.spec_from_file_location('packaged_render_docx',SKILL/'render_docx.py')
renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)

def word_convert(input_path,user_profile,convert_tmp_dir,stem,*,verbose=False):
    pdf=Path(convert_tmp_dir)/(stem+'.pdf')
    command=[r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
             '-File',str(WORK/'word_export_for_qa.ps1'),'-InputPath',input_path,'-PdfPath',str(pdf)]
    result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=240,creationflags=subprocess.CREATE_NO_WINDOW)
    log={'converter':'Microsoft Word 16 native COM export','managed_renderer':str(SKILL/'render_docx.py'),
         'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
    (WORK/'word_conversion_log.json').write_text(json.dumps(log,ensure_ascii=False,indent=2),encoding='utf-8')
    if result.returncode!=0 or not pdf.is_file():return '',json.dumps(log)
    print(result.stdout.strip(),flush=True)
    return str(pdf),json.dumps(log)

renderer.convert_to_pdf=word_convert
if __name__=='__main__':
    qa=WORK/(sys.argv[1] if len(sys.argv)>1 else 'qa_v1')
    paths=renderer.rasterize(r"D:\VTP\Do_an_tot_nghiep_PhuYen_BG_Flood_SAR_chinh_sua_20261005.docx",str(qa),150,False,True)
    print(json.dumps({'pages':len(paths),'qa_directory':str(qa)},ensure_ascii=False))
