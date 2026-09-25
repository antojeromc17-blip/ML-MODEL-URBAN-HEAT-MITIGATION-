/**
 * Kochi UHI Backend API
 * =====================
 * Serves precomputed grid_output.geojson via REST endpoints.
 * No database — loads JSON into memory on startup.
 */

const express = require("express");
const cors = require("cors");
const fs = require("fs");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 3001;

// Enable CORS for frontend dev server
app.use(cors());
app.use(express.json());

// ---------------------------------------------------------------------------
// Load data on startup
// ---------------------------------------------------------------------------
const DATA_PATH = path.join(__dirname, "..", "data", "grid_output.geojson");

let gridData = null;
let cellIndex = {};  // cell_id -> feature
let metadata = {};

function loadData() {
  console.log(`Loading data from ${DATA_PATH}...`);
  const raw = fs.readFileSync(DATA_PATH, "utf-8");
  gridData = JSON.parse(raw);
  metadata = gridData.metadata || {};

  // Build cell index for O(1) lookups
  cellIndex = {};
  for (const feature of gridData.features) {
    cellIndex[feature.properties.cell_id] = feature;
  }

  console.log(`Loaded ${gridData.features.length} grid cells`);
  console.log(`Hotspots: ${metadata.hotspot_count}, Coldspots: ${metadata.coldspot_count}`);
}

try {
  loadData();
} catch (err) {
  console.error("Failed to load grid data:", err.message);
  console.error("Make sure grid_output.geojson exists in the data/ directory.");
  process.exit(1);
}

// ---------------------------------------------------------------------------
// API Routes
// ---------------------------------------------------------------------------

/**
 * GET /api/grid
 * Returns the full GeoJSON FeatureCollection
 */
app.get("/api/grid", (req, res) => {
  res.json(gridData);
});

/**
 * GET /api/grid/:cellId
 * Returns a single cell's feature data
 */
app.get("/api/grid/:cellId", (req, res) => {
  const cellId = parseInt(req.params.cellId, 10);
  const cell = cellIndex[cellId];

  if (!cell) {
    return res.status(404).json({ error: `Cell ${cellId} not found` });
  }

  res.json(cell);
});

/**
 * GET /api/hotspots
 * Returns only cells where is_hotspot = true
 */
app.get("/api/hotspots", (req, res) => {
  const hotspots = gridData.features.filter(
    (f) => f.properties.is_hotspot === true
  );

  res.json({
    type: "FeatureCollection",
    metadata: {
      count: hotspots.length,
      threshold_lst: metadata.hotspot_threshold,
      clusters: metadata.zone_distribution?.hotspot || 0,
    },
    features: hotspots,
  });
});

/**
 * GET /api/coldspots
 * Returns only cells where is_coldspot = true
 */
app.get("/api/coldspots", (req, res) => {
  const coldspots = gridData.features.filter(
    (f) => f.properties.is_coldspot === true
  );

  res.json({
    type: "FeatureCollection",
    metadata: { count: coldspots.length },
    features: coldspots,
  });
});

/**
 * GET /api/stats
 * Returns summary statistics for the dashboard
 */
app.get("/api/stats", (req, res) => {
  const features = gridData.features;
  const lsts = features.map((f) => f.properties.lst);

  res.json({
    total_cells: features.length,
    hotspot_count: metadata.hotspot_count,
    coldspot_count: metadata.coldspot_count,
    lst_mean: metadata.lst_mean,
    lst_std: metadata.lst_std,
    lst_min: Math.min(...lsts),
    lst_max: Math.max(...lsts),
    hotspot_threshold: metadata.hotspot_threshold,
    zone_distribution: metadata.zone_distribution,
    scenario_summary: metadata.scenario_summary,
    global_shap_importance: metadata.global_shap_importance,
    model_metrics: metadata.model_metrics,
    feature_names: metadata.feature_names,
  });
});

/**
 * GET /api/scenario/:cellId?ndvi_increase=20
 * Returns the precomputed cooling delta for a specific cell and scenario
 */
app.get("/api/scenario/:cellId", (req, res) => {
  const cellId = parseInt(req.params.cellId, 10);
  const ndviIncrease = parseInt(req.query.ndvi_increase || "10", 10);
  const cell = cellIndex[cellId];

  if (!cell) {
    return res.status(404).json({ error: `Cell ${cellId} not found` });
  }

  const scenarioKey = `ndvi_plus_${ndviIncrease}`;
  const scenarios = cell.properties.scenarios || {};

  if (!(scenarioKey in scenarios)) {
    return res.status(400).json({
      error: `Scenario '${scenarioKey}' not available`,
      available: Object.keys(scenarios),
    });
  }

  res.json({
    cell_id: cellId,
    scenario: scenarioKey,
    ndvi_increase_pct: ndviIncrease,
    original_lst: cell.properties.lst,
    cooling_delta: scenarios[scenarioKey],
    projected_lst: Math.round((cell.properties.lst - scenarios[scenarioKey]) * 100) / 100,
    all_scenarios: scenarios,
  });
});

/**
 * GET /api/zones
 * Returns cells grouped by zone type
 */
app.get("/api/zones", (req, res) => {
  const zoneType = req.query.type; // optional filter

  let features = gridData.features;
  if (zoneType) {
    features = features.filter((f) => f.properties.zone_type === zoneType);
  }

  res.json({
    type: "FeatureCollection",
    metadata: {
      count: features.length,
      zone_distribution: metadata.zone_distribution,
    },
    features,
  });
});

// ---------------------------------------------------------------------------
// Health check
// ---------------------------------------------------------------------------
app.get("/api/health", (req, res) => {
  res.json({
    status: "ok",
    cells_loaded: gridData.features.length,
    uptime: process.uptime(),
  });
});

// ---------------------------------------------------------------------------
// Start server
// ---------------------------------------------------------------------------
app.listen(PORT, () => {
  console.log(`\nKochi UHI API server running at http://localhost:${PORT}`);
  console.log(`\nEndpoints:`);
  console.log(`  GET /api/grid              - Full GeoJSON`);
  console.log(`  GET /api/grid/:cellId      - Single cell data`);
  console.log(`  GET /api/hotspots          - Hotspot cells only`);
  console.log(`  GET /api/coldspots         - Coldspot cells only`);
  console.log(`  GET /api/stats             - Dashboard summary stats`);
  console.log(`  GET /api/scenario/:cellId  - Cooling scenario for a cell`);
  console.log(`  GET /api/zones?type=...    - Cells by zone type`);
  console.log(`  GET /api/health            - Health check`);
});
