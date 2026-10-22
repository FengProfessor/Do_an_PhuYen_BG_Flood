"""Evaluate published coarse HWM envelopes without inventing exact locations.

The reported coordinates provide geographic envelopes, not pixel locations.
Return modeled wet coverage inside each envelope; absolute WSE errors and
promotion remain unavailable until datum, location and event timing are resolved.
"""
from pathlib import Path
from datetime import datetime, timezone
import json
import netCDF4 as nc
import numpy as np
import pandas as pd
from pyproj import Transformer
from v49_synthesize_hydraulic_bed import sha256_file

PROJECT = Path(__file__).resolve().parent
EVIDENCE = PROJECT / "V49_PUBLIC_EVIDENCE_20261013"


def evaluate_coarse_high_water_marks(result_path, wet_threshold_m=.3):
    table_path = EVIDENCE / "2021_published_high_water_marks_coarse_coordinates.csv"
    registration_path = EVIDENCE / "V49_HWM_DIAGNOSTIC_PREREGISTRATION.json"
    if not registration_path.is_file():
        raise ValueError("HWM diagnostic must be registered before evaluation")
    registration = json.loads(registration_path.read_text(encoding="utf-8"))
    if registration["sha256"] != sha256_file(table_path):
        raise ValueError("Registered HWM evidence checksum mismatch")
    if wet_threshold_m != registration["wet_threshold_m"]:
        raise ValueError("HWM diagnostic threshold differs from registration")
    table = pd.read_csv(table_path)
    transformer = Transformer.from_crs(4326, 32649, always_xy=True)
    rows = []
    with nc.Dataset(result_path) as dataset:
        x, y = (np.asarray(dataset[key][:], dtype=float) for key in ("x", "y"))
        times = np.asarray(np.ma.filled(dataset["time"][:], np.nan), dtype=float)
        if times.size == 0 or not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
            raise ValueError("Cannot evaluate corrupt output times")
        for _, point in table.iterrows():
            lon, lat = point.longitude_reported, point.latitude_reported
            lons = [lon-.005, lon+.005, lon-.005, lon+.005]
            lats = [lat-.005, lat-.005, lat+.005, lat+.005]
            xx, yy = transformer.transform(lons,lats)
            cols = np.flatnonzero((x >= min(xx)) & (x <= max(xx)))
            row_ids = np.flatnonzero((y >= min(yy)) & (y <= max(yy)))
            item = {"point_id": int(point.point_id), "reported_longitude": float(lon), "reported_latitude": float(lat),
                    "reported_mark_elevation_m": float(point.observed_mark_elevation_m),
                    "evaluation": "COARSE_GEOGRAPHIC_ENVELOPE_DIAGNOSTIC", "absolute_wse_error_computed": False}
            if not len(cols) or not len(row_ids):
                item["status"] = "OUTSIDE_MODEL_DOMAIN"
            else:
                raw = dataset["h"][:, row_ids.min():row_ids.max()+1, cols.min():cols.max()+1]
                depth = np.asarray(np.ma.filled(raw,np.nan),dtype=float)
                maximum = np.max(np.where(np.isfinite(depth),depth,-np.inf),axis=0)
                finite = np.isfinite(maximum)
                item.update(status="MODELLED_ENVELOPE_AVAILABLE", valid_envelope_cells=int(finite.sum()),
                            cells_ever_wet=int((finite & (maximum > wet_threshold_m)).sum()),
                            maximum_depth_anywhere_in_envelope_m=float(maximum[finite].max()) if finite.any() else None)
            rows.append(item)
    return {"schema_version": "V49-coarse-hwm-diagnostic-1", "result_path": str(result_path),
            "evidence_table_sha256": sha256_file(table_path), "record_count": len(rows), "rows": rows,
            "modeled_last_time_h": float(times[-1]/3600.), "wet_threshold_m": wet_threshold_m,
            "absolute_wse_metrics": "UNAVAILABLE_DATUM_AND_EXACT_COORDINATES_UNVERIFIED",
            "interpretation": "A wet envelope does not prove agreement at the surveyed location; an entirely dry modeled envelope requires review, including the incomplete observation-time window.",
            "hydraulic_promotion_ready": False}


def preregister():
    table = EVIDENCE / "2021_published_high_water_marks_coarse_coordinates.csv"
    register = {"schema_version": "V49-extra-evidence-preregistration-1", "registered_at_utc": datetime.now(timezone.utc).isoformat(),
                "evidence_table": str(table), "sha256": sha256_file(table),
                "method": "Compare max modeled depth over available times in each published coordinate rounding envelope",
                "horizontal_crs_assumption": "Geographic WGS84 inferred from regional source context; exact survey CRS remains unverified",
                "wet_threshold_m": .3, "frozen_SAR_experiment_changed": False,
                "absolute_wse_or_pointwise_acceptance_authorized": False}
    path = EVIDENCE / "V49_HWM_DIAGNOSTIC_PREREGISTRATION.json"
    if path.exists():
        prior = json.loads(path.read_text(encoding="utf-8"))
        if prior["sha256"] != register["sha256"]:
            raise RuntimeError("Registered evidence changed")
        return prior
    path.write_text(json.dumps(register, indent=2), encoding="utf-8")
    return register


if __name__ == "__main__":
    from v49_prepare_hydraulic_validation import BASE_RESULT
    preregister()
    report = evaluate_coarse_high_water_marks(BASE_RESULT)
    (EVIDENCE / "V49_BASE_coarse_HWM_diagnostics.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({"records":len(report["rows"]),"model_last_h":report["modeled_last_time_h"],
                      "entirely_dry_envelopes": [r["point_id"] for r in report["rows"] if r.get("cells_ever_wet")==0]},indent=2))
