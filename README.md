# 🔴 ShadeNet // Planetary Thermal Observational System

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-red.svg)](https://www.python.org/downloads/)
[![XGBoost Monotonic](https://img.shields.io/badge/ML-XGBoost%20Monotonic-black.svg)](https://xgboost.readthedocs.io/)
[![Explainability SHAP](https://img.shields.io/badge/XAI-TreeExplainer%20SHAP-E4262E.svg)](https://github.com/slundberg/shap)
[![UI Google Stitch](https://img.shields.io/badge/UI%2FUX-Google%20Stitch-white.svg)](https://stitch.withgoogle.com/)
[![License MIT](https://img.shields.io/badge/license-MIT-gray.svg)](LICENSE)

An explainable artificial intelligence (XAI) and geospatial decision-support system that detects **Urban Heat Islands (UHI)**, decomposes microclimate drivers via **SHAP (SHapley Additive exPlanations)**, and simulates **physics-constrained counterfactual greening interventions** across major Indian metropolitan clusters.

> Replicated and connected from **Google Stitch Project `13233314015976264991`** with a high-performance Flask REST API backend.

---

## 📌 Executive Summary

Rapid urbanization and impervious surface expansion have amplified Land Surface Temperatures (LST) across Indian metros, creating dangerous microclimatic heat pockets. Municipalities and urban planners lack interpretable tools that provide actionable, cell-by-cell causality:

1. **Where are the critical heat anomalies?**
2. **Why is a specific block 8.9°C hotter than the city baseline?**
3. **What is the exact, verifiable cooling impact if we increase urban tree canopy by +10%, +20%, or +30%?**

**ShadeNet** answers these questions by fusing **Landsat 9 Thermal Infrared Sensor (TIRS)** radiance, **Sentinel-2 MSI** spectral indices, and **OpenStreetMap (OSM)** urban morphological vectors into a unified **500m × 500m spatial grid**, powered by **monotonic gradient-boosted decision trees**.

---

## 🛰️ Multi-City Regional Target Matrix

ShadeNet features a precomputed multi-metro observation network calibrated across distinct ecological sectors:

| City | Sector | Native Grid Cells | Hotspot Threshold | Mean LST | Peak Hotspot |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Kochi** (കൊച്ചി) | South-West Coastal Estuary | **1,980 cells** | $\ge 40.15^\circ\text{C}$ | $34.2^\circ\text{C}$ | **$43.1^\circ\text{C}$** |
| **Chennai** (சென்னை) | Coromandel East Littoral | **1,485 cells** | $\ge 44.20^\circ\text{C}$ | $36.8^\circ\text{C}$ | **$49.0^\circ\text{C}$** |
| **Mumbai** (मुंबई) | West Peninsular Estuary | **1,400 cells** | $\ge 42.00^\circ\text{C}$ | $36.9^\circ\text{C}$ | **$42.8^\circ\text{C}$** |
| **Bangalore** (ಬೆಂಗಳೂರು) | Deccan Plateau Inland | **1,440 cells** | $\ge 42.95^\circ\text{C}$ | $34.2^\circ\text{C}$ | **$43.5^\circ\text{C}$** |
| **Delhi** (दिल्ली) | Northern Gangetic Metroplex | **1,720 cells** | $\ge 44.40^\circ\text{C}$ | $41.5^\circ\text{C}$ | **$48.2^\circ\text{C}$** |

---

## 🧠 Machine Learning & Physics-Constrained Causal AI

### 1. Thermodynamic Monotonicity Constraints
Standard unconstrained regression models often suffer from spatial multicollinearity (e.g. correlated vegetation, albedo proxies, and water boundary effects), causing physically impossible predictions where adding vegetation is predicted to warm certain cells.

ShadeNet solves this with strict **XGBoost monotonicity constraints**:
$$\text{monotone\_constraints} = (-1, +1, +1, +1, +1)$$

* **Vegetation Index (`ndvi_mean`)**: Strictly negative gradient ($\le 0$) $\implies$ vegetation **strictly cools**.
* **Built-up Index (`ndbi_mean`)**: Strictly positive gradient ($\ge 0$) $\implies$ impervious surfaces **strictly warm**.
* **Road Density (`road_density`)**: Strictly positive gradient ($\ge 0$) $\implies$ asphalt absorption **strictly warms**.
* **Building Density (`building_density`)**: Strictly positive gradient ($\ge 0$) $\implies$ building mass **strictly warms**.
* **Distance to Green Space (`dist_to_green_m`)**: Strictly positive gradient ($\ge 0$) $\implies$ distance from park **strictly warms**.

**Physical Validation**: **0.00% physical violations** across all 1,980 cells in the operational matrix.

### 2. SHAP Explainability Hierarchy
Using `shap.TreeExplainer`, ShadeNet decomposes each individual block's temperature deviation into additive degrees Celsius ($^\circ\text{C}$):

| Feature | Physical Driver | Mean \|SHAP\| Impact | Direction |
| :--- | :--- | :---: | :---: |
| **`ndbi_mean`** | Built-up Index (Impervious fraction) | **1.651 °C** | Warming ($+\Delta T$) |
| **`road_density`** | Asphalt Network Surface Absorption | **1.031 °C** | Warming ($+\Delta T$) |
| **`building_density`** | Structural Concrete Thermal Mass | **0.391 °C** | Warming ($+\Delta T$) |
| **`ndvi_mean`** | Vegetative Evapotranspiration Canopy | **0.107 °C** | Cooling ($-\Delta T$) |
| **`dist_to_green_m`** | Park Proximity Microclimate Buffer | **0.026 °C** | Cooling Proximity |

---

## 🎨 Google Stitch Design System Implementation

The frontend strictly implements the design specifications from **Google Stitch Project `13233314015976264991`**:

* **4-Color Strict Terminal Palette**:
  * Near-Black: `#0A0A0A` (Surface Base)
  * Dark Slate: `#161616` / `#1c1b1e` (Panels and Elevated Drawers)
  * Vivid Red: `#E4262E` (Thermal Heat Anomaly / Active Accents)
  * Off-White: `#E8E8E8` (Primary Typography)
* **Typography**:
  * Headlines & Subtitles: `Montserrat`
  * Telemetry, Readings, & Code: `JetBrains Mono`
  * Hero Numbers: `Orbitron` & `Bebas Neue`
* **5 Interactive Screen Views**:
  1. **Global Landing Observatory**: Radial breathing aura, HUD telemetry micro-matrix, and direct metro quicklinks.
  2. **Regional City Selection**: Featured Kochi hero card with glowing border and regional metro cards with local language scripts.
  3. **City Hero Drill-Down**: Animated $8.9^\circ\text{C}$ intra-urban disparity stat with corner registration reticles and 4 diagnostic cards (*Cool Sink*, *Critical Peak*, *Surface Albedo*, *Population at Risk*).
  4. **Map Dashboard**: Clean **Esri Dark Gray Canvas basemap** (zero watermarks) displaying black-to-vivid-red thermal infrared choropleths, layer matrix switcher, and peak anomaly tracker.
  5. **Slide-in Cell Diagnosis Drawer**: Locks a pulsing target reticle onto the map cell, renders solid red warming SHAP bars / white outline cooling SHAP bars, and provides an interactive greening slider with live struck-through temperature readouts ($43.1^\circ\text{C} \to 41.3^\circ\text{C}$).
  6. **Model & SHAP Architecture Modal**: Centered technical inspection modal displaying monotonic constraints and the 5-feature beeswarm attribution plot.

---

## ⚡ REST API Documentation

The Flask backend runs on port `3001` and serves static frontend assets alongside clean JSON endpoints:

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/api/cities` | `GET` | Returns list of available metropolitan targets. |
| `/api/grid?city=<name>` | `GET` | Full GeoJSON FeatureCollection with cell properties, SHAP attributions, and scenarios. |
| `/api/grid/<cell_id>?city=<name>` | `GET` | Detailed microclimate diagnostics for an individual grid cell. |
| `/api/hotspots?city=<name>` | `GET` | Filtered FeatureCollection containing only critical heat island anomalies. |
| `/api/coldspots?city=<name>` | `GET` | Filtered FeatureCollection containing ecological urban cool sinks. |
| `/model/<filename>` | `GET` | Static access to model metrics, SHAP JSON values, and beeswarm summary plots. |

---

## 🚀 Quickstart & Running Locally

### 1. Prerequisites
* Python 3.9+
* Git

### 2. Clone the Repository
```bash
git clone https://github.com/antojeromc17-blip/ML-MODEL-URBAN-HEAT-MITIGATION-.git
cd ML-MODEL-URBAN-HEAT-MITIGATION-
```

### 3. Install Dependencies
```bash
pip install flask flask-cors xgboost scikit-learn pandas numpy geopandas shap
```

### 4. Launch the Server
```bash
python server/app.py
```

### 5. Open in Browser
Navigate to:
```
http://localhost:3001
```

---

## 📂 Repository Layout

```
ML-MODEL-URBAN-HEAT-MITIGATION-/
├── client/                      # Google Stitch Frontend Implementation
│   ├── index.html               # 5-screen connected terminal interface
│   ├── style.css                # Stitch design system (4-color palette, animations)
│   └── app.js                   # Application state, Leaflet integration, SHAP rendering
├── server/                      # High-performance Flask REST API
│   ├── app.py                   # Multi-city endpoints & static server
│   └── index.js                 # Optional Node server wrapper
├── model/                       # Serialized XGBoost Models & SHAP Artifacts
│   ├── model.pkl                # Trained monotonic model (Kochi baseline)
│   ├── metrics.json             # MAE, RMSE, R² scores
│   ├── shap_values.json         # Per-cell SHAP explanations
│   ├── shap_summary.png         # 5-feature beeswarm plot
│   └── [city]/                  # Sub-models for Chennai, Delhi, Bangalore, Mumbai
├── data/                        # Processed Geospatial Data & Output Layers
│   ├── grid_output.geojson      # Master 1,980-cell Kochi GeoJSON
│   ├── kochi_grid_features.csv  # Extracted feature matrix
│   ├── kochi_grid.geojson       # 500m polygon boundaries
│   └── [city]/                  # Multi-city grid outputs and feature CSVs
├── stitch_design/               # Extracted Google Stitch Project Assets & Spec
│   ├── ShadeNet_Design_Spec.md  # Official design tokens & component contracts
│   └── *.html / *.png           # Screen blueprints and reference screenshots
├── train_model.py               # Monotonic XGBoost Training Pipeline
├── scenarios.py                 # Counterfactual Simulation Engine (+10%, +20%, +30%)
├── optimize_city_heatmaps.py    # Multi-metro threshold calibration
└── README.md                    # Project documentation
```

---

## 👥 Hackathon Team & Acknowledgements

* **Dataset Sources**: Landsat 9 TIRS (USGS / NASA), Sentinel-2 MSI (Copernicus / ESA), OpenStreetMap contributors.
* **Interface Design**: Built with Google Stitch Project `13233314015976264991`.
