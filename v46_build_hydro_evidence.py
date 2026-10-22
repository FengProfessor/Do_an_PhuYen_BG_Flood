"""Build audit-only terrain and pre-2021 water evidence for V46."""
from __future__ import annotations
import argparse, hashlib, json, platform
from pathlib import Path
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
import pyflwdir

ROOT=Path(r"D:/VTP")
DEFAULT_DEM=ROOT/"05-Du-lieu-GIS/PhuYen_DEM_30m_V41.asc"
DEFAULT_JRC=ROOT/"V46_inputs/JRC_GSW1_3_occurrence_1984_2020_100E_10N.tif"
DEFAULT_OUT=ROOT/"V46_hydro_evidence_20260930"

def sha256(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
    return h.hexdigest()

def write(path,arr,profile,dtype,nodata,desc,tags):
    p=profile.copy(); p.update(driver='GTiff',dtype=dtype,count=1,compress='deflate',nodata=nodata)
    with rasterio.open(path,'w',**p) as dst:
        dst.write(arr.astype(dtype),1); dst.set_band_description(1,desc); dst.update_tags(**tags)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--dem',type=Path,default=DEFAULT_DEM); ap.add_argument('--jrc',type=Path,default=DEFAULT_JRC); ap.add_argument('--out-dir',type=Path,default=DEFAULT_OUT); a=ap.parse_args(); a.out_dir.mkdir(parents=True,exist_ok=True)
    with rasterio.open(a.dem) as src:
        dem=src.read(1).astype(np.float32); profile=src.profile.copy(); nodata=src.nodata; transform=src.transform; crs=src.crs
    valid=np.isfinite(dem) & (dem!=nodata)
    filled,d8=pyflwdir.dem.fill_depressions(dem,nodata=nodata,outlets='edge',connectivity=8)
    flw=pyflwdir.from_array(d8,ftype='d8',check_ftype=False,transform=transform,latlon=bool(crs and crs.is_geographic),cache=True)
    uparea=flw.upstream_area('km2').astype(np.float32)
    hand1=flw.hand(drain=(uparea>=1.0),elevtn=filled).astype(np.float32)
    hand10=flw.hand(drain=(uparea>=10.0),elevtn=filled).astype(np.float32)
    fill_depth=np.where(valid,filled-dem,nodata).astype(np.float32)
    jrc=np.full(dem.shape,255,dtype=np.uint8)
    with rasterio.open(a.jrc) as src:
        reproject(source=rasterio.band(src,1),destination=jrc,src_transform=src.transform,src_crs=src.crs,src_nodata=src.nodata,dst_transform=transform,dst_crs=crs,dst_nodata=255,resampling=Resampling.nearest)
    tags={'SOURCE_DEM':str(a.dem),'BASE_DEM_MODIFIED':'false','ALGORITHM':'pyflwdir 0.5.12 Wang-Liu depression fill + D8'}
    paths={
      'filled':a.out_dir/'V46_V41_filled_for_routing_only.tif',
      'd8':a.out_dir/'V46_V41_D8.tif',
      'uparea':a.out_dir/'V46_V41_upstream_area_km2.tif',
      'hand1':a.out_dir/'V46_V41_HAND_drain_1km2.tif',
      'hand10':a.out_dir/'V46_V41_HAND_drain_10km2.tif',
      'filldepth':a.out_dir/'V46_V41_fill_depth_m.tif',
      'jrc':a.out_dir/'V46_JRC_GSW1_3_occurrence_1984_2020.tif'}
    write(paths['filled'],np.where(valid,filled,nodata),profile,'float32',nodata,'Routing-only depression-filled V41',tags)
    write(paths['d8'],d8,profile,'uint8',247,'D8 flow direction',tags)
    write(paths['uparea'],uparea,profile,'float32',-9999.0,'Upstream area km2',tags)
    write(paths['hand1'],hand1,profile,'float32',-9999.0,'HAND, drainage >=1 km2',tags)
    write(paths['hand10'],hand10,profile,'float32',-9999.0,'HAND, drainage >=10 km2',tags)
    write(paths['filldepth'],fill_depth,profile,'float32',nodata,'Fill depth used only to derive routing',tags)
    jtags={'SOURCE':str(a.jrc),'SOURCE_SHA256':sha256(a.jrc),'TEMPORAL_COVERAGE':'1984-2020','PRODUCT':'JRC GSW v1.3 occurrence','SENTINEL1_2021_USED':'false'}
    write(paths['jrc'],jrc,profile,'uint8',255,'JRC GSW occurrence 1984-2020 percent',jtags)
    fd=fill_depth[valid]; jv=jrc[jrc!=255]
    summary={'status':'HYDRO_EVIDENCE_ONLY_BASE_DEM_UNCHANGED','base_dem':{'path':str(a.dem),'sha256':sha256(a.dem)},'jrc_source':{'path':str(a.jrc),'sha256':sha256(a.jrc),'temporal_coverage':'1984-2020'},'software':{'python':platform.python_version(),'numpy':np.__version__,'rasterio':rasterio.__version__,'pyflwdir':pyflwdir.__version__},'method':{'flow':'pyflwdir.dem.fill_depressions, Wang & Liu (2006), D8, edge outlets','hand_thresholds_km2':[1.0,10.0],'jrc_resampling':'nearest'},'diagnostics':{'valid_cells':int(valid.sum()),'routing_fill_cells':int((fd>1e-6).sum()),'routing_fill_depth_max_m':float(fd.max()),'routing_fill_depth_p99_m':float(np.quantile(fd,0.99)),'upstream_area_max_km2':float(np.max(uparea[uparea>=0])),'jrc_valid_cells':int(jv.size),'jrc_occurrence_gt0_cells':int((jv>0).sum()),'jrc_occurrence_ge50_cells':int((jv>=50).sum())},'invariants':{'base_dem_modified':False,'sentinel1_2021_used':False,'jrc_ends_before_2021':True},'outputs':{k:str(v) for k,v in paths.items()}}
    sp=a.out_dir/'V46_hydro_evidence_summary.json'; sp.write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    outputs=list(paths.values())+[sp]
    manifest={'algorithm':str(Path(__file__)),'algorithm_sha256':sha256(Path(__file__)),'inputs':{str(a.dem):sha256(a.dem),str(a.jrc):sha256(a.jrc)},'outputs':{str(p):sha256(p) for p in outputs}}
    mp=a.out_dir/'V46_hydro_evidence_manifest.json'; mp.write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'summary':str(sp),'manifest':str(mp),'routing_fill_cells':summary['diagnostics']['routing_fill_cells'],'upstream_area_max_km2':summary['diagnostics']['upstream_area_max_km2']},indent=2))
if __name__=='__main__': main()
