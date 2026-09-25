"""
Kochi UHI Backend API (Flask)
=============================
Serves precomputed grid_output.geojson via REST endpoints + static frontend.
No database -- loads JSON into memory on startup.
"""

import json
import math
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
CLIENT_DIR = BASE_DIR.parent / "client"
MODEL_DIR = BASE_DIR.parent / "model"

app = Flask(__name__, static_folder=str(CLIENT_DIR), static_url_path="")
CORS(app)

# ---------------------------------------------------------------------------
# Load data on startup
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Load data on startup (Multi-city: Kochi & Chennai)
# ---------------------------------------------------------------------------
KOCHI_PATH = DATA_DIR / "grid_output.geojson"
CHENNAI_PATH = DATA_DIR / "chennai" / "grid_output.geojson"

cities_data = {}
cell_indices = {}

if KOCHI_PATH.exists():
    print(f"Loading Kochi data from {KOCHI_PATH}...")
    with open(KOCHI_PATH, "r") as f:
        cities_data["kochi"] = json.load(f)
        cell_indices["kochi"] = {f["properties"]["cell_id"]: f for f in cities_data["kochi"].get("features", [])}

if CHENNAI_PATH.exists():
    print(f"Loading Chennai data from {CHENNAI_PATH}...")
    with open(CHENNAI_PATH, "r") as f:
        cities_data["chennai"] = json.load(f)
        cell_indices["chennai"] = {f["properties"]["cell_id"]: f for f in cities_data["chennai"].get("features", [])}

# Default references
grid_data = cities_data.get("kochi") or list(cities_data.values())[0]
metadata = grid_data.get("metadata", {})
features = grid_data.get("features", [])
cell_index = cell_indices.get("kochi", {})

print(f"Loaded cities: {list(cities_data.keys())}")


# ---------------------------------------------------------------------------
# Serve frontend & static model artifacts
# ---------------------------------------------------------------------------
@app.route("/")
def serve_frontend():
    return send_from_directory(str(CLIENT_DIR), "index.html")


@app.route("/model/<path:filename>")
def serve_model_file(filename):
    return send_from_directory(str(MODEL_DIR), filename)


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------
@app.route("/api/cities")
def get_cities():
    """List available cities"""
    return jsonify({
        "cities": [
            {"id": cid, "name": cdata.get("metadata", {}).get("city", cid.title())}
            for cid, cdata in cities_data.items()
        ]
    })


@app.route("/api/grid")
def get_grid():
    """Full GeoJSON FeatureCollection for requested city"""
    city = request.args.get("city", "kochi").lower()
    cdata = cities_data.get(city) or cities_data.get("kochi")
    return jsonify(cdata)


@app.route("/api/grid/<int:cell_id>")
def get_cell(cell_id):
    """Single cell's feature data"""
    cell = cell_index.get(cell_id)
    if not cell:
        return jsonify({"error": f"Cell {cell_id} not found"}), 404
    return jsonify(cell)


@app.route("/api/hotspots")
def get_hotspots():
    """Only cells where is_hotspot = true"""
    hotspots = [f for f in features if f["properties"].get("is_hotspot")]
    return jsonify({
        "type": "FeatureCollection",
        "metadata": {
            "count": len(hotspots),
            "threshold_lst": metadata.get("hotspot_threshold"),
        },
        "features": hotspots,
    })


@app.route("/api/coldspots")
def get_coldspots():
    """Only cells where is_coldspot = true"""
    coldspots = [f for f in features if f["properties"].get("is_coldspot")]
    return jsonify({
        "type": "FeatureCollection",
        "metadata": {"count": len(coldspots)},
        "features": coldspots,
    })


@app.route("/api/stats")
def get_stats():
    """Summary statistics for the dashboard for the requested city"""
    city = request.args.get("city", "kochi").lower()
    cdata = cities_data.get(city) or cities_data.get("kochi")
    c_meta = cdata.get("metadata", {})
    c_features = cdata.get("features", [])
    lsts = [f["properties"]["lst"] for f in c_features if f["properties"].get("lst") is not None]
    return jsonify({
        "city": c_meta.get("city", city.title()),
        "total_cells": len(c_features),
        "hotspot_count": c_meta.get("hotspot_count", 0),
        "coldspot_count": c_meta.get("coldspot_count", 0),
        "lst_mean": c_meta.get("lst_mean"),
        "lst_std": c_meta.get("lst_std"),
        "lst_min": min(lsts) if lsts else None,
        "lst_max": max(lsts) if lsts else None,
        "hotspot_threshold": c_meta.get("hotspot_threshold"),
        "zone_distribution": c_meta.get("zone_distribution"),
        "scenario_summary": c_meta.get("scenario_summary"),
        "global_shap_importance": c_meta.get("global_shap_importance"),
        "model_metrics": c_meta.get("model_metrics"),
        "feature_names": c_meta.get("feature_names"),
    })


@app.route("/api/scenario/<int:cell_id>")
def get_scenario(cell_id):
    """Cooling scenario for a specific cell"""
    ndvi_increase = request.args.get("ndvi_increase", "10", type=int)
    cell = cell_index.get(cell_id)

    if not cell:
        return jsonify({"error": f"Cell {cell_id} not found"}), 404

    scenario_key = f"ndvi_plus_{ndvi_increase}"
    scenarios = cell["properties"].get("scenarios", {})

    if scenario_key not in scenarios:
        return jsonify({
            "error": f"Scenario '{scenario_key}' not available",
            "available": list(scenarios.keys()),
        }), 400

    original_lst = cell["properties"]["lst"]
    cooling = scenarios[scenario_key]

    return jsonify({
        "cell_id": cell_id,
        "scenario": scenario_key,
        "ndvi_increase_pct": ndvi_increase,
        "original_lst": original_lst,
        "cooling_delta": cooling,
        "projected_lst": round(original_lst - cooling, 2),
        "all_scenarios": scenarios,
    })


@app.route("/api/zones")
def get_zones():
    """Cells grouped by zone type"""
    zone_type = request.args.get("type")

    filtered = features
    if zone_type:
        filtered = [f for f in features if f["properties"].get("zone_type") == zone_type]

    return jsonify({
        "type": "FeatureCollection",
        "metadata": {
            "count": len(filtered),
            "zone_distribution": metadata.get("zone_distribution"),
        },
        "features": filtered,
    })


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "cells_loaded": len(features),
    })


# ---------------------------------------------------------------------------
# Start server
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"\nKochi UHI API server running at http://localhost:3001")
    print(f"\nEndpoints:")
    print(f"  GET /                      - Frontend UI")
    print(f"  GET /api/grid              - Full GeoJSON")
    print(f"  GET /api/grid/<cellId>     - Single cell data")
    print(f"  GET /api/hotspots          - Hotspot cells only")
    print(f"  GET /api/coldspots         - Coldspot cells only")
    print(f"  GET /api/stats             - Dashboard summary stats")
    print(f"  GET /api/scenario/<cellId> - Cooling scenario for a cell")
    print(f"  GET /api/zones?type=...    - Cells by zone type")
    print(f"  GET /api/health            - Health check")

    app.run(host="0.0.0.0", port=3001, debug=False)
