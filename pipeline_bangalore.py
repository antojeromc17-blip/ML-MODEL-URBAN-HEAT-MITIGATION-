"""
Complete Autonomous Bangalore Pipeline
======================================
1. Feature extraction from satellite rasters (LST, NDVI, NDBI) and OSM (buildings, roads)
2. XGBoost Model Training with Monotonic Physics Constraints & SHAP explainability
3. Hotspot detection & counterfactual cooling scenarios
4. Generation of data/bangalore/grid_output.geojson
"""
import os
import json
import time
import warnings
import numpy as np
import pandas as pd
import geopandas as gpd
from pathlib import Path
from shapely.geometry import box, mapping
from rasterstats import zonal_stats
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import shap
import joblib

warnings.filterwarnings("ignore")

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────
NORTH, SOUTH = 13.05, 12.90
EAST, WEST = 77.70, 77.50
GRID_SIZE_M = 500
UTM_EPSG = 32643  # UTM zone 43N for Bangalore (~77.6°E)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "bangalore"
MODEL_DIR = BASE_DIR / "model" / "bangalore"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

LST_TIF = DATA_DIR / "bangalore_lst.tif"
NDVI_TIF = DATA_DIR / "bangalore_ndvi.tif"
NDBI_TIF = DATA_DIR / "bangalore_ndbi.tif"
BUILDINGS_GEOJSON = DATA_DIR / "bangalore_buildings.geojson"
ROADS_GEOJSON = DATA_DIR / "bangalore_roads.geojson"

FEATURES_CSV = DATA_DIR / "bangalore_grid_features.csv"
GRID_GEOJSON = DATA_DIR / "bangalore_grid.geojson"
GRID_OUTPUT_GEOJSON = DATA_DIR / "grid_output.geojson"

FEATURE_COLS = [
    "ndvi_mean",
    "ndbi_mean",
    "building_density",
    "road_density",
    "dist_to_green_m",
]

FEATURE_NAMES = {
    "ndvi_mean": "Vegetation Index (NDVI)",
    "ndbi_mean": "Built-up Index (NDBI)",
    "building_density": "Building Density",
    "road_density": "Road Density",
    "dist_to_green_m": "Distance to Green Space (m)",
}

HOTSPOT_ZSCORE = 1.5
NDVI_SCENARIOS = [10, 20, 30]

def create_grid(west, south, east, north, cell_size_m):
    print(f"Creating {cell_size_m}m x {cell_size_m}m grid for Bangalore...")
    lat_deg_per_m = 1.0 / 111320.0
    lon_deg_per_m = 1.0 / (111320.0 * np.cos(np.radians((north + south) / 2)))
    cell_lat = cell_size_m * lat_deg_per_m
    cell_lon = cell_size_m * lon_deg_per_m

    cells, cell_ids, lons, lats = [], [], [], []
    cell_id = 0
    lat = south
    while lat < north:
        lon = west
        while lon < east:
            cell = box(lon, lat, lon + cell_lon, lat + cell_lat)
            cells.append(cell)
            cell_ids.append(cell_id)
            lons.append(lon + cell_lon / 2)
            lats.append(lat + cell_lat / 2)
            cell_id += 1
            lon += cell_lon
        lat += cell_lat

    grid = gpd.GeoDataFrame({
        "cell_id": cell_ids,
        "lon": lons,
        "lat": lats,
    }, geometry=cells, crs="EPSG:4326")
    print(f"  Created {len(grid)} grid cells")
    return grid

def extract_raster(grid, tif_path, prefix):
    print(f"  Extracting {prefix} from {tif_path.name}...")
    stats = zonal_stats(grid.geometry, str(tif_path), stats=["mean", "std", "min", "max"], nodata=np.nan)
    stats_df = pd.DataFrame(stats)
    stats_df.columns = [f"{prefix}_{col}" for col in stats_df.columns]
    valid = stats_df[f"{prefix}_mean"].notna().sum()
    print(f"    Valid: {valid}/{len(grid)}")
    return stats_df

def extract_buildings(grid, buildings_path):
    print("  Extracting building footprint features...")
    buildings = gpd.read_file(buildings_path)
    grid_utm = grid.to_crs(epsg=UTM_EPSG)
    buildings_utm = buildings.to_crs(epsg=UTM_EPSG)
    buildings_utm["area_m2"] = buildings_utm.geometry.area
    buildings_utm["centroid"] = buildings_utm.geometry.centroid
    buildings_centroids = buildings_utm.set_geometry("centroid")
    cell_area = grid_utm.geometry.iloc[0].area

    joined = gpd.sjoin(buildings_centroids, grid_utm[["cell_id", "geometry"]], how="inner", predicate="within")
    stats = joined.groupby("cell_id").agg(
        building_count=("geometry", "size"),
        total_building_area=("area_m2", "sum"),
        avg_building_area=("area_m2", "mean")
    ).reset_index()

    stats["building_density"] = stats["total_building_area"] / cell_area
    res = grid[["cell_id"]].merge(stats, on="cell_id", how="left").fillna(0)
    print(f"    Cells with buildings: {(res['building_count'] > 0).sum()}/{len(grid)}")
    return res[["building_count", "building_density", "avg_building_area"]]

def extract_roads(grid, roads_path):
    print("  Extracting road network density...")
    roads = gpd.read_file(roads_path)
    grid_utm = grid.to_crs(epsg=UTM_EPSG)
    roads_utm = roads.to_crs(epsg=UTM_EPSG)
    cell_area = grid_utm.geometry.iloc[0].area

    sindex = roads_utm.sindex
    road_lengths = []
    for _, cell in grid_utm.iterrows():
        cand_idx = list(sindex.intersection(cell.geometry.bounds))
        if cand_idx:
            subset = roads_utm.iloc[cand_idx]
            clipped = gpd.clip(subset, cell.geometry)
            road_lengths.append(clipped.geometry.length.sum())
        else:
            road_lengths.append(0.0)

    res = pd.DataFrame({
        "road_length_m": road_lengths,
        "road_density": [l / cell_area for l in road_lengths]
    })
    print(f"    Cells with roads: {(res['road_density'] > 0).sum()}/{len(grid)}")
    return res

def compute_derived(df):
    print("  Computing derived features...")
    df["albedo_proxy"] = 1 - df["ndbi_mean"].clip(-1, 1)
    df["green_fraction"] = df["ndvi_mean"].clip(0, 1)

    max_bd = df["building_density"].quantile(0.99)
    max_rd = df["road_density"].quantile(0.99)
    df["norm_building_density"] = (df["building_density"] / max_bd).clip(0, 1) if max_bd > 0 else 0
    df["norm_road_density"] = (df["road_density"] / max_rd).clip(0, 1) if max_rd > 0 else 0
    df["impervious_fraction"] = (0.6 * df["norm_building_density"] + 0.4 * df["norm_road_density"]).clip(0, 1)

    green_mask = df["ndvi_mean"] > 0.4
    if green_mask.sum() > 0:
        green_lons = df.loc[green_mask, "lon"].values
        green_lats = df.loc[green_mask, "lat"].values
        distances = []
        for _, row in df.iterrows():
            d_lon = (row["lon"] - green_lons) * 111320 * np.cos(np.radians(row["lat"]))
            d_lat = (row["lat"] - green_lats) * 111320
            distances.append(np.sqrt(d_lon**2 + d_lat**2).min())
        df["dist_to_green_m"] = distances
    else:
        df["dist_to_green_m"] = 0
    return df

def main():
    t0 = time.time()
    print("=" * 60)
    print("STARTING BANGALORE PIPELINE")
    print("=" * 60)

    # 1. Feature Engineering
    grid = create_grid(WEST, SOUTH, EAST, NORTH, GRID_SIZE_M)
    lst_df = extract_raster(grid, LST_TIF, "lst")
    ndvi_df = extract_raster(grid, NDVI_TIF, "ndvi")
    ndbi_df = extract_raster(grid, NDBI_TIF, "ndbi")
    bldg_df = extract_buildings(grid, BUILDINGS_GEOJSON)
    road_df = extract_roads(grid, ROADS_GEOJSON)

    df = grid[["cell_id", "lon", "lat"]].copy()
    df = pd.concat([df, lst_df, ndvi_df, ndbi_df, bldg_df, road_df], axis=1)
    df = compute_derived(df)

    df_valid = df.dropna(subset=["lst_mean"] + FEATURE_COLS).copy()
    print(f"\nValid cells for modeling: {len(df_valid)} / {len(df)}")
    df_valid.to_csv(FEATURES_CSV, index=False)
    
    grid_out = grid[grid["cell_id"].isin(df_valid["cell_id"])].copy()
    grid_out.to_file(GRID_GEOJSON, driver="GeoJSON")

    # 2. Model Training with Monotonic Constraints
    print("\nTraining XGBoost Regressor with Monotonic Constraints...")
    X = df_valid[FEATURE_COLS].values
    y = df_valid["lst_mean"].values

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = XGBRegressor(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,
        random_state=42,
        n_jobs=-1,
        objective="reg:squarederror",
        monotone_constraints=(-1, 1, 1, 1, 1),
    )
    model.fit(X_train, y_train)

    y_pred_test = model.predict(X_test)
    r2 = r2_score(y_test, y_pred_test)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))
    mae = mean_absolute_error(y_test, y_pred_test)
    print(f"  Test Performance: R² = {r2:.4f}, RMSE = {rmse:.3f}°C, MAE = {mae:.3f}°C")

    # Save model
    joblib.dump(model, str(MODEL_DIR / "model.pkl"))

    # 3. SHAP Explainability
    print("\nComputing SHAP values for all cells...")
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)
    expected_value = float(explainer.expected_value)
    mean_abs_shap = np.abs(shap_values).mean(axis=0)

    shap_ranking = sorted(zip(FEATURE_COLS, mean_abs_shap.tolist()), key=lambda x: x[1], reverse=True)
    shap_per_cell = []
    for i in range(len(df_valid)):
        cell_id = int(df_valid.iloc[i]["cell_id"])
        c_shap = shap_values[i]
        drivers = [
            {"name": feat, "display_name": FEATURE_NAMES.get(feat, feat), "shap": round(float(c_shap[j]), 4), "value": round(float(X[i, j]), 4)}
            for j, feat in enumerate(FEATURE_COLS)
        ]
        drivers.sort(key=lambda d: abs(d["shap"]), reverse=True)
        shap_per_cell.append({
            "cell_id": cell_id,
            "expected_value": round(expected_value, 4),
            "predicted_lst": round(float(expected_value + c_shap.sum()), 4),
            "actual_lst": round(float(y[i]), 4),
            "top_drivers": drivers,
            "all_shap": {feat: round(float(c_shap[j]), 4) for j, feat in enumerate(FEATURE_COLS)},
        })

    shap_data = {
        "expected_value": round(expected_value, 4),
        "feature_columns": FEATURE_COLS,
        "feature_names": FEATURE_NAMES,
        "global_importance": [{"name": feat, "display_name": FEATURE_NAMES.get(feat, feat), "mean_abs_shap": round(val, 4)} for feat, val in shap_ranking],
        "cells": shap_per_cell,
    }
    with open(MODEL_DIR / "shap_values.json", "w") as f:
        json.dump(shap_data, f, indent=2)

    # 4. Hotspots & Scenarios
    print("\nDetecting hotspots and simulating scenarios...")
    lst_mean = df_valid["lst_mean"].mean()
    lst_std = df_valid["lst_mean"].std()
    df_valid["lst_zscore"] = (df_valid["lst_mean"] - lst_mean) / lst_std
    df_valid["is_hotspot"] = df_valid["lst_zscore"] > HOTSPOT_ZSCORE
    df_valid["is_coldspot"] = df_valid["lst_zscore"] < -HOTSPOT_ZSCORE

    def categorize(z):
        if z > HOTSPOT_ZSCORE: return "hotspot"
        elif z > 0.5: return "warm"
        elif z > -0.5: return "neutral"
        elif z > -HOTSPOT_ZSCORE: return "cool"
        else: return "coldspot"
    df_valid["zone_type"] = df_valid["lst_zscore"].apply(categorize)

    # Scenarios
    scenarios_res = []
    lst_orig = model.predict(X)
    ndvi_idx = FEATURE_COLS.index("ndvi_mean")
    ndbi_idx = FEATURE_COLS.index("ndbi_mean")
    dist_idx = FEATURE_COLS.index("dist_to_green_m")

    for pct in NDVI_SCENARIOS:
        X_mod = X.copy()
        inc = pct / 100.0
        X_mod[:, ndvi_idx] = np.clip(X_mod[:, ndvi_idx] + inc, -1, 1)
        X_mod[:, ndbi_idx] -= inc * 0.3
        X_mod[:, dist_idx] = np.maximum(0, X_mod[:, dist_idx] - inc * 500.0)
        lst_mod = model.predict(X_mod)
        delta = np.clip(lst_orig - lst_mod, 0, None)
        hotspot_cooling = delta[df_valid["is_hotspot"].values].mean() if df_valid["is_hotspot"].sum() > 0 else 0
        scenarios_res.append({"pct": pct, "delta": delta, "mean_cooling": delta.mean(), "max_cooling": delta.max(), "hotspot_cooling": hotspot_cooling})
        print(f"  +{pct}% Vegetation: avg cooling = {delta.mean():.3f}°C (hotspots: {hotspot_cooling:.3f}°C)")

    # 5. Assemble final GeoJSON
    print("\nAssembling Bangalore grid_output.geojson...")
    shap_lookup = {c["cell_id"]: c for c in shap_per_cell}
    features = []
    for idx, (_, row) in enumerate(df_valid.iterrows()):
        cid = int(row["cell_id"])
        geom_row = grid_out[grid_out["cell_id"] == cid]
        if len(geom_row) == 0: continue
        geometry = mapping(geom_row.iloc[0].geometry)
        s_cell = shap_lookup.get(cid, {})

        scen_dict = {f"ndvi_plus_{s['pct']}": round(float(s["delta"][idx]), 4) for s in scenarios_res}

        props = {
            "cell_id": cid,
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
            "top_drivers": s_cell.get("top_drivers", [])[:5],
            "scenarios": scen_dict,
            "predicted_lst": s_cell.get("predicted_lst", None),
            "shap_expected_value": s_cell.get("expected_value", None),
        }
        features.append({"type": "Feature", "geometry": geometry, "properties": props})

    final_geojson = {
        "type": "FeatureCollection",
        "metadata": {
            "city": "Bangalore",
            "grid_size_m": GRID_SIZE_M,
            "total_cells": len(features),
            "hotspot_count": int(df_valid["is_hotspot"].sum()),
            "coldspot_count": int(df_valid["is_coldspot"].sum()),
            "lst_mean": round(float(lst_mean), 2),
            "lst_std": round(float(lst_std), 2),
            "hotspot_threshold": round(float(lst_mean + HOTSPOT_ZSCORE * lst_std), 2),
            "zone_distribution": {str(k): int(v) for k, v in df_valid["zone_type"].value_counts().items()},
            "scenarios_available": [f"ndvi_plus_{pct}" for pct in NDVI_SCENARIOS],
            "scenario_summary": [
                {
                    "scenario": f"ndvi_plus_{s['pct']}",
                    "label": f"+{s['pct']}% Vegetation",
                    "mean_cooling_c": round(float(s["mean_cooling"]), 3),
                    "max_cooling_c": round(float(s["max_cooling"]), 3),
                    "hotspot_avg_cooling_c": round(float(s["hotspot_cooling"]), 3),
                } for s in scenarios_res
            ],
            "global_shap_importance": shap_data["global_importance"],
            "feature_names": FEATURE_NAMES,
            "model_metrics": {"r2": round(r2, 4), "rmse": round(rmse, 4), "mae": round(mae, 4)},
        },
        "features": features
    }

    with open(GRID_OUTPUT_GEOJSON, "w") as f:
        json.dump(final_geojson, f)

    file_size_mb = GRID_OUTPUT_GEOJSON.stat().st_size / (1024 * 1024)
    print(f"\nSaved Bangalore GeoJSON: {GRID_OUTPUT_GEOJSON} ({file_size_mb:.2f} MB)")
    print(f"Total pipeline time: {time.time() - t0:.1f}s")
    print("BANGALORE PIPELINE COMPLETE!")

if __name__ == "__main__":
    main()
