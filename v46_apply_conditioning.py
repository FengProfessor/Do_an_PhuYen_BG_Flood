"""Apply only evidence-approved V46 cuts and verify the output cell-by-cell."""
from __future__ import annotations
import argparse,hashlib,json,shutil
from pathlib import Path
import numpy as np,pandas as pd,rasterio

ROOT=Path(r"D:/VTP")
BASE=ROOT/"05-Du-lieu-GIS/PhuYen_DEM_30m_V41.asc"
CUTS=ROOT/"V46_topology_20260930/V46_proposed_cut_cells.csv"
TOPO_SUM=ROOT/"V46_topology_20260930/V46_topology_summary.json"
OUT=ROOT/"05-Du-lieu-GIS/PhuYen_DEM_30m_V46.asc"
AUDIT=ROOT/"V46_audit_20260930"

def sha256(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
 return h.hexdigest()

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--base',type=Path,default=BASE); ap.add_argument('--cuts',type=Path,default=CUTS); ap.add_argument('--topology-summary',type=Path,default=TOPO_SUM); ap.add_argument('--out',type=Path,default=OUT); ap.add_argument('--audit-dir',type=Path,default=AUDIT); ap.add_argument('--include-bounded',action='store_true'); a=ap.parse_args(); a.audit_dir.mkdir(parents=True,exist_ok=True)
 topo=json.loads(a.topology_summary.read_text(encoding='utf-8')); cuts=pd.read_csv(a.cuts)
 allowed=['AUTO_APPROVE_STRICT']+(['REVIEW_APPROVE_BOUNDED'] if a.include_bounded else [])
 approved=cuts[cuts.decision.isin(allowed)].copy()
 if approved.empty: raise RuntimeError('No evidence-approved cut cells; refusing to create a nominal V46 identical to V41')
 if approved.duplicated(['row','col']).any():
  approved=approved.sort_values('proposed_z_m').drop_duplicates(['row','col'],keep='first')
 with rasterio.open(a.base) as src:
  base=src.read(1).astype(np.float64); profile=src.profile.copy(); transform=src.transform; crs=src.crs; nodata=src.nodata; shape=src.shape
 out=base.copy(); applied=[]
 for rec in approved.itertuples(index=False):
  r=int(rec.row); c=int(rec.col); orig=float(base[r,c]); prop=float(rec.proposed_z_m); cut=orig-prop
  if not np.isfinite(orig) or orig==nodata: raise RuntimeError(f'invalid base cell {r},{c}')
  if abs(orig-float(rec.original_z_m))>0.002: raise RuntimeError(f'base/cut CSV mismatch at {r},{c}: {orig} vs {rec.original_z_m}')
  if cut<=0 or cut>3.000001: raise RuntimeError(f'cut out of global bound at {r},{c}: {cut}')
  if rec.decision=='AUTO_APPROVE_STRICT' and cut>1.000001: raise RuntimeError(f'strict cut exceeds 1m at {r},{c}: {cut}')
  out[r,c]=prop; applied.append({'component_id':int(rec.component_id),'row':r,'col':c,'x':float(rec.x),'y':float(rec.y),'original_z_m':orig,'conditioned_z_m':prop,'cut_depth_m':cut,'decision':rec.decision,'osm_way_id':int(rec.osm_way_id),'hydrorivers_id':int(rec.hydrorivers_id),'jrc_occurrence_buffer_max_pct':float(rec.jrc_occurrence_buffer_max_pct),'upstream_area_buffer_max_km2':float(rec.upstream_area_buffer_max_km2),'reason_code':str(rec.reason_code)})
 diff=out-base; changed=np.abs(diff)>1e-9; expected=np.zeros(shape,bool); expected[approved.row.astype(int),approved.col.astype(int)]=True
 if not np.array_equal(changed,expected): raise RuntimeError(f'diff mask mismatch: changed={changed.sum()} expected={expected.sum()}')
 if np.any(diff[changed]>=0): raise RuntimeError('V46 contains non-lowering modifications')
 if np.any(~np.isfinite(out[base!=nodata])): raise RuntimeError('NaN/Inf introduced')
 p=profile.copy(); p.update(driver='AAIGrid',dtype='float32',count=1,nodata=nodata)
 a.out.parent.mkdir(parents=True,exist_ok=True)
 with rasterio.open(a.out,'w',**p) as dst: dst.write(out.astype(np.float32),1)
 base_prj=a.base.with_suffix('.prj'); out_prj=a.out.with_suffix('.prj')
 if base_prj.exists(): shutil.copy2(base_prj,out_prj)
 with rasterio.open(a.out) as chk:
  reread=chk.read(1).astype(np.float64)
  if chk.shape!=shape or chk.transform!=transform or chk.nodata!=nodata: raise RuntimeError('output grid metadata mismatch')
 # AAIGrid roundtrip tolerance follows 3-decimal source precision.
 od=reread-base; och=np.abs(od)>0.001
 if int(och.sum())!=int(expected.sum()): raise RuntimeError(f'roundtrip changed count mismatch: {och.sum()} != {expected.sum()}')
 applied_path=a.audit_dir/'V46_applied_cells.csv'; pd.DataFrame(applied).to_csv(applied_path,index=False,encoding='utf-8-sig')
 summary={'status':'V46_HYDROLOGICALLY_CONDITIONED_DEM_CREATED','base_dem':{'path':str(a.base),'sha256':sha256(a.base)},'output_dem':{'path':str(a.out),'sha256':sha256(a.out),'prj':str(out_prj) if out_prj.exists() else None,'prj_sha256':sha256(out_prj) if out_prj.exists() else None},'selection':{'allowed_decisions':allowed,'include_bounded':bool(a.include_bounded),'modified_cells':int(expected.sum()),'modified_area_km2':float(expected.sum()*abs(transform.a*transform.e)/1e6),'cut_depth_min_m':float((-diff[changed]).min()),'cut_depth_median_m':float(np.median(-diff[changed])),'cut_depth_max_m':float((-diff[changed]).max()),'excavation_volume_m3':float((-diff[changed]).sum()*abs(transform.a*transform.e))},'invariants':{'grid_transform_preserved':True,'nodata_preserved':True,'only_approved_cells_modified':True,'only_lowering':True,'sentinel1_2021_used_for_conditioning':False,'base_v41_unchanged':True},'topology_summary_sha256':sha256(a.topology_summary),'applied_cells':str(applied_path)}
 sp=a.audit_dir/'V46_conditioning_summary.json'; sp.write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
 evidence=[a.base,a.cuts,a.topology_summary,ROOT/'V46_inputs/osm_historical_20211125/historical_osm_manifest.json',ROOT/'V46_inputs/JRC_GSW1_3_occurrence_1984_2020_manifest.json',ROOT/'V46_hydro_evidence_20260930/V46_hydro_evidence_manifest.json',ROOT/'V46_seed55_historical_validated_20260930/V46_seed55_validation_manifest.json',ROOT/'V46_topology_20260930/V46_topology_manifest.json']
 outputs=[a.out,applied_path,sp]+([out_prj] if out_prj.exists() else [])
 manifest={'algorithm':str(Path(__file__)),'algorithm_sha256':sha256(Path(__file__)),'inputs':{str(p):sha256(p) for p in evidence},'outputs':{str(p):sha256(p) for p in outputs}}
 mp=a.audit_dir/'V46_conditioning_manifest.json'; mp.write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
 print(json.dumps({'output':str(a.out),'modified_cells':summary['selection']['modified_cells'],'max_cut_m':summary['selection']['cut_depth_max_m'],'sha256':summary['output_dem']['sha256'],'summary':str(sp)},indent=2))
if __name__=='__main__': main()
