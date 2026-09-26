# ShadeNet — Final UI/UX Design Spec

Project: ShadeNet — AI-based Urban Heat Island Detection, multi-city (Hackathon PS1)
Purpose: single reference doc for design + frontend build (Phase 7)

**Product structure:** Global landing (ShadeNet brand) → City selection grid (Kochi, Bangalore, Mumbai, Chennai) → per-city 3-screen drill-down (Hero → Map Dashboard → Cell Diagnosis). Kochi is the fully-built demo city; the other three reuse the identical template with swapped city name, map imagery, and stat numbers.

---

## 1. Visual Identity

**Concept:** "Climate data terminal" — precise scientific instrumentation, not a consumer app. No decorative shapes, no stock illustration, no bubbly icons.

### Color Palette (revised — locked at 4 colors, no blue anywhere)

| Role | Color | Hex |
|---|---|---|
| Background (base) | Near-black | `#0A0A0A` |
| Panel background | Dark slate | `#161616` |
| Panel border | Low-opacity light | `rgba(255,255,255,0.08)` |
| Primary accent (UI chrome, buttons, CTA, "hot") | Vivid red | `#E4262E` |
| Heat scale — cool end | Near-black / dark slate | `#161616` |
| Heat scale — hot end | Vivid red | `#E4262E` |
| Text — primary | Off-white | `#E8E8E8` |
| Text — on filled red buttons | Off-white | `#E8E8E8` |
| "Pushes hotter" indicator (SHAP bars) | Vivid red (filled) | `#E4262E` |
| "Pulls cooler" indicator (SHAP bars) | Off-white (outline only, no fill) | `#E8E8E8` |

Only 4 colors total: black, dark slate, vivid red, off-white. The heat scale is now a monochrome-to-red ramp (black → red) instead of a diverging blue-to-red scale — cells glow red as they get hotter, staying dark/black when cool. This reads as a thermal-camera glow rather than a generic diverging heatmap, which fits the "climate terminal" concept even more tightly than the blue-red version did.

For the SHAP diagnosis panel, since there's no second hue to distinguish "hotter" vs "cooler" drivers, use **fill vs. outline** instead of color: red-filled bars = pushes temperature up, off-white outlined (unfilled) bars = pulls temperature down.

### Typography

| Use | Style | Font choice |
|---|---|---|
| Headlines / hero number | Bold geometric sans | **Poppins ExtraBold** or **Montserrat Black** |
| Body text / labels | Regular geometric sans | **Poppins Regular** |
| UI micro-labels (buttons, tags) | Medium, slightly letter-spaced | **Poppins Medium / SemiBold** |
| All numeric readouts (temps, %, counts) | Monospace — non-negotiable, this is the signature detail | **JetBrains Mono** or **IBM Plex Mono** |

Every stat, temperature, and percentage on screen uses the monospace font — this is what makes it read as "instrument panel" instead of "generic dashboard."

---

## 2. Screens (5-screen flow)

### Screen 1 — Global Landing / Hero
- Full-bleed near-black screen
- "ShadeNet" wordmark, massive, bold geometric sans, off-white, subtle red glow behind it
- Subtitle: "An AI model that detects urban heat islands, explains their causes, and simulates cooling interventions — city by city."
- Small dim monospace line: "satellite data · explainable ML · scenario simulation"
- Single glowing CTA: "Get Started →"

### Screen 2 — City Selection Grid
- Header: "● shadenet" wordmark top-left
- Heading: "Select a city to analyze"
- 2×2 grid of 4 cards: Kochi, Bangalore, Mumbai, Chennai
- Each card: desaturated near-monochrome (black/red only) satellite-style city image, vivid-red border glowing on hover, city name overlaid bottom in bold monospace off-white
- Clicking a card routes into that city's 3-screen flow (Screens 3–5, templated per city)

### Screen 3 — City Hero
- Header: "● shadenet" wordmark top-left, "← back to cities" link top-right
- One large monospace statistic center-stage (e.g. "11.4°C") with caption: "difference between the hottest and coolest block in Kochi"
- Small dim monospace line: "model v1 · 400 grid cells · live inference: off (precomputed)"
- Subtle heat-gradient glow pulsing behind the number
- Single glowing CTA: "Explore the Map →"

### Screen 4 — Main Map Dashboard
- Full-screen dark map (CartoDB Dark Matter style tiles), ~400-cell choropleth grid colored on the black-to-red heat scale
- Header bar: "● shadenet" wordmark far left + small city-name tag (e.g. "KOCHI"), then 3 stats, monospace, evenly spaced — Avg LST / Hotspot Count / Max Cooling Potential
- Bottom-left: vertical gradient legend (black→red) with °C labels
- Top-right: single "Auto Tour" icon button (scripted demo fallback)
- A few hotspot cells pulse gently

### Screen 5 — Cell Diagnosis Panel (slide-in from right, map dimmed/blurred behind)
- Glassmorphism panel, dark + blur backdrop
- Header: "Why is this block 6.2°C above average?"
- Horizontal SHAP bar chart, 5 drivers, sorted longest→shortest, fill-coded — solid vivid red (hotter) / off-white outline only (cooler), plain-language labels:
  - Built-up Density +2.3°C
  - Road Density +1.1°C
  - Building Density +0.6°C
  - Vegetation (NDVI) −0.8°C
  - Distance to Green Space −0.2°C
- Divider, then "Cooling Scenario" section: slider (0%→30% vegetation increase) with a **live-updating** old-vs-new temperature readout — old value struck through in off-white, new predicted value in vivid red if still a hotspot, or off-white if it's dropped out of hotspot range
- Close (X) top-right

---

## 3. Component Cut Priority (if time runs short)

Cut in this order — never cut the last item:
1. Before/After map-wide toggle
2. Animated pulse on hotspot markers
3. Glassmorphism blur (fallback: solid panel + border)
4. Hero load-in animation
5. **Never cut:** click → SHAP diagnosis panel → live scenario slider. This is the differentiator.

---

## 4. Final Stitch (Google) Prompt — ShadeNet, multi-city, 5-screen flow

Generate sequentially: Screen 1 → 2 → 3 → 4 → 5, one prompt block at a time. For screens 3–5, regenerate once per city (Kochi, Bangalore, Mumbai, Chennai) swapping only the city name/stats, keeping the "STRICT DESIGN SYSTEM" block identical each time to prevent palette drift.

```
Design a dark-mode web application called "ShadeNet" — an AI model that detects and
explains urban heat islands across Indian cities.

STRICT DESIGN SYSTEM — apply identically to every screen, do not substitute any default
Stitch styling, default color palette, or default font pairing:
- Colors, exactly four, nowhere else: near-black background #0A0A0A, dark slate panels
  #161616, vivid red accent #E4262E, off-white text #E8E8E8. No blue. No purple. No
  gradients except the black-to-red heat scale described below.
- Headings: bold geometric sans, Poppins ExtraBold or Montserrat Black weight.
- Body text: same sans family, Regular weight.
- Every number, stat, percentage, and coordinate on any screen: monospace font,
  JetBrains Mono or IBM Plex Mono — signature rule, zero exceptions.
- Small "ShadeNet" wordmark, all lowercase, monospace, preceded by a single vivid-red dot
  (●), present in the nav/header of every screen after the first.
- Aesthetic: "climate data terminal" — precise scientific instrumentation. No stock
  illustration, no rounded bubbly icons, no decorative shapes outside the heat scale.

Design these 5 screens as one connected flow:

SCREEN 1 — Global Landing / Hero
Full-bleed near-black screen. Center-stage: "ShadeNet" in massive bold geometric sans,
off-white, with a subtle vivid-red glow behind the wordmark. Subtitle below in off-white
regular weight: "An AI model that detects urban heat islands, explains their causes, and
simulates cooling interventions — city by city." Smaller dim-grey monospace line below:
"satellite data · explainable ML · scenario simulation". Single glowing vivid-red CTA,
centered: "Get Started →".

SCREEN 2 — City Selection Grid
Header: "● shadenet" wordmark top-left. Centered heading in off-white: "Select a city to
analyze". Below, a 2x2 grid of four large cards, evenly spaced with generous gutters. Each
card: a desaturated near-monochrome (black/red tones only) satellite-style image of the
city as background — Kochi shows coastline and backwaters, Bangalore shows a dense inland
grid, Mumbai shows a coastal peninsula, Chennai shows a coastal grid — with a vivid-red
border glowing brighter on hover. City name overlaid at the bottom of each card in bold
monospace off-white: "KOCHI", "BANGALORE", "MUMBAI", "CHENNAI".

SCREEN 3 — City Hero (Kochi as example)
Header: "● shadenet" wordmark top-left, "← back to cities" link top-right, both monospace
off-white. Center-stage: one large animated statistic in monospace vivid red — "11.4°C" —
caption below in off-white: "difference between the hottest and coolest block in Kochi."
Small dim monospace line beneath: "model v1 · 400 grid cells · live inference: off
(precomputed)". Subtle red glow pulsing behind the number. Single glowing vivid-red CTA:
"Explore the Map →".

SCREEN 4 — Main Map Dashboard (Kochi example)
Full-screen near-black map of the selected city, semi-transparent choropleth grid of square
cells on a black-to-red heat scale — dark cells near-invisible, hotter cells glow vivid red.
Header bar: "● shadenet" wordmark far left plus small city tag ("KOCHI"), then 3 stats in
monospace off-white, evenly spaced — "Avg LST: 32.1°C", "Hotspots: 47", "Max Cooling
Potential: −2.1°C" — each with a minimal line-icon. Bottom-left: vertical black-to-red
gradient legend bar with °C tick labels. Top-right: single icon button "Auto Tour". A few
hotspot cells pulse gently in red.

SCREEN 5 — Cell Diagnosis Panel (slide-in from right over Screen 4, map dimmed/blurred
behind)
Glassmorphism dark-slate panel, blurred backdrop, thin red glowing left border. Small dim
monospace label at top: "shadenet · kochi · cell #142". Bold off-white header below: "Why
is this block 6.2°C above average?" Horizontal bar chart, 5 drivers, sorted longest to
shortest — solid vivid-red filled bars for factors pushing temperature up, off-white
outline-only bars for factors pulling it down: "Built-up Density +2.3°C", "Road Density
+1.1°C", "Building Density +0.6°C", "Vegetation (NDVI) −0.8°C", "Distance to Green Space
−0.2°C". Thin divider, then "Cooling Scenario" section: slider labeled "Add Vegetation:
0% ————●———— 30%" with live-updating readout above — old temperature struck through in
off-white ("35.2°C"), new predicted temperature in vivid red ("33.7°C"). Close (X) top-right
in off-white.

Generate these as one cohesive product, not five unrelated pages — reuse the exact same
header treatment, wordmark placement, and heat-scale styling across screens 3, 4, and 5 so
it's visually obvious they belong to the same city-drill-down flow.
```

---

## 5. Build Notes

- No live API/GEE calls during rendering — everything reads from precomputed `grid_output.geojson`.
- Keep the "climate data terminal" phrase in any Stitch refinement prompts to prevent visual drift toward a generic template.
- Verify NDVI scenario direction (cooling) and updated `metrics.json` R²/RMSE before wiring the slider to real numbers.
