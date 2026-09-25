"""
Phase 4: ML Model Training + SHAP Explainability
=================================================
Trains XGBRegressor to predict LST from urban features,
then uses SHAP TreeExplainer to attribute per-cell temperature drivers.

Inputs:
  - data/kochi_grid_features.csv  (from Phase 3)

Outputs:
  - model/model.pkl          — serialized XGBRegressor
  - model/shap_values.json   — per-cell SHAP breakdown (top drivers)
  - model/metrics.json       — R², RMSE, MAE, feature importances
  - model/shap_summary.png   — SHAP beeswarm summary plot
"""

import os
import json
import warnings
import numpy as np
import pandas as pd
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "model"
MODEL_DIR.mkdir(exist_ok=True)

FEATURES_CSV = DATA_DIR / "kochi_grid_features.csv"

# Target variable
TARGET = "lst_mean"

# Feature columns used for prediction (clean, non-collinear set)
FEATURE_COLS = [
    "ndvi_mean",
    "ndbi_mean",
    "building_density",
    "road_density",
    "dist_to_green_m",
]

# Human-readable names for display
FEATURE_NAMES = {
    "ndvi_mean": "Vegetation Index (NDVI)",
    "ndbi_mean": "Built-up Index (NDBI)",
    "building_density": "Building Density",
    "road_density": "Road Density",
    "dist_to_green_m": "Distance to Green Space (m)",
}


def main():
    print("=" * 60)
    print("PHASE 4: ML Model Training + SHAP Explainability")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Load data
    # ------------------------------------------------------------------
    print("\n1. Loading features...")
    df = pd.read_csv(FEATURES_CSV)
    print(f"   Loaded {len(df)} grid cells with {len(df.columns)} columns")

    # Drop rows with NaN in target or features
    valid_mask = df[TARGET].notna() & df[FEATURE_COLS].notna().all(axis=1)
    df_valid = df[valid_mask].copy()
    dropped = len(df) - len(df_valid)
    if dropped > 0:
        print(f"   Dropped {dropped} rows with missing values")
    print(f"   Using {len(df_valid)} cells for modeling")

    X = df_valid[FEATURE_COLS].values
    y = df_valid[TARGET].values

    print(f"\n   Target ({TARGET}) stats:")
    print(f"     Mean: {y.mean():.2f} C, Std: {y.std():.2f} C")
    print(f"     Range: {y.min():.2f} C - {y.max():.2f} C")

    # ------------------------------------------------------------------
    # 2. Train/test split
    # ------------------------------------------------------------------
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    print(f"\n2. Train/test split: {len(X_train)} train / {len(X_test)} test")

    # ------------------------------------------------------------------
    # 3. Train XGBRegressor with grid search and physical monotone constraints
    # ------------------------------------------------------------------
    print("\n3. Training XGBRegressor with physics constraints...")
    from xgboost import XGBRegressor
    from sklearn.model_selection import GridSearchCV
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

    param_grid = {
        "n_estimators": [200, 300, 400],
        "max_depth": [5, 6, 7],
        "learning_rate": [0.03, 0.05, 0.1],
        "subsample": [0.8],
        "colsample_bytree": [0.8],
        "min_child_weight": [3, 5],
    }

    # Monotonic constraints:
    # ndvi_mean: -1 (more vegetation strictly cools / decreases LST)
    # ndbi_mean: +1 (more built-up strictly warms / increases LST)
    # building_density: +1 (more buildings strictly increase LST)
    # road_density: +1 (more roads strictly increase LST)
    # dist_to_green_m: +1 (further from green strictly increases LST)
    base_model = XGBRegressor(
        random_state=42,
        n_jobs=-1,
        objective="reg:squarederror",
        monotone_constraints=(-1, 1, 1, 1, 1),
    )

    grid_search = GridSearchCV(
        base_model,
        param_grid,
        cv=5,
        scoring="r2",
        n_jobs=-1,
        verbose=0,
        refit=True,
    )

    grid_search.fit(X_train, y_train)
    model = grid_search.best_estimator_

    print(f"   Best params: {grid_search.best_params_}")
    print(f"   Best CV R²:  {grid_search.best_score_:.4f}")

    # ------------------------------------------------------------------
    # 4. Evaluate
    # ------------------------------------------------------------------
    print("\n4. Model evaluation:")

    y_pred_train = model.predict(X_train)
    y_pred_test = model.predict(X_test)

    r2_train = r2_score(y_train, y_pred_train)
    r2_test = r2_score(y_test, y_pred_test)
    rmse_train = np.sqrt(mean_squared_error(y_train, y_pred_train))
    rmse_test = np.sqrt(mean_squared_error(y_test, y_pred_test))
    mae_train = mean_absolute_error(y_train, y_pred_train)
    mae_test = mean_absolute_error(y_test, y_pred_test)

    print(f"   Train - R2: {r2_train:.4f} | RMSE: {rmse_train:.3f} C | MAE: {mae_train:.3f} C")
    print(f"   Test  - R2: {r2_test:.4f} | RMSE: {rmse_test:.3f} C | MAE: {mae_test:.3f} C")

    # Feature importances from XGBoost
    importances = model.feature_importances_
    importance_ranking = sorted(
        zip(FEATURE_COLS, importances.tolist()),
        key=lambda x: x[1], reverse=True
    )
    print("\n   Feature importance (XGBoost gain):")
    for feat, imp in importance_ranking:
        bar = "#" * int(imp * 50)
        print(f"     {FEATURE_NAMES.get(feat, feat):35s} {imp:.4f} {bar}")

    # ------------------------------------------------------------------
    # 5. SHAP Analysis
    # ------------------------------------------------------------------
    print("\n5. Computing SHAP values (this may take a minute)...")
    import shap

    # Use all valid data for SHAP (not just test set) — we need explanations for every cell
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)

    # Global mean absolute SHAP values
    mean_abs_shap = np.abs(shap_values).mean(axis=0)
    shap_ranking = sorted(
        zip(FEATURE_COLS, mean_abs_shap.tolist()),
        key=lambda x: x[1], reverse=True
    )

    print("\n   Global SHAP feature importance (mean |SHAP|):")
    for feat, shap_imp in shap_ranking:
        bar = "#" * int(shap_imp * 10)
        print(f"     {FEATURE_NAMES.get(feat, feat):35s} {shap_imp:.4f} C {bar}")

    # Expected value (base prediction)
    expected_value = float(explainer.expected_value)
    print(f"\n   Base prediction (expected value): {expected_value:.2f} C")

    # ------------------------------------------------------------------
    # 6. Build per-cell SHAP breakdown
    # ------------------------------------------------------------------
    print("\n6. Building per-cell SHAP breakdown...")

    shap_per_cell = []
    for i in range(len(df_valid)):
        cell_id = int(df_valid.iloc[i]["cell_id"])
        cell_shap = shap_values[i]

        # All SHAP values for this cell
        all_drivers = [
            {
                "name": feat,
                "display_name": FEATURE_NAMES.get(feat, feat),
                "shap": round(float(cell_shap[j]), 4),
                "value": round(float(X[i, j]), 4),
            }
            for j, feat in enumerate(FEATURE_COLS)
        ]

        # Sort by absolute SHAP value, get top 5
        all_drivers.sort(key=lambda d: abs(d["shap"]), reverse=True)
        top_drivers = all_drivers[:5]

        shap_per_cell.append({
            "cell_id": cell_id,
            "expected_value": round(expected_value, 4),
            "predicted_lst": round(float(expected_value + cell_shap.sum()), 4),
            "actual_lst": round(float(y[i]), 4),
            "top_drivers": top_drivers,
            "all_shap": {feat: round(float(cell_shap[j]), 4) for j, feat in enumerate(FEATURE_COLS)},
        })

    # ------------------------------------------------------------------
    # 7. Save SHAP summary plot
    # ------------------------------------------------------------------
    print("\n7. Saving SHAP summary plot...")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 8))
    shap.summary_plot(
        shap_values, X,
        feature_names=[FEATURE_NAMES.get(f, f) for f in FEATURE_COLS],
        show=False,
        plot_size=(10, 8),
    )
    plt.tight_layout()
    plt.savefig(str(MODEL_DIR / "shap_summary.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"   Saved: {MODEL_DIR / 'shap_summary.png'}")

    # Also save a bar plot
    fig, ax = plt.subplots(figsize=(10, 6))
    shap.summary_plot(
        shap_values, X,
        feature_names=[FEATURE_NAMES.get(f, f) for f in FEATURE_COLS],
        plot_type="bar",
        show=False,
        plot_size=(10, 6),
    )
    plt.tight_layout()
    plt.savefig(str(MODEL_DIR / "shap_bar.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"   Saved: {MODEL_DIR / 'shap_bar.png'}")

    # ------------------------------------------------------------------
    # 8. Save model and outputs
    # ------------------------------------------------------------------
    print("\n8. Saving model artifacts...")

    # Save model
    import joblib
    model_path = MODEL_DIR / "model.pkl"
    joblib.dump(model, str(model_path))
    print(f"   Saved model: {model_path}")

    # Save SHAP values JSON
    shap_output = {
        "expected_value": round(expected_value, 4),
        "feature_columns": FEATURE_COLS,
        "feature_names": FEATURE_NAMES,
        "global_importance": [
            {"name": feat, "display_name": FEATURE_NAMES.get(feat, feat), "mean_abs_shap": round(val, 4)}
            for feat, val in shap_ranking
        ],
        "cells": shap_per_cell,
    }
    shap_path = MODEL_DIR / "shap_values.json"
    with open(shap_path, "w") as f:
        json.dump(shap_output, f, indent=2)
    print(f"   Saved SHAP values: {shap_path}")

    # Save metrics JSON
    metrics = {
        "model_type": "XGBRegressor",
        "best_params": grid_search.best_params_,
        "cv_r2": round(grid_search.best_score_, 4),
        "train": {
            "r2": round(r2_train, 4),
            "rmse": round(rmse_train, 4),
            "mae": round(mae_train, 4),
            "n_samples": len(X_train),
        },
        "test": {
            "r2": round(r2_test, 4),
            "rmse": round(rmse_test, 4),
            "mae": round(mae_test, 4),
            "n_samples": len(X_test),
        },
        "feature_importance_xgb": [
            {"name": feat, "display_name": FEATURE_NAMES.get(feat, feat), "importance": round(imp, 4)}
            for feat, imp in importance_ranking
        ],
        "feature_importance_shap": [
            {"name": feat, "display_name": FEATURE_NAMES.get(feat, feat), "mean_abs_shap": round(val, 4)}
            for feat, val in shap_ranking
        ],
        "total_cells": len(df_valid),
        "target_variable": TARGET,
        "features_used": FEATURE_COLS,
    }
    metrics_path = MODEL_DIR / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"   Saved metrics: {metrics_path}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("PHASE 4 SUMMARY")
    print("=" * 60)
    print(f"Model:              XGBRegressor")
    print(f"Training cells:     {len(X_train)}")
    print(f"Test cells:         {len(X_test)}")
    print(f"Test R2:            {r2_test:.4f}")
    print(f"Test RMSE:          {rmse_test:.3f} C")
    print(f"Test MAE:           {mae_test:.3f} C")
    print(f"\nTop 3 global SHAP drivers:")
    for feat, val in shap_ranking[:3]:
        direction = "(+) heats" if val > 0 else "(-) cools"
        print(f"  {FEATURE_NAMES.get(feat, feat):35s} avg |SHAP| = {val:.3f} C")
    print(f"\nBase prediction: {expected_value:.2f} C")
    print(f"\nArtifacts saved to: {MODEL_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
