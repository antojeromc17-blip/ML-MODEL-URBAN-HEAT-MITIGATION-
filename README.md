# 🏙️ Urban Heat Mitigation Engine — Kochi

An end-to-end Machine Learning and Geospatial decision-support system to detect **Urban Heat Islands (UHI)**, explain microclimate drivers with **SHAP**, and simulate **counterfactual urban greening interventions**.

Developed for Kochi (Ernakulam), Kerala, India.

---

## 📌 Problem Overview
Rapid urbanization and impervious surface expansion have amplified Land Surface Temperatures (LST) across Kochi. Urban planning authorities require spatial, explainable insights rather than black-box models to prioritize green infrastructure interventions (e.g., green corridors, rooftop gardens, urban tree canopies).

---

## 🛰️ Data Pipeline & Architecture

```
Landsat 8 Thermal (Band 10 LST)  ──┐
Sentinel-2 Multispectral (NDVI/NDBI) ─┼──> 500m × 500m Grid ──> XGBoost (Monotonic) ──> SHAP Explainability ──> Interactive Web UI
OpenStreetMap (Buildings & Roads) ─┘        (1,980 cells)
```

1. **Satellite Remote Sensing (Google Earth Engine)**:
   - **Landsat 8 Thermal Infrared Sensor (TIRS)**: Surface temperature in Celsius ($30\text{m}$ resolution, cloud cover $< 1\%$).
   - **Sentinel-2 MSI**: Cloud-masked composites for **NDVI** (Normalized Difference Vegetation Index) and **NDBI** (Normalized Difference Built-up Index).
2. **OpenStreetMap Vector Ingestion (`osmnx`)**:
   - Building footprints and road network density mapped across Kochi's $20\text{km} \times 20\text{km}$ bounding box `[76.2, 9.9, 76.4, 10.1]`.
3. **Zonal Feature Extraction**:
   - Uniform $500\text{m} \times 500\text{m}$ grid generating **1,980 analysis cells**.
   - Extracted 5 non-collinear physical features:
     * `ndbi_mean`: Built-up index
     * `road_density`: Road network length per unit area
     * `building_density`: Building footprint area per unit area
     * `ndvi_mean`: Vegetation canopy index
     * `dist_to_green_m`: Distance to nearest major green space

---

## 🧠 Machine Learning & SHAP Interpretability

### Physics-Informed Monotonic Constraints
To prevent spatial multicollinearity artifacts (where greening counter-intuitively shows warming in coastal boundary cells), the model enforces strict **thermodynamic monotonicity**:
$$\text{monotone\_constraints} = (-1, +1, +1, +1, +1)$$
* **Vegetation (NDVI)** strictly decreases temperature.
* **Built-up surfaces, roads, and building density** strictly increase temperature.

### Benchmark Validation
* **Random 5-Fold Cross-Validation $R^2$**: `0.6031`
* **Spatial Block Group-CV $R^2$ (Unseen Geographic Quadrants)**: `0.4846`
* **Test MAE**: `1.2854 °C`
* **Test RMSE**: `2.5511 °C`

### SHAP Feature Importance Hierarchy
| Feature | Physical Driver | Mean \|SHAP\| Contribution |
| :--- | :--- | :---: |
| **`ndbi_mean`** | Built-up Index | **1.6508 °C** |
| **`road_density`** | Asphalt Network Absorption | **1.0306 °C** |
| **`building_density`** | Thermal Mass | **0.3914 °C** |
| **`ndvi_mean`** | Vegetative Cooling | **0.1069 °C** |
| **`dist_to_green_m`** | Park Proximity Effect | **0.0256 °C** |

---

## 🌳 What-If Cooling Interventions

Counterfactual simulations precompute temperature reductions across all cells:
* **+10% Vegetation**: Citywide avg cooling = **0.47 °C** | Hotspot avg = **0.89 °C**
* **+20% Vegetation**: Citywide avg cooling = **0.94 °C** | Hotspot avg = **1.66 °C** *(Max: 4.64 °C)*
* **+30% Vegetation**: Citywide avg cooling = **1.31 °C** | Hotspot avg = **2.54 °C**

---

## 🚀 Quickstart & Running Locally

### 1. Requirements
* Python 3.9+
* Node.js (optional, Flask serves the frontend directly)

### 2. Install Dependencies
```bash
pip install flask flask-cors xgboost scikit-learn pandas numpy geopandas shap
```

### 3. Run the Application
```bash
python server/app.py
```
Open **`http://localhost:3001`** (or `http://localhost:5000`) in your browser.

---

## 📁 Repository Structure
```
├── client/                      # Interactive Leaflet + Chart.js Dashboard
│   ├── index.html
│   ├── app.js
│   └── style.css
├── server/                      # Lightweight REST API & Static Asset Server
│   ├── app.py
│   └── index.js
├── model/                       # Serialized Models & SHAP Artifacts
│   ├── model.pkl
│   ├── metrics.json
│   ├── shap_values.json
│   ├── shap_summary.png
│   └── shap_bar.png
├── data/                        # Geospatial Layers & Processed Grid
│   ├── grid_output.geojson      # Precomputed master geojson (2.5MB)
│   ├── kochi_grid_features.csv
│   └── kochi_grid.geojson
├── train_model.py               # XGBoost Model Training with Monotonicity
├── scenarios.py                 # Counterfactual Simulation Engine
├── feature_engineering.py       # Grid & Zonal Extraction
└── pull_osm_data.py             # OSM Vector Ingestion
```

---

## 👥 Authors
* Developed for Hackathon 2026.
