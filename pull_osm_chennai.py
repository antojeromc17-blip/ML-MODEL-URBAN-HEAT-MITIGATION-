"""
Pull OpenStreetMap building footprints and road network for Chennai
Saves to data/chennai/chennai_buildings.geojson and data/chennai/chennai_roads.geojson
"""
import os
import time
import osmnx as ox
import geopandas as gpd

NORTH, SOUTH = 13.15, 12.95
EAST, WEST = 80.35, 80.15

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "chennai")
os.makedirs(OUT_DIR, exist_ok=True)

BUILDINGS_OUT = os.path.join(OUT_DIR, "chennai_buildings.geojson")
ROADS_OUT = os.path.join(OUT_DIR, "chennai_roads.geojson")

def pull_buildings():
    print(f"Pulling building footprints for Chennai from OSM...")
    print(f"  Bounding box: N={NORTH}, S={SOUTH}, E={EAST}, W={WEST}")
    start = time.time()
    
    buildings = ox.features_from_bbox(
        bbox=(WEST, SOUTH, EAST, NORTH),
        tags={"building": True}
    )
    
    # Filter to valid polygons only
    buildings = buildings[buildings.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()
    buildings = buildings.reset_index()
    
    keep_cols = [c for c in ["osmid", "geometry", "building", "name"] if c in buildings.columns]
    buildings = buildings[keep_cols]
    
    buildings.to_file(BUILDINGS_OUT, driver="GeoJSON")
    print(f"  Saved {len(buildings)} buildings to {BUILDINGS_OUT} ({time.time() - start:.1f}s)")

def pull_roads():
    print(f"Pulling road network for Chennai from OSM...")
    start = time.time()
    
    G = ox.graph_from_bbox(
        bbox=(WEST, SOUTH, EAST, NORTH),
        network_type="drive"
    )
    
    roads = ox.graph_to_gdfs(G, nodes=False)
    roads = roads.reset_index()
    
    keep_cols = [c for c in ["osmid", "geometry", "highway", "name", "length"] if c in roads.columns]
    roads = roads[keep_cols]
    
    roads.to_file(ROADS_OUT, driver="GeoJSON")
    print(f"  Saved {len(roads)} road segments to {ROADS_OUT} ({time.time() - start:.1f}s)")

if __name__ == "__main__":
    pull_buildings()
    pull_roads()
    print("All OSM data for Chennai extracted successfully!")
