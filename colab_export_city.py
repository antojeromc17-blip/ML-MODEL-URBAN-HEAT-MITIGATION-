# ================================================================
# GOOGLE COLAB: Export Satellite + OSM Data for Any City
# ================================================================
# Copy each section (separated by # === CELL X ===) into a
# separate Colab cell, and run them in order.
#
# TOTAL TIME: ~30-45 min per city (mostly waiting for EE export)
# ================================================================


# === CELL 1: Install dependencies ===
# !pip install earthengine-api osmnx geopandas rasterio

# === CELL 2: Authenticate Earth Engine ===
# import ee
# ee.Authenticate()
# ee.Initialize(project='YOUR-GCP-PROJECT-ID')  # <-- CHANGE THIS


# === CELL 3: CHOOSE YOUR CITY ===
# Just change CITY_NAME and the 4 coordinates. Everything else is automatic.

CITY_NAME = "chennai"  # <-- CHANGE THIS

# Bounding box: [WEST, SOUTH, EAST, NORTH]
CITIES = {
    "chennai":   {"west": 80.15, "south": 12.95, "east": 80.35, "north": 13.15},
    "bangalore": {"west": 77.50, "south": 12.90, "east": 77.70, "north": 13.05},
    "mumbai":    {"west": 72.80, "south": 18.90, "east": 72.95, "north": 19.10},
    "delhi":     {"west": 77.10, "south": 28.50, "east": 77.30, "north": 28.70},
    "hyderabad": {"west": 78.35, "south": 17.35, "east": 78.55, "north": 17.50},
}

bbox = CITIES[CITY_NAME]
print(f"Selected city: {CITY_NAME}")
print(f"Bounding box: {bbox}")


# === CELL 4: Export LST from Landsat 8 ===
import ee

roi = ee.Geometry.Rectangle([bbox["west"], bbox["south"], bbox["east"], bbox["north"]])

# Landsat 8 Collection 2, Level 2 (surface temperature)
# Using hot season (March-May) for clear UHI signal
landsat = (ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
    .filterBounds(roi)
    .filterDate("2024-03-01", "2024-05-31")
    .filter(ee.Filter.lt("CLOUD_COVER", 20)))

print(f"Landsat images found: {landsat.size().getInfo()}")

# Convert thermal band to Celsius
def to_celsius(img):
    lst = (img.select("ST_B10")
        .multiply(0.00341802)
        .add(149.0)
        .subtract(273.15)
        .rename("LST"))
    return lst.copyProperties(img, ["system:time_start"])

lst = landsat.map(to_celsius).median().clip(roi)

# Export to Google Drive
task_lst = ee.batch.Export.image.toDrive(
    image=lst,
    description=f"{CITY_NAME}_lst",
    folder="uhi_data",
    scale=30,
    region=roi,
    maxPixels=1e13,
    fileFormat="GeoTIFF"
)
task_lst.start()
print(f"LST export started -> Google Drive/uhi_data/{CITY_NAME}_lst.tif")


# === CELL 5: Export NDVI + NDBI from Sentinel-2 ===

s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(roi)
    .filterDate("2024-03-01", "2024-05-31")
    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
    .median()
    .clip(roi))

# NDVI = (NIR - Red) / (NIR + Red)
ndvi = s2.normalizedDifference(["B8", "B4"]).rename("NDVI")

# NDBI = (SWIR - NIR) / (SWIR + NIR)
ndbi = s2.normalizedDifference(["B11", "B8"]).rename("NDBI")

# Export NDVI
task_ndvi = ee.batch.Export.image.toDrive(
    image=ndvi,
    description=f"{CITY_NAME}_ndvi",
    folder="uhi_data",
    scale=10,
    region=roi,
    maxPixels=1e13,
    fileFormat="GeoTIFF"
)
task_ndvi.start()
print(f"NDVI export started -> Google Drive/uhi_data/{CITY_NAME}_ndvi.tif")

# Export NDBI
task_ndbi = ee.batch.Export.image.toDrive(
    image=ndbi,
    description=f"{CITY_NAME}_ndbi",
    folder="uhi_data",
    scale=10,
    region=roi,
    maxPixels=1e13,
    fileFormat="GeoTIFF"
)
task_ndbi.start()
print(f"NDBI export started -> Google Drive/uhi_data/{CITY_NAME}_ndbi.tif")


# === CELL 6: Check export status (run this repeatedly until all COMPLETED) ===
import time

tasks = [task_lst, task_ndvi, task_ndbi]
names = ["LST", "NDVI", "NDBI"]

while True:
    all_done = True
    for name, task in zip(names, tasks):
        status = task.status()
        state = status["state"]
        print(f"  {name}: {state}")
        if state not in ["COMPLETED", "FAILED"]:
            all_done = False
    if all_done:
        print("\nAll exports finished!")
        break
    print("  Waiting 30 seconds...\n")
    time.sleep(30)


# === CELL 7: Download TIFs from Google Drive to Colab ===
from google.colab import drive
drive.mount("/content/drive")

import shutil
import os

os.makedirs(f"/content/{CITY_NAME}_data", exist_ok=True)

for name in ["lst", "ndvi", "ndbi"]:
    src = f"/content/drive/MyDrive/uhi_data/{CITY_NAME}_{name}.tif"
    dst = f"/content/{CITY_NAME}_data/{CITY_NAME}_{name}.tif"
    shutil.copy(src, dst)
    size_mb = os.path.getsize(dst) / (1024 * 1024)
    print(f"  Copied {name}: {size_mb:.1f} MB")

print(f"\nAll TIFs saved to /content/{CITY_NAME}_data/")


# === CELL 8: Pull OSM Buildings + Roads ===
import osmnx as ox
import geopandas as gpd

OUT_DIR = f"/content/{CITY_NAME}_data"

# Buildings
print(f"Pulling buildings for {CITY_NAME}...")
buildings = ox.features_from_bbox(
    bbox=(bbox["west"], bbox["south"], bbox["east"], bbox["north"]),
    tags={"building": True}
)
# Keep only polygon geometries
buildings = buildings[buildings.geometry.type.isin(["Polygon", "MultiPolygon"])]
buildings = buildings.reset_index()
# Keep only essential columns
keep_cols = [c for c in ["osmid", "geometry", "building", "name"] if c in buildings.columns]
buildings = buildings[keep_cols]
buildings.to_file(f"{OUT_DIR}/{CITY_NAME}_buildings.geojson", driver="GeoJSON")
print(f"  Saved {len(buildings)} buildings")

# Roads
print(f"Pulling roads for {CITY_NAME}...")
G = ox.graph_from_bbox(
    bbox=(bbox["west"], bbox["south"], bbox["east"], bbox["north"]),
    network_type="drive"
)
roads = ox.graph_to_gdfs(G, nodes=False)
roads = roads.reset_index()
keep_cols = [c for c in ["osmid", "geometry", "highway", "name", "length"] if c in roads.columns]
roads = roads[keep_cols]
roads.to_file(f"{OUT_DIR}/{CITY_NAME}_roads.geojson", driver="GeoJSON")
print(f"  Saved {len(roads)} road segments")


# === CELL 9: Download everything as a ZIP ===
import shutil

zip_name = f"/content/{CITY_NAME}_data"
shutil.make_archive(zip_name, "zip", zip_name)
print(f"\nZIP created: {zip_name}.zip")

# Auto-download to your computer
from google.colab import files
files.download(f"{zip_name}.zip")
print(f"\nDownloading {CITY_NAME}_data.zip to your computer...")
print("Unzip it and put all files into your hackathon/data/ folder.")
