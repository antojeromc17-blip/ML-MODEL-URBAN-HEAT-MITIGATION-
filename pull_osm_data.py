"""
Phase 2: Pull OpenStreetMap building footprints and road network for Kochi.

This script downloads building polygons and road geometries from OSM
using the osmnx library, then saves them as GeoJSON files for feature
engineering in Phase 3.

Usage:
    pip install osmnx geopandas
    python pull_osm_data.py

Or paste into a Google Colab cell after:
    !pip install osmnx geopandas
"""

import osmnx as ox
import geopandas as gpd
import os
import time

# ──────────────────────────────────────────────
# Configuration: Same bounding box as Phase 1
# ──────────────────────────────────────────────
NORTH, SOUTH = 10.1, 9.9
EAST, WEST = 76.4, 76.2

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def pull_buildings():
    """
    Pull building footprints from OpenStreetMap within the Kochi bounding box.
    
    Returns a GeoDataFrame where each row is a building polygon with attributes
    like building type, name, height (if tagged), etc.
    """
    print("Pulling building footprints from OSM...")
    print(f"  Bounding box: N={NORTH}, S={SOUTH}, E={EAST}, W={WEST}")
    start = time.time()

    # osmnx.features_from_bbox fetches any OSM feature matching the given tags.
    # tags={'building': True} means "any feature with a 'building' key, regardless of value"
    # This includes residential, commercial, industrial, etc.
    buildings = ox.features_from_bbox(
        bbox=(WEST, SOUTH, EAST, NORTH),
        tags={"building": True}
    )

    elapsed = time.time() - start
    print(f"  Downloaded {len(buildings)} building features in {elapsed:.1f}s")

    # The result can contain Points, Polygons, and MultiPolygons.
    # We only want polygon geometries (actual footprints), not POI points.
    buildings = buildings[buildings.geometry.type.isin(["Polygon", "MultiPolygon"])]
    print(f"  After filtering to polygons: {len(buildings)} buildings")

    # Keep only useful columns to reduce file size.
    # Many OSM columns are sparse/irrelevant. We keep geometry + a few tags.
    keep_cols = ["geometry"]
    for col in ["building", "name", "building:levels", "height", "amenity"]:
        if col in buildings.columns:
            keep_cols.append(col)

    buildings = buildings[keep_cols].reset_index(drop=True)

    # Compute area in square meters for each building footprint.
    # We project to UTM zone 43N (EPSG:32643) which covers Kochi for accurate area calculation.
    buildings_projected = buildings.to_crs(epsg=32643)
    buildings["area_m2"] = buildings_projected.geometry.area

    return buildings


def pull_roads():
    """
    Pull the road/street network from OpenStreetMap for the Kochi bounding box.
    
    Returns a GeoDataFrame of road edges (LineStrings) with attributes like
    road type, name, number of lanes, etc.
    """
    print("\nPulling road network from OSM...")
    print(f"  Bounding box: N={NORTH}, S={SOUTH}, E={EAST}, W={WEST}")
    start = time.time()

    # osmnx.graph_from_bbox downloads the drivable road network as a NetworkX graph.
    # network_type='drive' gets roads that cars can use (excludes footpaths, cycle paths).
    # This gives us the most relevant "impervious surface" proxy for UHI analysis.
    graph = ox.graph_from_bbox(
        bbox=(WEST, SOUTH, EAST, NORTH),
        network_type="drive"
    )

    elapsed = time.time() - start
    print(f"  Downloaded road graph in {elapsed:.1f}s")

    # Convert the graph edges to a GeoDataFrame for easy spatial analysis.
    # Each row is a road segment (LineString) with attributes.
    edges = ox.graph_to_gdfs(graph, nodes=False, edges=True)
    print(f"  Total road segments: {len(edges)}")

    # Keep only useful columns
    keep_cols = ["geometry"]
    for col in ["highway", "name", "lanes", "maxspeed", "length"]:
        if col in edges.columns:
            keep_cols.append(col)

    edges = edges[keep_cols].reset_index(drop=True)

    # Compute road length in meters using UTM projection
    edges_projected = edges.to_crs(epsg=32643)
    edges["length_m"] = edges_projected.geometry.length

    return edges


def main():
    print("=" * 50)
    print("PHASE 2: OpenStreetMap Data Pull for Kochi")
    print("=" * 50)

    # ── Pull Buildings ──
    buildings = pull_buildings()
    buildings_path = os.path.join(OUTPUT_DIR, "kochi_buildings.geojson")
    buildings.to_file(buildings_path, driver="GeoJSON")
    print(f"  Saved to: {buildings_path}")

    # ── Pull Roads ──
    roads = pull_roads()
    roads_path = os.path.join(OUTPUT_DIR, "kochi_roads.geojson")
    roads.to_file(roads_path, driver="GeoJSON")
    print(f"  Saved to: {roads_path}")

    # ── Summary ──
    total_building_area_km2 = buildings["area_m2"].sum() / 1e6
    total_road_length_km = roads["length_m"].sum() / 1000

    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Buildings:          {len(buildings)} polygons")
    print(f"Total building area: {total_building_area_km2:.2f} km²")
    print(f"Road segments:      {len(roads)} edges")
    print(f"Total road length:  {total_road_length_km:.1f} km")
    print(f"Output directory:   {OUTPUT_DIR}")
    print(f"Files created:")
    print(f"  - kochi_buildings.geojson ({os.path.getsize(buildings_path) / 1024:.0f} KB)")
    print(f"  - kochi_roads.geojson ({os.path.getsize(roads_path) / 1024:.0f} KB)")
    print("=" * 50)


if __name__ == "__main__":
    main()
