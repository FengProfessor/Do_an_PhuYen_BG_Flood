"""Conservative V49-A water-object classification.

This module deliberately avoids assigning physical bathymetry.  It converts
object-level evidence into provisional hydrographic classes or an explicit
review queue.  The rules are intentionally conservative because JRC surface
water occurrence is not a bathymetry or water-body-type product.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple


@dataclass(frozen=True)
class ClassificationConfig:
    river_near_m: float = 90.0
    strong_river_fraction: float = 0.05
    estuary_near_ocean_m: float = 600.0
    broad_water_area_km2: float = 2.0
    broad_water_max_line_fraction: float = 0.20


def classify_water_object(
    evidence: Mapping[str, float | int | bool],
    config: ClassificationConfig = ClassificationConfig(),
) -> Tuple[str, str, bool, str]:
    """Return class, confidence, review flag, and explanation.

    Only ``OCEAN`` is treated as a terminal class in V49-A.  Inland classes
    remain candidates until V49-C introduces dedicated lake/reservoir/wetland
    evidence.
    """

    if bool(evidence.get("is_ocean", False)):
        return (
            "OCEAN",
            "HIGH",
            False,
            "Open-water core connected to the eastern marine boundary.",
        )

    hydro_min = float(evidence.get("hydrorivers_min_m", 1.0e12))
    osm_min = float(evidence.get("osm_waterway_min_m", 1.0e12))
    hydro_frac = float(evidence.get("hydrorivers_within_90m_fraction", 0.0))
    osm_frac = float(evidence.get("osm_within_90m_fraction", 0.0))
    ocean_dist = float(evidence.get("distance_to_ocean_m", 1.0e12))
    hydro_count = int(evidence.get("hydrorivers_feature_count", 0))
    area_km2 = float(evidence.get("area_km2", 0.0))

    strong_hydro = (
        hydro_min <= config.river_near_m
        or hydro_frac >= config.strong_river_fraction
        or hydro_count > 0
    )
    strong_osm = (
        osm_min <= config.river_near_m
        or osm_frac >= config.strong_river_fraction
    )

    if ocean_dist <= config.estuary_near_ocean_m and (strong_hydro or strong_osm):
        return (
            "ESTUARY_REVIEW_REQUIRED",
            "MEDIUM",
            True,
            "Persistent water is close to the marine mask and has river/waterway evidence; tidal/backwater treatment must be reviewed.",
        )

    # A HydroRIVERS line commonly passes through reservoirs and lakes.  Large
    # persistent polygons with only sparse line overlap are therefore kept in
    # the open-water review queue instead of being promoted to river geometry.
    if (
        area_km2 >= config.broad_water_area_km2
        and max(hydro_frac, osm_frac) < config.broad_water_max_line_fraction
    ):
        return (
            "OPEN_WATER_REVIEW_REQUIRED",
            "LOW",
            True,
            "Large persistent open-water object has sparse river/waterway line coverage; lake/reservoir/wetland classification requires dedicated evidence.",
        )

    if strong_hydro:
        return (
            "RIVER_CANDIDATE",
            "MEDIUM",
            True,
            "Persistent water overlaps or lies near HydroRIVERS evidence; final river/stream/canal class requires V49-C review.",
        )

    if strong_osm:
        return (
            "OSM_WATERWAY_CANDIDATE",
            "LOW",
            True,
            "Persistent water lies near mapped OSM waterway evidence but lacks strong HydroRIVERS support.",
        )

    return (
        "OPEN_WATER_REVIEW_REQUIRED",
        "LOW",
        True,
        "Persistent JRC open water lacks enough local evidence for a defensible river/lake/reservoir/wetland assignment.",
    )

