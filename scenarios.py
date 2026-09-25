"""
Phase 5: Hotspot Detection + Cooling Scenarios
===============================================
Flags UHI hotspots, computes counterfactual cooling scenarios,
and assembles the final grid_output.geojson that powers the frontend.

Inputs:
  - data/kochi_grid_features.csv   (Phase 3)
  - data/kochi_grid.geojson        (Phase 3 - grid geometries)
  - model/model.pkl                (Phase 4)
  - model/shap_values.json         (Phase 4)

Outputs:
  - data/grid_output.geojson       (THE key file for the entire app)
"""

import os
import json
import numpy as np
import pandas as pd
import geopandas as gpd
import joblib
from pathlib import Path
from shapely.geometry import mapping

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "model"

FEATURES_CSV = DATA_DIR / "kochi_grid_features.csv"
GRID_GEOJSON = DATA_DIR / "kochi_grid.geojson"
MODEL_PATH = MODEL_DIR / "model.pkl"
SHAP_PATH = MODEL_DIR / "shap_values.json"
OUTPUT_PATH = DATA_DIR / "grid_output.geojson"

# Hotspot threshold (z-score)
HOTSPOT_ZSCORE = 1.5

# Feature columns (must match training - clean 5 features)
FEATURE_COLS = [
    "ndvi_mean",
    "ndbi_mean",
    "building_density",
    "road_density",
    "dist_to_green_m",
]

# Human-readable names
FEATURE_NAMES = {
    "ndvi_mean": "Vegetation Index (NDVI)",
    "ndbi_mean": "Built-up Index (NDBI)",
    "building_density": "Building Density",
    "road_density": "Road Density",
    "dist_to_green_m": "Distance to Green Space (m)",
}

# Scenario configurations: what-if NDVI increases
NDVI_SCENARIOS = [10, 20, 30]  # percent increase in NDVI


def main():
    print("=" * 60)
    print("PHASE 5: Hotspot Detection + Cooling Scenarios")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Load all inputs
    # ------------------------------------------------------------------
    print("\n1. Loading inputs...")

    df = pd.read_csv(FEATURES_CSV)
    print(f"   Features CSV: {len(df)} cells")

    grid_gdf = gpd.read_file(GRID_GEOJSON)
    print(f"   Grid GeoJSON: {len(grid_gdf)} geometries")

    model = joblib.load(str(MODEL_PATH))
    print(f"   Model loaded: {type(model).__name__}")

    with open(SHAP_PATH, "r") as f:
        shap_data = json.load(f)
    print(f"   SHAP data loaded: {len(shap_data['cells'])} cells")

    # Build SHAP lookup by cell_id
    shap_lookup = {cell["cell_id"]: cell for cell in shap_data["cells"]}

    # ------------------------------------------------------------------
    # 2. Hotspot detection
    # ------------------------------------------------------------------
    print("\n2. Detecting hotspots...")

    lst_mean = df["lst_mean"].mean()
    lst_std = df["lst_mean"].std()
    df["lst_zscore"] = (df["lst_mean"] - lst_mean) / lst_std
    df["is_hotspot"] = df["lst_zscore"] > HOTSPOT_ZSCORE

    n_hotspots = df["is_hotspot"].sum()
    print(f"   LST mean: {lst_mean:.2f} C, std: {lst_std:.2f} C")
    print(f"   Hotspot threshold (z > {HOTSPOT_ZSCORE}): LST > {lst_mean + HOTSPOT_ZSCORE * lst_std:.2f} C")
    print(f"   Hotspots found: {n_hotspots} / {len(df)} cells ({n_hotspots/len(df)*100:.1f}%)")

    # Also detect coldspots (for the map)
    df["is_coldspot"] = df["lst_zscore"] < -HOTSPOT_ZSCORE
    n_coldspots = df["is_coldspot"].sum()
    print(f"   Coldspots found: {n_coldspots} / {len(df)} cells ({n_coldspots/len(df)*100:.1f}%)")

    # Categorize zones
    def categorize(z):
        if z > HOTSPOT_ZSCORE:
            return "hotspot"
        elif z > 0.5:
            return "warm"
        elif z > -0.5:
            return "neutral"
        elif z > -HOTSPOT_ZSCORE:
            return "cool"
        else:
            return "coldspot"

    df["zone_type"] = df["lst_zscore"].apply(categorize)
    zone_counts = df["zone_type"].value_counts()
    print(f"\n   Zone distribution:")
    for zone, count in zone_counts.items():
        print(f"     {zone:12s}: {count:4d} cells")

    # ------------------------------------------------------------------
    # 3. Cooling scenarios (counterfactual predictions)
    # ------------------------------------------------------------------
    print("\n3. Computing cooling scenarios...")

    # For each cell, simulate greening interventions
    scenarios_all = []

    X_original = df[FEATURE_COLS].values
    lst_original = model.predict(X_original)

    for pct in NDVI_SCENARIOS:
        # Create modified features
        X_modified = X_original.copy()

        # Feature indices we modify for greening scenario
        ndvi_idx = FEATURE_COLS.index("ndvi_mean")
        ndbi_idx = FEATURE_COLS.index("ndbi_mean")
        dist_idx = FEATURE_COLS.index("dist_to_green_m")

        # Increase NDVI (e.g. +10% = +0.10)
        ndvi_increase = pct / 100.0
        X_modified[:, ndvi_idx] = np.clip(X_modified[:, ndvi_idx] + ndvi_increase, -1, 1)

        # Decrease NDBI proportionally (greening converts built-up surface to vegetative cover)
        X_modified[:, ndbi_idx] = X_modified[:, ndbi_idx] - ndvi_increase * 0.3

        # Distance to green space: greening a cell reduces its effective distance to green space
        X_modified[:, dist_idx] = np.maximum(0, X_modified[:, dist_idx] - ndvi_increase * 500.0)

        # Predict new LST
        lst_modified = model.predict(X_modified)
        delta = lst_original - lst_modified  # positive = cooling
        delta = np.clip(delta, 0, None)  # vegetation should never increase temperature

        scenarios_all.append({
            "pct": pct,
            "delta": delta,
            "mean_cooling": delta.mean(),
            "max_cooling": delta.max(),
            "hotspot_cooling": delta[df["is_hotspot"].values].mean() if n_hotspots > 0 else 0,
        })

        print(f"   +{pct}% NDVI: avg cooling = {delta.mean():.3f} C, "
              f"max = {delta.max():.3f} C, "
              f"hotspot avg = {scenarios_all[-1]['hotspot_cooling']:.3f} C")

    # ------------------------------------------------------------------
    # 4. Cluster adjacent hotspots into zones
    # ------------------------------------------------------------------
    print("\n4. Clustering adjacent hotspots...")

    # Simple spatial clustering: assign each hotspot to a zone based on proximity
    hotspot_cells = df[df["is_hotspot"]].copy()
    if len(hotspot_cells) > 0:
        # Merge with grid geometries to get spatial info
        hotspot_gdf = grid_gdf[grid_gdf["cell_id"].isin(hotspot_cells["cell_id"])].copy()

        # Use DBSCAN-like approach: buffer each hotspot and dissolve overlapping ones
        from shapely.ops import unary_union
        buffered = hotspot_gdf.geometry.buffer(0.005)  # ~500m buffer in degrees
        merged = unary_union(buffered)

        # Assign zone IDs
        if merged.geom_type == "Polygon":
            zones = [merged]
        else:
            zones = list(merged.geoms)

        zone_map = {}
        for zone_id, zone_geom in enumerate(zones):
            for _, row in hotspot_gdf.iterrows():
                if zone_geom.contains(row.geometry.centroid):
                    zone_map[row["cell_id"]] = f"Zone {zone_id + 1}"

        print(f"   Identified {len(zones)} hotspot clusters")
        for zone_id, zone_geom in enumerate(zones):
            count = sum(1 for v in zone_map.values() if v == f"Zone {zone_id + 1}")
            print(f"     Zone {zone_id + 1}: {count} cells")
    else:
        zone_map = {}
        print("   No hotspots to cluster")

    # ------------------------------------------------------------------
    # 5. Assemble final GeoJSON
    # ------------------------------------------------------------------
    print("\n5. Assembling grid_output.geojson...")

    features = []
    for idx, row in df.iterrows():
        cell_id = int(row["cell_id"])

        # Get geometry from grid GeoJSON
        grid_row = grid_gdf[grid_gdf["cell_id"] == cell_id]
        if len(grid_row) == 0:
            continue
        geometry = mapping(grid_row.iloc[0].geometry)

        # Get SHAP data
        shap_cell = shap_lookup.get(cell_id, {})
        top_drivers = shap_cell.get("top_drivers", [])

        # Build scenarios dict
        scenarios = {}
        for s in scenarios_all:
            key = f"ndvi_plus_{s['pct']}"
            scenarios[key] = round(float(s["delta"][idx]), 4)

        # Build properties
        properties = {
            "cell_id": cell_id,
            "lon": round(float(row["lon"]), 6),
            "lat": round(float(row["lat"]), 6),
            "lst": round(float(row["lst_mean"]), 2),
            "lst_zscore": round(float(row["lst_zscore"]), 3),
            "ndvi": round(float(row["ndvi_mean"]), 4),
            "ndbi": round(float(row["ndbi_mean"]), 4),
            "building_count": int(row["building_count"]),
            "building_density": round(float(row["building_density"]), 4),
            "road_density": round(float(row["road_density"]), 6),
            "green_fraction": round(float(row["green_fraction"]), 4),
            "impervious_fraction": round(float(row["impervious_fraction"]), 4),
            "dist_to_green_m": round(float(row["dist_to_green_m"]), 1),
            "is_hotspot": bool(row["is_hotspot"]),
            "is_coldspot": bool(row["is_coldspot"]),
            "zone_type": row["zone_type"],
            "hotspot_zone": zone_map.get(cell_id, None),
            "top_drivers": top_drivers[:5],
            "scenarios": scenarios,
            "predicted_lst": shap_cell.get("predicted_lst", None),
            "shap_expected_value": shap_cell.get("expected_value", None),
        }

        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": properties,
        })

    # Build the full GeoJSON with metadata
    output = {
        "type": "FeatureCollection",
        "metadata": {
            "city": "Kochi",
            "grid_size_m": 500,
            "total_cells": len(features),
            "hotspot_count": int(n_hotspots),
            "coldspot_count": int(n_coldspots),
            "lst_mean": round(float(lst_mean), 2),
            "lst_std": round(float(lst_std), 2),
            "hotspot_threshold": round(float(lst_mean + HOTSPOT_ZSCORE * lst_std), 2),
            "zone_distribution": {str(k): int(v) for k, v in zone_counts.items()},
            "scenarios_available": [f"ndvi_plus_{pct}" for pct in NDVI_SCENARIOS],
            "scenario_summary": [
                {
                    "scenario": f"ndvi_plus_{s['pct']}",
                    "label": f"+{s['pct']}% Vegetation",
                    "mean_cooling_c": round(float(s["mean_cooling"]), 3),
                    "max_cooling_c": round(float(s["max_cooling"]), 3),
                    "hotspot_avg_cooling_c": round(float(s["hotspot_cooling"]), 3),
                }
                for s in scenarios_all
            ],
            "global_shap_importance": shap_data["global_importance"][:10],
            "feature_names": FEATURE_NAMES,
            "model_metrics": json.load(open(MODEL_DIR / "metrics.json"))["test"],
        },
        "features": features,
    }

    # Write output
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f)
    file_size_mb = OUTPUT_PATH.stat().st_size / (1024 * 1024)
    print(f"   Saved: {OUTPUT_PATH} ({file_size_mb:.1f} MB)")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("PHASE 5 SUMMARY")
    print("=" * 60)
    print(f"Total cells:        {len(features)}")
    print(f"Hotspots:           {n_hotspots} cells (z > {HOTSPOT_ZSCORE})")
    print(f"Coldspots:          {n_coldspots} cells (z < -{HOTSPOT_ZSCORE})")
    print(f"Hotspot clusters:   {len(zones) if len(hotspot_cells) > 0 else 0}")
    print(f"\nCooling scenarios (hotspot average):")
    for s in scenarios_all:
        print(f"  +{s['pct']}% vegetation -> {s['hotspot_cooling']:.2f} C cooling")
    print(f"\nOutput: {OUTPUT_PATH}")
    print(f"File size: {file_size_mb:.1f} MB")
    print("=" * 60)
    print("\n>>> grid_output.geojson is ready! The frontend can now consume it. <<<")


if __name__ == "__main__":
    main()
