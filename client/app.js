/**
 * Kochi Urban Heat Island (UHI) AI Observatory - Frontend Application
 */

// Application State
const state = {
  map: null,
  geoJsonLayer: null,
  geoData: null,
  selectedCell: null,
  viewMode: 'lst', // 'lst', 'scenario', 'delta', 'ndvi', 'ndbi'
  greeningPct: 0,   // 0, 10, 20, 30
  shapChart: null,
  globalShapChart: null,
  cellLayers: new Map(), // cell_id -> Leaflet polygon layer
};

// Heat Scale Palette - Dynamically tuned for Pan-India temperature range (20°C to 50°C)
const COLOR_RAMPS = {
  lst: [
    { t: 15, c: '#1e3a8a' }, // Deep Blue (Water/Wetland)
    { t: 24, c: '#3b82f6' }, // Cool Blue
    { t: 30, c: '#38bdf8' }, // Cyan
    { t: 34, c: '#fef08a' }, // Soft Yellow (Ambient Baseline)
    { t: 37, c: '#f59e0b' }, // Amber (Warm)
    { t: 40, c: '#f97316' }, // Orange (Very Warm)
    { t: 43, c: '#ef4444' }, // Red (Thermal Alert)
    { t: 46, c: '#b91c1c' }, // Crimson (Critical Hotspot)
    { t: 50, c: '#7f1d1d' }  // Deep Maroon (Extreme Urban Core)
  ],
  delta: [
    { t: 0.0, c: '#0f172a' }, // Neutral / Slate
    { t: 0.5, c: '#064e3b' }, // Dark Emerald
    { t: 1.5, c: '#059669' }, // Vibrant Green
    { t: 3.5, c: '#10b981' }, // Mint Green
    { t: 6.5, c: '#14b8a6' }, // Teal
    { t: 10.0, c: '#2dd4bf' }, // Bright Turquoise
    { t: 15.0, c: '#5eead4' }, // Vivid Cyan Glow
    { t: 18.0, c: '#a7f3d0' }  // Ultra High Cooling
  ],
  ndvi: [
    { t: -0.3, c: '#1e293b' },
    { t: 0.0, c: '#a16207' },
    { t: 0.2, c: '#ca8a04' },
    { t: 0.4, c: '#65a30d' },
    { t: 0.6, c: '#16a34a' },
    { t: 0.8, c: '#15803d' }
  ],
  ndbi: [
    { t: -0.4, c: '#0284c7' },
    { t: -0.1, c: '#38bdf8' },
    { t: 0.0, c: '#fde047' },
    { t: 0.1, c: '#ea580c' },
    { t: 0.25, c: '#dc2626' }
  ]
};

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
  initMap();
  initEventListeners();
  loadGridData();
});

// 1. Initialize Map
function initMap() {
  state.map = L.map('map', {
    center: [9.98, 76.28],
    zoom: 12,
    minZoom: 10,
    maxZoom: 16,
    zoomControl: false,
  });

  // Custom Zoom Control (bottom-right)
  L.control.zoom({ position: 'bottomright' }).addTo(state.map);

  // CartoDB Dark Matter Basemap
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; OpenStreetMap contributors',
    maxZoom: 19,
    subdomains: 'abcd',
  }).addTo(state.map);
}

// 2. Fetch and Load Grid Data
async function loadGridData(city = 'kochi') {
  try {
    state.currentCity = city;
    let response;
    try {
      response = await fetch(`/api/grid?city=${city}`);
      if (!response.ok) throw new Error('API fetch failed');
    } catch (e) {
      // Fallback
      const fallbackUrl = city === 'kochi' ? '../data/grid_output.geojson' : `../data/${city}/grid_output.geojson`;
      response = await fetch(fallbackUrl);
    }

    state.geoData = await response.json();
    const meta = state.geoData.metadata || {};
    
    // Update title
    const appTitle = document.getElementById('appTitle');
    if (appTitle) {
      appTitle.textContent = `${meta.city || city.toUpperCase()} UHI AI Observatory`;
    }

    populateStats(meta);
    renderGridLayer();
    initGlobalShapChart();

    // Auto-fit map to the selected city's bounds
    if (state.geoJsonLayer && state.geoJsonLayer.getBounds().isValid()) {
      state.map.fitBounds(state.geoJsonLayer.getBounds(), { padding: [20, 20] });
    }
  } catch (err) {
    console.error('Failed to load grid data:', err);
    alert(`Unable to load data for ${city}. Ensure server is running on http://localhost:3001`);
  }
}

// 3. Populate Header Statistics
function populateStats(meta) {
  if (!meta) return;
  document.getElementById('statAvgLst').textContent = `${meta.lst_mean?.toFixed(1) || '34.2'}°C`;
  document.getElementById('statHotspots').textContent = `${meta.hotspot_count !== undefined ? meta.hotspot_count : 0} cells`;
  
  // Real dynamic peak temperature from loaded city cells
  const feats = (state.geoData && state.geoData.features) || [];
  const lsts = feats.map(f => f.properties.lst).filter(v => v != null);
  const statMaxLstEl = document.getElementById('statMaxLst');
  if (statMaxLstEl && lsts.length > 0) {
    statMaxLstEl.textContent = `${Math.max(...lsts).toFixed(1)}°C`;
  }

  const scenarios = meta.scenario_summary || [];
  const s30 = scenarios.find(s => s.scenario === 'ndvi_plus_30');
  if (s30) {
    document.getElementById('statCooling').textContent = `${s30.max_cooling_c?.toFixed(2)}°C`;
    const hsEl = document.getElementById('hotspotAvgCooling');
    if (hsEl) hsEl.textContent = `${s30.hotspot_avg_cooling_c?.toFixed(2)}°C`;
    const cMaxEl = document.getElementById('cityMaxCooling');
    if (cMaxEl) cMaxEl.textContent = `${s30.max_cooling_c?.toFixed(2)}°C`;
  }
}

// 4. Color Interpolator
function getColor(val, rampName) {
  const ramp = COLOR_RAMPS[rampName] || COLOR_RAMPS.lst;
  if (val <= ramp[0].t) return ramp[0].c;
  if (val >= ramp[ramp.length - 1].t) return ramp[ramp.length - 1].c;

  for (let i = 0; i < ramp.length - 1; i++) {
    if (val >= ramp[i].t && val <= ramp[i + 1].t) {
      // Return exact color or gradient step
      const ratio = (val - ramp[i].t) / (ramp[i + 1].t - ramp[i].t);
      return interpolateHex(ramp[i].c, ramp[i + 1].c, ratio);
    }
  }
  return ramp[0].c;
}

function interpolateHex(c1, c2, ratio) {
  const r1 = parseInt(c1.slice(1, 3), 16);
  const g1 = parseInt(c1.slice(3, 5), 16);
  const b1 = parseInt(c1.slice(5, 7), 16);

  const r2 = parseInt(c2.slice(1, 3), 16);
  const g2 = parseInt(c2.slice(3, 5), 16);
  const b2 = parseInt(c2.slice(5, 7), 16);

  const r = Math.round(r1 + (r2 - r1) * ratio);
  const g = Math.round(g1 + (g2 - g1) * ratio);
  const b = Math.round(b1 + (b2 - b1) * ratio);

  return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
}

// 5. Compute Cell Color based on current mode
function getCellDisplayValue(props) {
  const baseLst = props.lst;
  if (state.viewMode === 'lst') return baseLst;

  if (state.viewMode === 'scenario') {
    if (state.greeningPct === 0) return baseLst;
    const delta = props.scenarios[`ndvi_plus_${state.greeningPct}`] || 0;
    return Math.max(20, baseLst - delta);
  }

  if (state.viewMode === 'delta') {
    if (state.greeningPct === 0) return 0;
    return props.scenarios[`ndvi_plus_${state.greeningPct}`] || 0;
  }

  if (state.viewMode === 'ndvi') return props.ndvi;
  if (state.viewMode === 'ndbi') return props.ndbi;

  return baseLst;
}

// 6. Style GeoJSON Features
function styleFeature(feature) {
  const props = feature.properties;
  const isSelected = state.selectedCell && state.selectedCell.properties.cell_id === props.cell_id;
  const isHotspot = props.is_hotspot;

  const displayVal = getCellDisplayValue(props);
  const rampName = state.viewMode === 'scenario' ? 'lst' : state.viewMode;
  const fillColor = getColor(displayVal, rampName);

  return {
    fillColor: fillColor,
    weight: isSelected ? 3 : (isHotspot ? 2 : 0.8),
    opacity: 0.8,
    color: isSelected ? '#38bdf8' : (isHotspot ? '#ef4444' : 'rgba(255, 255, 255, 0.15)'),
    dashArray: isHotspot && !isSelected ? '3' : null,
    fillOpacity: isSelected ? 0.85 : 0.65,
  };
}

// 7. Render Grid GeoJSON
function renderGridLayer() {
  if (state.geoJsonLayer) {
    state.map.removeLayer(state.geoJsonLayer);
  }
  state.cellLayers.clear();

  state.geoJsonLayer = L.geoJSON(state.geoData, {
    style: styleFeature,
    onEachFeature: (feature, layer) => {
      const props = feature.properties;
      state.cellLayers.set(props.cell_id, layer);

      // Tooltip
      layer.bindTooltip(`
        <div style="font-family: sans-serif; font-size: 11px;">
          <strong>Cell #${props.cell_id}</strong> ${props.is_hotspot ? '<span style="color:#ef4444;font-weight:bold;">[HOTSPOT]</span>' : ''}<br>
          LST: <b>${props.lst.toFixed(1)}°C</b> | NDVI: ${props.ndvi.toFixed(2)}<br>
          Zone: ${props.zone_type} ${props.hotspot_zone ? `(${props.hotspot_zone})` : ''}
        </div>
      `, { sticky: true, opacity: 0.95 });

      // Click handler
      layer.on('click', () => {
        selectCell(feature);
      });
    }
  }).addTo(state.map);

  updateLegend();
}

// 8. Update Styles on Slider / Mode Change
function refreshGridStyles() {
  if (!state.geoJsonLayer) return;
  state.geoJsonLayer.eachLayer(layer => {
    layer.setStyle(styleFeature(layer.feature));
  });
  updateLegend();
}

// 9. Update Map Legend
function updateLegend() {
  const rampEl = document.getElementById('legendRamp');
  const titleEl = document.getElementById('legendTitle');
  const minEl = document.getElementById('legendMin');
  const midEl = document.getElementById('legendMid');
  const maxEl = document.getElementById('legendMax');
  if (!rampEl || !titleEl || !minEl || !midEl || !maxEl) return;

  const meta = (state.geoData && state.geoData.metadata) || {};
  const feats = (state.geoData && state.geoData.features) || [];
  const lsts = feats.map(f => f.properties.lst).filter(v => v != null);
  const minLst = lsts.length ? Math.min(...lsts) : 20;
  const maxLst = lsts.length ? Math.max(...lsts) : 48;
  const avgLst = meta.lst_mean || ((minLst + maxLst) / 2);

  if (state.viewMode === 'lst' || state.viewMode === 'scenario') {
    titleEl.textContent = state.viewMode === 'scenario' ? `Simulated LST (+${state.greeningPct}% Green)` : 'Surface Temperature (°C)';
    rampEl.style.background = 'linear-gradient(to right, #1e3a8a, #3b82f6, #38bdf8, #fef08a, #f59e0b, #f97316, #ef4444, #b91c1c, #7f1d1d)';
    minEl.textContent = `${Math.round(minLst)}°C`;
    midEl.textContent = `${avgLst.toFixed(1)}°C`;
    maxEl.textContent = `${Math.round(maxLst)}°C`;
  } else if (state.viewMode === 'delta') {
    titleEl.textContent = `Cooling Potential (+${state.greeningPct}% Green)`;
    rampEl.style.background = 'linear-gradient(to right, #0f172a, #064e3b, #059669, #10b981, #14b8a6, #2dd4bf, #5eead4, #a7f3d0)';
    const scenarios = meta.scenario_summary || [];
    const sCurr = scenarios.find(s => s.scenario === `ndvi_plus_${state.greeningPct}`) || scenarios[scenarios.length - 1];
    const maxDelta = sCurr ? sCurr.max_cooling_c : 5.0;
    minEl.textContent = '0.0°C';
    midEl.textContent = `${(maxDelta / 2).toFixed(1)}°C`;
    maxEl.textContent = `${maxDelta.toFixed(1)}°C`;
  } else if (state.viewMode === 'ndvi') {
    titleEl.textContent = 'Vegetation Index (NDVI)';
    rampEl.style.background = 'linear-gradient(to right, #1e293b, #a16207, #ca8a04, #65a30d, #16a34a, #15803d)';
    minEl.textContent = '-0.3';
    midEl.textContent = '0.3';
    maxEl.textContent = '0.8';
  } else if (state.viewMode === 'ndbi') {
    titleEl.textContent = 'Built-up Index (NDBI)';
    rampEl.style.background = 'linear-gradient(to right, #0284c7, #38bdf8, #fde047, #ea580c, #dc2626)';
    minEl.textContent = '-0.4';
    midEl.textContent = '0.0';
    maxEl.textContent = '+0.25';
  }
}

// 10. Select and Inspect a Cell
function selectCell(feature) {
  state.selectedCell = feature;
  const props = feature.properties;

  // Refresh map borders
  state.geoJsonLayer.eachLayer(layer => {
    layer.setStyle(styleFeature(layer.feature));
  });

  // Open Drawer
  const drawer = document.getElementById('cellDrawer');
  drawer.classList.remove('closed');

  // Populate basic info
  document.getElementById('drawerCellTag').textContent = `Cell #${props.cell_id}`;
  
  const zoneBadge = document.getElementById('drawerZoneBadge');
  zoneBadge.textContent = props.zone_type.toUpperCase();
  zoneBadge.className = `zone-badge ${props.zone_type}`;

  document.getElementById('cellTemp').textContent = props.lst.toFixed(1);
  document.getElementById('cellZScore').textContent = `Z-score: ${props.lst_zscore > 0 ? '+' : ''}${props.lst_zscore.toFixed(2)}`;

  // Populate Scenario Cooling Cards
  const sc10 = props.scenarios?.ndvi_plus_10 || 0;
  const sc20 = props.scenarios?.ndvi_plus_20 || 0;
  const sc30 = props.scenarios?.ndvi_plus_30 || 0;
  document.getElementById('scenVal10').textContent = `-${sc10.toFixed(2)}°C`;
  document.getElementById('scenVal20').textContent = `-${sc20.toFixed(2)}°C`;
  document.getElementById('scenVal30').textContent = `-${sc30.toFixed(2)}°C`;

  // Urban Indicators
  document.getElementById('cellNdbi').textContent = props.ndbi.toFixed(3);
  document.getElementById('cellNdvi').textContent = props.ndvi.toFixed(3);
  document.getElementById('cellBldgDensity').textContent = `${(props.building_density * 100).toFixed(1)}%`;
  document.getElementById('cellRoadDensity').textContent = props.road_density.toFixed(4);
  document.getElementById('cellDistGreen').textContent = `${Math.round(props.dist_to_green_m)} m`;
  document.getElementById('cellCluster').textContent = props.hotspot_zone || 'None';

  // Render Local SHAP Breakdown Chart
  renderShapChart(props.top_drivers || []);
}

// 11. Render Local SHAP Bar Chart
function renderShapChart(drivers) {
  const ctx = document.getElementById('shapChart').getContext('2d');
  if (state.shapChart) {
    state.shapChart.destroy();
  }

  const labels = drivers.map(d => d.display_name.replace('Vegetation Index (NDVI)', 'NDVI (Veg)').replace('Built-up Index (NDBI)', 'NDBI (Built)'));
  const values = drivers.map(d => d.shap);
  const bgColors = values.map(v => v >= 0 ? 'rgba(239, 68, 68, 0.85)' : 'rgba(6, 182, 212, 0.85)');

  state.shapChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'SHAP Contribution (°C)',
        data: values,
        backgroundColor: bgColors,
        borderRadius: 4,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.raw >= 0 ? '+' : ''}${ctx.raw.toFixed(3)}°C temperature impact`
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.08)' },
          ticks: { color: '#94a3b8', font: { family: 'JetBrains Mono', size: 10 } }
        },
        y: {
          grid: { display: false },
          ticks: { color: '#f8fafc', font: { family: 'Inter', size: 11, weight: '500' } }
        }
      }
    }
  });
}

// 12. Render Global SHAP Chart (in Modal)
function initGlobalShapChart() {
  const ctx = document.getElementById('globalShapChart').getContext('2d');
  const globalShap = state.geoData.metadata?.global_shap_importance || [];

  const labels = globalShap.map(d => d.display_name);
  const values = globalShap.map(d => d.mean_abs_shap);

  state.globalShapChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Mean |SHAP| (°C)',
        data: values,
        backgroundColor: 'rgba(56, 189, 248, 0.85)',
        borderRadius: 4,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.08)' },
          ticks: { color: '#94a3b8', font: { family: 'JetBrains Mono', size: 10 } }
        },
        y: {
          grid: { display: false },
          ticks: { color: '#f8fafc', font: { family: 'Inter', size: 10 } }
        }
      }
    }
  });
}

// 13. Event Listeners
function initEventListeners() {
  // Mode Buttons
  document.querySelectorAll('.mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.viewMode = btn.dataset.mode;
      refreshGridStyles();
    });
  });

  // Scenario Slider
  const slider = document.getElementById('scenarioSlider');
  const badge = document.getElementById('sliderValueBadge');
  const ticks = document.querySelectorAll('.slider-ticks .tick');

  slider.addEventListener('input', (e) => {
    const val = parseInt(e.target.value);
    state.greeningPct = val;

    badge.textContent = val === 0 ? '+0% Baseline' : `+${val}% Greening`;
    ticks.forEach(t => {
      t.classList.toggle('active', parseInt(t.dataset.val) === val);
    });

    // Auto-switch to scenario mode if still in lst mode
    if (val > 0 && state.viewMode === 'lst') {
      document.querySelector('.mode-btn[data-mode="scenario"]').click();
    } else {
      refreshGridStyles();
    }
  });

  // Reset View
  document.getElementById('btnResetView').addEventListener('click', () => {
    state.map.setView([9.98, 76.28], 12);
  });

  // Close Drawer
  document.getElementById('btnCloseDrawer').addEventListener('click', () => {
    document.getElementById('cellDrawer').classList.add('closed');
    state.selectedCell = null;
    refreshGridStyles();
  });

  // Modal handlers
  const modal = document.getElementById('modelModal');
  document.getElementById('btnOpenModelInfo').addEventListener('click', () => {
    modal.classList.add('open');
  });
  document.getElementById('btnCloseModal').addEventListener('click', () => {
    modal.classList.remove('open');
  });
  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.classList.remove('open');
  });

  // Hotspot Quick Navigator (if present in DOM)
  const hotspotSelect = document.getElementById('hotspotSelect');
  if (hotspotSelect) {
    hotspotSelect.addEventListener('change', (e) => {
      const val = e.target.value;
      if (!val || !state.geoData) return;

      let targetFeature = null;
      if (val === 'hottest') {
        let maxL = -Infinity;
        state.geoData.features.forEach(f => {
          if (f.properties.lst > maxL) {
            maxL = f.properties.lst;
            targetFeature = f;
          }
        });
      } else {
        targetFeature = state.geoData.features.find(f => f.properties.hotspot_zone === val);
      }

      if (targetFeature) {
        const coords = targetFeature.geometry.coordinates[0];
        const bounds = L.latLngBounds(coords.map(c => [c[1], c[0]]));
        state.map.fitBounds(bounds, { maxZoom: 14, padding: [100, 100] });
        selectCell(targetFeature);
      }
    });
  }

  // City Selector
  const citySelect = document.getElementById('citySelect');
  if (citySelect) {
    citySelect.addEventListener('change', (e) => {
      const selectedCity = e.target.value;
      // Close drawer if open
      document.getElementById('cellDrawer').classList.add('closed');
      state.selectedCell = null;
      loadGridData(selectedCity);
    });
  }
}
