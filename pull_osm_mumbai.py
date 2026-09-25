"""
Pull OpenStreetMap building footprints and road network for Mumbai
Saves to data/mumbai/mumbai_buildings.geojson and data/mumbai/mumbai_roads.geojson
"""
import os
import time
import osmnx as ox
import geopandas as gpd

NORTH, SOUTH = 19.10, 18.90
EAST, WEST = 72.95, 72.80

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "mumbai")
os.makedirs(OUT_DIR, exist_ok=True)

BUILDINGS_OUT = os.path.join(OUT_DIR, "mumbai_buildings.geojson")
ROADS_OUT = os.path.join(OUT_DIR, "mumbai_roads.geojson")

def pull_buildings():
    print(f"Pulling building footprints for Mumbai from OSM...")
    print(f"  Bounding box: N={NORTH}, S={SOUTH}, E={EAST}, W={WEST}")
    start = time.time()
    
    buildings = ox.features_from_bbox(
        bbox=(WEST, SOUTH, EAST, NORTH),
        tags={"building": True}
    )
    
    buildings = buildings[buildings.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()
    buildings = buildings.reset_index()
    
    keep_cols = [c for c in ["osmid", "geometry", "building", "name"] if c in buildings.columns]
    buildings = buildings[keep_cols]
    
    buildings.to_file(BUILDINGS_OUT, driver="GeoJSON")
    print(f"  Saved {len(buildings)} buildings to {BUILDINGS_OUT} ({time.time() - start:.1f}s)")

def pull_roads():
    print(f"Pulling road network for Mumbai from OSM...")
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
    print("All OSM data for Mumbai extracted successfully!")
