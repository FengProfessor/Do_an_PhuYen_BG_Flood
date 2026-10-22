"""Fetch an auditable historical OSM waterway snapshot for V46.

Resumes valid tile files and recursively subdivides a tile when an Overpass
attic query times out. Every response is stored byte-for-byte and hashed.
"""
from __future__ import annotations
import argparse, hashlib, json, time, xml.etree.ElementTree as ET
from pathlib import Path
import requests, rasterio
from rasterio.warp import transform_bounds

ROOT=Path(r"D:/VTP")
DEFAULT_DEM=ROOT/"05-Du-lieu-GIS/PhuYen_DEM_30m_V41.asc"
DEFAULT_OUT=ROOT/"V46_inputs/osm_historical_20211125"
DEFAULT_DATE="2021-11-25T00:00:00Z"
ENDPOINTS=("https://overpass-api.de/api/interpreter","https://overpass.private.coffee/api/interpreter")
UA="V46-hydro-conditioning-audit/1.0"

def sha256(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
    return h.hexdigest()

def query(date:str,bbox)->str:
    s,w,n,e=bbox
    return f'[out:xml][timeout:60][date:"{date}"];way["waterway"~"^(river|stream|canal|drain)$"]({s:.8f},{w:.8f},{n:.8f},{e:.8f});out geom meta;'

def fetch(q:str,timeout:int=75):
    errors=[]
    for endpoint in ENDPOINTS:
        try:
            r=requests.post(endpoint,data=q.encode('utf-8'),headers={'User-Agent':UA,'Content-Type':'application/x-www-form-urlencoded'},timeout=timeout)
            if r.ok and b'<osm' in r.content:
                return endpoint,r.content
            errors.append(f"{endpoint}: HTTP {r.status_code}: {r.text[:120]}")
        except Exception as e:
            errors.append(f"{endpoint}: {type(e).__name__}: {e}")
    raise RuntimeError(' | '.join(errors))

def inspect_bytes(content:bytes,snapshot:str):
    root=ET.fromstring(content); ways=root.findall('way'); timestamps=[]; ids=[]
    for way in ways:
        ids.append(int(way.attrib['id']))
        if way.attrib.get('timestamp'): timestamps.append(way.attrib['timestamp'])
    if timestamps and max(timestamps)>snapshot:
        raise RuntimeError(f"post-snapshot way returned: {max(timestamps)} > {snapshot}")
    return ways,ids,timestamps

def split4(bbox):
    s,w,n,e=bbox; my=(s+n)/2; mx=(w+e)/2
    return [(s,w,my,mx),(s,mx,my,e),(my,w,n,mx),(my,mx,n,e)]

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--dem',type=Path,default=DEFAULT_DEM); ap.add_argument('--out-dir',type=Path,default=DEFAULT_OUT); ap.add_argument('--snapshot',default=DEFAULT_DATE); ap.add_argument('--tiles',type=int,default=4); ap.add_argument('--max-split-depth',type=int,default=2); a=ap.parse_args(); a.out_dir.mkdir(parents=True,exist_ok=True)
    with rasterio.open(a.dem) as ds: bounds=transform_bounds(ds.crs,'EPSG:4326',*ds.bounds,densify_pts=21)
    w,s,e,n=map(float,bounds); records=[]; all_way_ids=set(); all_ts=[]
    def process(label,bbox,depth=0):
        fp=a.out_dir/f"osm_hist_20211125_tile_{label}.osm"
        if fp.exists() and fp.stat().st_size>100:
            content=fp.read_bytes(); ways,ids,tss=inspect_bytes(content,a.snapshot)
            records.append({'path':str(fp),'sha256':sha256(fp),'bytes':fp.stat().st_size,'way_elements':len(ways),'endpoint':'RESUMED_EXISTING','bbox':list(bbox),'query':query(a.snapshot,bbox),'depth':depth}); all_way_ids.update(ids); all_ts.extend(tss); return
        q=query(a.snapshot,bbox)
        try:
            endpoint,content=fetch(q); ways,ids,tss=inspect_bytes(content,a.snapshot); fp.write_bytes(content)
            records.append({'path':str(fp),'sha256':sha256(fp),'bytes':fp.stat().st_size,'way_elements':len(ways),'endpoint':endpoint,'bbox':list(bbox),'query':q,'depth':depth}); all_way_ids.update(ids); all_ts.extend(tss)
        except Exception as exc:
            if depth>=a.max_split_depth: raise RuntimeError(f"tile {label} failed at max split depth: {exc}") from exc
            for k,sub in enumerate(split4(bbox)): process(f"{label}s{k}",sub,depth+1)
    for iy in range(a.tiles):
        for ix in range(a.tiles):
            ss=s+(n-s)*iy/a.tiles; nn=s+(n-s)*(iy+1)/a.tiles; ww=w+(e-w)*ix/a.tiles; ee=w+(e-w)*(ix+1)/a.tiles
            process(f"{iy}{ix}",(ss,ww,nn,ee),0)
    manifest={'status':'HISTORICAL_OSM_SNAPSHOT','snapshot_utc':a.snapshot,'source':'OpenStreetMap via Overpass attic/date query','license':'ODbL; OpenStreetMap contributors','dem':str(a.dem),'dem_sha256':sha256(a.dem),'dem_bounds_wgs84':[w,s,e,n],'base_tile_grid':[a.tiles,a.tiles],'max_split_depth':a.max_split_depth,'files':records,'unique_way_ids':len(all_way_ids),'returned_way_timestamp_min':min(all_ts) if all_ts else None,'returned_way_timestamp_max':max(all_ts) if all_ts else None,'acquired_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    mp=a.out_dir/'historical_osm_manifest.json'; mp.write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'unique_way_ids':len(all_way_ids),'files':len(records),'max_timestamp':manifest['returned_way_timestamp_max'],'manifest':str(mp)},indent=2))
if __name__=='__main__': main()
