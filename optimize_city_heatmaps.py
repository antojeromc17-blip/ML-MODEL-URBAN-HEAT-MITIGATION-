"""
Optimize City UHI Hotspots & Heatmap Thresholds
================================================
Calibrates hotspot thresholds and spatial clusters based on each city's
average temperature and standard deviation, preserving trained ML model outputs.
"""

import json
from pathlib import Path
import numpy as np
from shapely.geometry import shape
from shapely.ops import unary_union

BASE_DIR = Path(__file__).resolve().parent

CONFIGS = {
    "kochi": {
        "path": BASE_DIR / "data" / "grid_output.geojson",
        "hs_threshold": 40.15,
        "cs_threshold": 28.5,
    },
    "chennai": {
        "path": BASE_DIR / "data" / "chennai" / "grid_output.geojson",
        "hs_threshold": 44.20,
        "cs_threshold": 28.0,
    },
    "bangalore": {
        "path": BASE_DIR / "data" / "bangalore" / "grid_output.geojson",
        "hs_threshold": 42.95,
        "cs_threshold": 32.0,
    },
    "delhi": {
        "path": BASE_DIR / "data" / "delhi" / "grid_output.geojson",
        "hs_threshold": 44.40,
        "cs_threshold": 30.0,
    },
    "mumbai": {
        "path": BASE_DIR / "data" / "mumbai" / "grid_output.geojson",
        "hs_threshold": 42.00,
        "cs_threshold": 27.0,
    },
}

def optimize_city(city_name, cfg):
    file_path = cfg["path"]
    if not file_path.exists():
        print(f"Skipping {city_name}: {file_path} not found.")
        return

    print(f"\nProcessing {city_name.upper()} ({file_path})...")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])
    if not features:
        print(f"No features in {city_name}")
        return

    lsts = np.array([f["properties"]["lst"] for f in features])
    mean_lst = float(np.mean(lsts))
    std_lst = float(np.std(lsts))

    hs_th = cfg["hs_threshold"]
    cs_th = cfg["cs_threshold"]

    hs_mask = lsts >= hs_th
    cs_mask = lsts <= cs_th
    hotspot_count = int(hs_mask.sum())
    coldspot_count = int(cs_mask.sum())

    # Spatial clustering of hotspot cells into zones
    hs_indices = [i for i, m in enumerate(hs_mask) if m]
    zone_map = {}

    if hs_indices:
        hs_geoms = [shape(features[i]["geometry"]) for i in hs_indices]
        # Buffer each cell by ~600m to merge contiguous/adjacent hotspot cells
        buffered = [g.buffer(0.006) for g in hs_geoms]
        merged = unary_union(buffered)
        zones = [merged] if merged.geom_type == "Polygon" else list(merged.geoms)

        zone_cells = [[] for _ in zones]
        for idx_in_hs, i in enumerate(hs_indices):
            centroid = hs_geoms[idx_in_hs].centroid
            for zid, zg in enumerate(zones):
                if zg.contains(centroid):
                    zone_cells[zid].append(features[i]["properties"]["cell_id"])
                    break

        # Sort zones by number of cells descending
        sorted_zones = sorted(enumerate(zone_cells), key=lambda x: len(x[1]), reverse=True)
        for rank, (_, cell_ids) in enumerate(sorted_zones, start=1):
            for cid in cell_ids:
                zone_map[cid] = f"Zone {rank}"

    # Categorize each cell into zone_type
    zone_distribution = {"hotspot": 0, "warm": 0, "neutral": 0, "cool": 0, "coldspot": 0}

    for i, feat in enumerate(features):
        props = feat["properties"]
        lst = props["lst"]
        is_hs = bool(hs_mask[i])
        is_cs = bool(cs_mask[i])

        if is_hs:
            z_type = "hotspot"
        elif lst >= (mean_lst + 0.5 * std_lst):
            z_type = "warm"
        elif lst <= cs_th:
            z_type = "coldspot"
        elif lst <= (mean_lst - 0.5 * std_lst):
            z_type = "cool"
        else:
            z_type = "neutral"

        props["is_hotspot"] = is_hs
        props["is_coldspot"] = is_cs
        props["zone_type"] = z_type
        props["hotspot_zone"] = zone_map.get(props["cell_id"], None)
        zone_distribution[z_type] += 1

    # Recalculate scenario summary hotspot cooling
    meta = data.get("metadata", {})
    meta["hotspot_count"] = hotspot_count
    meta["coldspot_count"] = coldspot_count
    meta["hotspot_threshold"] = round(hs_th, 2)
    meta["coldspot_threshold"] = round(cs_th, 2)
    meta["zone_distribution"] = zone_distribution

    scenario_summary = meta.get("scenario_summary", [])
    for s_entry in scenario_summary:
        scen_key = s_entry.get("scenario")
        if scen_key:
            deltas = np.array([f["properties"]["scenarios"].get(scen_key, 0.0) for f in features])
            hs_cooling = float(deltas[hs_mask].mean()) if hotspot_count > 0 else 0.0
            s_entry["hotspot_avg_cooling_c"] = round(hs_cooling, 3)

    # Save updated GeoJSON
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    print(f"  Updated {city_name}: {hotspot_count} hotspots (threshold {hs_th} C), {coldspot_count} coldspots")
    print(f"  Zone distribution: {zone_distribution}")
    for s in scenario_summary:
        print(f"    {s.get('label')}: hotspot avg cooling = {s.get('hotspot_avg_cooling_c')} C")

def main():
    for city, cfg in CONFIGS.items():
        optimize_city(city, cfg)
    print("\nAll cities successfully optimized!")

if __name__ == "__main__":
    main()
