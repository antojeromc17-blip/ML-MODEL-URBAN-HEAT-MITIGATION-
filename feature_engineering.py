"""
Phase 3: Feature Engineering — Grid-based spatial feature extraction.

Creates a uniform 500m x 500m grid over the Kochi bounding box and extracts
per-cell features from all raster (LST, NDVI, NDBI) and vector (buildings, roads)
layers. The output CSV is the input for ML modeling in Phase 4.

Usage:
    pip install rasterio rasterstats geopandas shapely pandas numpy
    python feature_engineering.py

Inputs (expected in data/ directory):
    - kochi_lst.tif       (Landsat surface temperature in °C)
    - kochi_ndvi.tif      (Sentinel-2 NDVI)
    - kochi_ndbi.tif      (Sentinel-2 NDBI)
    - kochi_buildings.geojson  (OSM building footprints)
    - kochi_roads.geojson      (OSM road network)

Output:
    - data/kochi_grid_features.csv
    - data/kochi_grid.geojson  (grid polygons for later visualization)
"""

import os
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import box, Polygon
from rasterstats import zonal_stats
import warnings
warnings.filterwarnings("ignore")

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
NORTH, SOUTH = 10.1, 9.9
EAST, WEST = 76.4, 76.2
GRID_SIZE_M = 500  # 500m x 500m grid cells

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# Input file paths
LST_TIF = os.path.join(DATA_DIR, "kochi_lst.tif")
NDVI_TIF = os.path.join(DATA_DIR, "kochi_ndvi.tif")
NDBI_TIF = os.path.join(DATA_DIR, "kochi_ndbi.tif")
BUILDINGS_GEOJSON = os.path.join(DATA_DIR, "kochi_buildings.geojson")
ROADS_GEOJSON = os.path.join(DATA_DIR, "kochi_roads.geojson")


def create_grid(west, south, east, north, cell_size_m):
    """
    Create a uniform grid of square polygons over the bounding box.
    
    Since we're working in EPSG:4326 (degrees), we approximate the cell size
    by converting meters to degrees at Kochi's latitude (~10°N).
    At 10°N: 1° lat ≈ 111,320 m, 1° lon ≈ 109,640 m
    
    Args:
        cell_size_m: Grid cell size in meters
    
    Returns:
        GeoDataFrame with grid cell polygons in EPSG:4326
    """
    print(f"Creating {cell_size_m}m x {cell_size_m}m grid...")
    
    # Convert cell size from meters to approximate degrees at Kochi's latitude
    lat_deg_per_m = 1.0 / 111320.0
    lon_deg_per_m = 1.0 / (111320.0 * np.cos(np.radians((north + south) / 2)))
    
    cell_lat = cell_size_m * lat_deg_per_m  # cell height in degrees
    cell_lon = cell_size_m * lon_deg_per_m  # cell width in degrees
    
    cells = []
    cell_ids = []
    centroids_lon = []
    centroids_lat = []
    
    cell_id = 0
    lat = south
    while lat < north:
        lon = west
        while lon < east:
            # Create a rectangular polygon for each grid cell
            cell = box(lon, lat, lon + cell_lon, lat + cell_lat)
            cells.append(cell)
            cell_ids.append(cell_id)
            centroids_lon.append(lon + cell_lon / 2)
            centroids_lat.append(lat + cell_lat / 2)
            cell_id += 1
            lon += cell_lon
        lat += cell_lat
    
    grid = gpd.GeoDataFrame({
        "cell_id": cell_ids,
        "lon": centroids_lon,
        "lat": centroids_lat,
    }, geometry=cells, crs="EPSG:4326")
    
    print(f"  Created {len(grid)} grid cells")
    print(f"  Cell size: ~{cell_lon:.5f}° lon x {cell_lat:.5f}° lat")
    return grid


def extract_raster_features(grid, tif_path, band_name):
    """
    Extract zonal statistics (mean, std, min, max) from a raster for each grid cell.
    
    Uses rasterstats to compute statistics of raster pixel values that fall
    within each grid cell polygon. This is how we go from continuous raster
    data to per-cell tabular features for the ML model.
    
    Args:
        grid: GeoDataFrame of grid cell polygons
        tif_path: Path to the GeoTIFF raster
        band_name: Name prefix for the output columns (e.g., 'lst', 'ndvi')
    
    Returns:
        DataFrame with columns: {band_name}_mean, {band_name}_std, etc.
    """
    print(f"  Extracting {band_name} from {os.path.basename(tif_path)}...")
    
    # zonal_stats computes raster statistics for each polygon in the GeoDataFrame.
    # It handles the spatial intersection of polygons with raster pixels internally.
    stats = zonal_stats(
        grid.geometry,
        tif_path,
        stats=["mean", "std", "min", "max", "count"],
        nodata=np.nan
    )
    
    # Convert list of dicts to DataFrame
    stats_df = pd.DataFrame(stats)
    stats_df.columns = [f"{band_name}_{col}" for col in stats_df.columns]
    
    valid = stats_df[f"{band_name}_mean"].notna().sum()
    print(f"    Valid cells: {valid}/{len(grid)} ({100*valid/len(grid):.1f}%)")
    
    return stats_df


def extract_building_features(grid, buildings_path):
    """
    Extract building density features for each grid cell.
    
    For each cell, we compute:
    - building_count: Number of buildings whose centroid falls in the cell
    - building_density: Total building footprint area / cell area
    - avg_building_area: Average building size in the cell
    
    These are key predictors of urban heat — denser built-up areas trap more heat.
    """
    print("  Extracting building features...")
    
    buildings = gpd.read_file(buildings_path)
    
    # Project both to UTM zone 43N (EPSG:32643) for accurate area calculations
    grid_utm = grid.to_crs(epsg=32643)
    buildings_utm = buildings.to_crs(epsg=32643)
    
    # Compute building centroids for spatial join
    buildings_utm["centroid"] = buildings_utm.geometry.centroid
    buildings_centroids = buildings_utm.set_geometry("centroid")
    
    # Compute cell area in m² (should be ~250,000 m² for 500m cells)
    cell_area = grid_utm.geometry.iloc[0].area
    
    # Spatial join: for each building centroid, find which grid cell it falls in
    joined = gpd.sjoin(buildings_centroids, grid_utm[["cell_id", "geometry"]], 
                       how="inner", predicate="within")
    
    # Aggregate per cell
    building_stats = joined.groupby("cell_id").agg(
        building_count=("geometry", "size"),
        total_building_area=("area_m2", "sum"),
        avg_building_area=("area_m2", "mean")
    ).reset_index()
    
    # Compute building density = total building area / cell area
    building_stats["building_density"] = building_stats["total_building_area"] / cell_area
    
    # Merge back with grid (cells with no buildings get NaN → fill with 0)
    result = grid[["cell_id"]].merge(building_stats, on="cell_id", how="left")
    result = result.fillna(0)
    
    print(f"    Cells with buildings: {(result['building_count'] > 0).sum()}/{len(grid)}")
    
    return result[["building_count", "building_density", "avg_building_area"]]


def extract_road_features(grid, roads_path):
    """
    Extract road density for each grid cell.
    
    road_density = total road length within cell / cell area
    
    Higher road density indicates more impervious surface, which contributes
    to the urban heat island effect by absorbing and re-radiating solar energy.
    """
    print("  Extracting road features...")
    
    roads = gpd.read_file(roads_path)
    
    # Project to UTM for accurate length calculations
    grid_utm = grid.to_crs(epsg=32643)
    roads_utm = roads.to_crs(epsg=32643)
    
    cell_area = grid_utm.geometry.iloc[0].area
    
    road_lengths = []
    
    # For each grid cell, clip roads to the cell and sum their lengths.
    # This is more accurate than spatial join for linear features.
    for idx, cell in grid_utm.iterrows():
        try:
            clipped = gpd.clip(roads_utm, cell.geometry)
            total_length = clipped.geometry.length.sum()
            road_lengths.append(total_length)
        except Exception:
            road_lengths.append(0)
    
    result = pd.DataFrame({
        "road_length_m": road_lengths,
        "road_density": [l / cell_area for l in road_lengths]
    })
    
    print(f"    Cells with roads: {(result['road_density'] > 0).sum()}/{len(grid)}")
    
    return result


def compute_derived_features(df):
    """
    Compute derived features from the raw extracted values.
    
    These derived features capture higher-level spatial relationships
    that are more meaningful for UHI analysis than raw band values alone.
    """
    print("  Computing derived features...")
    
    # Albedo proxy: rough approximation using NDBI
    # Built-up surfaces (high NDBI) tend to have lower albedo (absorb more heat)
    # This is a simplification — true albedo requires multi-band calculation
    df["albedo_proxy"] = 1 - df["ndbi_mean"].clip(-1, 1)
    
    # Green fraction: proportion of the cell that is "vegetated"
    # NDVI > 0.3 is a common threshold for moderate-to-dense vegetation
    # Since we have the mean NDVI, we use it as a continuous proxy
    df["green_fraction"] = df["ndvi_mean"].clip(0, 1)
    
    # Impervious fraction: combination of building density and road density
    # Normalized to 0-1 range for model interpretability
    max_bd = df["building_density"].quantile(0.99)  # avoid outlier skew
    max_rd = df["road_density"].quantile(0.99)
    if max_bd > 0:
        df["norm_building_density"] = (df["building_density"] / max_bd).clip(0, 1)
    else:
        df["norm_building_density"] = 0
    if max_rd > 0:
        df["norm_road_density"] = (df["road_density"] / max_rd).clip(0, 1)
    else:
        df["norm_road_density"] = 0
    
    df["impervious_fraction"] = (
        0.6 * df["norm_building_density"] + 0.4 * df["norm_road_density"]
    ).clip(0, 1)
    
    # Distance to nearest green space (cell with high vegetation)
    # "Green space" = cell with NDVI mean > 0.4
    green_mask = df["ndvi_mean"] > 0.4
    if green_mask.sum() > 0:
        green_lons = df.loc[green_mask, "lon"].values
        green_lats = df.loc[green_mask, "lat"].values
        
        distances = []
        for _, row in df.iterrows():
            # Approximate distance in meters using Euclidean on degree coords
            # (acceptable at city scale near equator)
            d_lon = (row["lon"] - green_lons) * 111320 * np.cos(np.radians(row["lat"]))
            d_lat = (row["lat"] - green_lats) * 111320
            min_dist = np.sqrt(d_lon**2 + d_lat**2).min()
            distances.append(min_dist)
        
        df["dist_to_green_m"] = distances
    else:
        print("    Warning: No cells with NDVI > 0.4 found. Setting dist_to_green to 0.")
        df["dist_to_green_m"] = 0
    
    return df


def main():
    print("=" * 60)
    print("PHASE 3: Feature Engineering for Kochi UHI Analysis")
    print("=" * 60)
    
    # ── Validate inputs exist ──
    required_files = [LST_TIF, NDVI_TIF, NDBI_TIF, BUILDINGS_GEOJSON, ROADS_GEOJSON]
    missing = [f for f in required_files if not os.path.exists(f)]
    if missing:
        print("\nERROR: Missing input files:")
        for f in missing:
            print(f"  - {f}")
        print("\nMake sure you've:")
        print("  1. Downloaded .tif files from Google Drive into data/")
        print("  2. Run pull_osm_data.py to generate the GeoJSON files")
        return
    
    print("All input files found. Starting feature extraction...\n")
    
    # ── Step 1: Create the spatial grid ──
    grid = create_grid(WEST, SOUTH, EAST, NORTH, GRID_SIZE_M)
    
    # ── Step 2: Extract raster features ──
    print("\nExtracting raster features:")
    lst_features = extract_raster_features(grid, LST_TIF, "lst")
    ndvi_features = extract_raster_features(grid, NDVI_TIF, "ndvi")
    ndbi_features = extract_raster_features(grid, NDBI_TIF, "ndbi")
    
    # ── Step 3: Extract vector features ──
    print("\nExtracting vector features:")
    building_features = extract_building_features(grid, BUILDINGS_GEOJSON)
    
    print("\n  Road feature extraction (this may take a few minutes for ~400 cells)...")
    road_features = extract_road_features(grid, ROADS_GEOJSON)
    
    # ── Step 4: Combine all features ──
    print("\nCombining features...")
    df = grid[["cell_id", "lon", "lat"]].copy()
    df = pd.concat([df, lst_features, ndvi_features, ndbi_features, 
                     building_features, road_features], axis=1)
    
    # ── Step 5: Compute derived features ──
    df = compute_derived_features(df)
    
    # ── Step 6: Drop cells with no LST data (outside raster coverage) ──
    before = len(df)
    df = df.dropna(subset=["lst_mean"])
    after = len(df)
    if before != after:
        print(f"\n  Dropped {before - after} cells with no LST data (outside raster coverage)")
    
    # ── Step 7: Save outputs ──
    csv_path = os.path.join(DATA_DIR, "kochi_grid_features.csv")
    df.to_csv(csv_path, index=False)
    print(f"\nSaved features CSV: {csv_path}")
    
    # Also save the grid as GeoJSON for visualization later
    grid_out = grid.copy()
    grid_out = grid_out[grid_out["cell_id"].isin(df["cell_id"])]
    grid_geojson_path = os.path.join(DATA_DIR, "kochi_grid.geojson")
    grid_out.to_file(grid_geojson_path, driver="GeoJSON")
    print(f"Saved grid GeoJSON: {grid_geojson_path}")
    
    # ── Summary ──
    print("\n" + "=" * 60)
    print("FEATURE ENGINEERING SUMMARY")
    print("=" * 60)
    print(f"Grid cells (total):     {len(grid)}")
    print(f"Grid cells (with data): {len(df)}")
    print(f"Grid cell size:         {GRID_SIZE_M}m x {GRID_SIZE_M}m")
    print(f"Features per cell:      {len(df.columns) - 1}")  # minus cell_id
    print(f"\nFeature columns:")
    for col in df.columns:
        if col != "cell_id":
            non_null = df[col].notna().sum()
            print(f"  {col:30s} | non-null: {non_null:4d} | "
                  f"mean: {df[col].mean():8.3f} | std: {df[col].std():8.3f}")
    
    print(f"\nLST range: {df['lst_mean'].min():.1f}°C to {df['lst_mean'].max():.1f}°C")
    print(f"NDVI range: {df['ndvi_mean'].min():.3f} to {df['ndvi_mean'].max():.3f}")
    print(f"NDBI range: {df['ndbi_mean'].min():.3f} to {df['ndbi_mean'].max():.3f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
