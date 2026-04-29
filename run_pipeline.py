"""
run_pipeline.py
---------------
Standalone script to execute the full pricing optimisation pipeline end-to-end.

Usage (from the project root):
    python run_pipeline.py

What it does:
  1. Generate (or load) synthetic pricing data
  2. Preprocess and clean the dataset
  3. Compute price elasticity per product
  4. Build per-product demand models
  5. Run batch price optimisation
  6. Save results to results/sample_outputs.json
  7. Generate visualisation plots in results/
"""

import os
import sys
import logging

# ── Ensure project root is on the import path ─────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils         import setup_logging, save_json, plot_elasticity_summary, plot_revenue_comparison, plot_price_vs_demand, plot_price_vs_revenue
from src.data_loader   import generate_synthetic_data, load_data, save_data
from src.preprocessing import preprocess
from src.elasticity    import compute_all_elasticities
from src.revenue_model import build_demand_models
from src.optimizer     import optimize_price_for_product, run_batch_optimization

setup_logging()
logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
RAW_DATA_PATH       = os.path.join(PROJECT_ROOT, "data", "raw",       "pricing_data.csv")
PROCESSED_DATA_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "clean_data.csv")
RESULTS_DIR         = os.path.join(PROJECT_ROOT, "results")
OUTPUTS_JSON        = os.path.join(RESULTS_DIR,  "sample_outputs.json")


def main() -> None:
    logger.info("=" * 60)
    logger.info("  Pricing Optimisation Engine — Full Pipeline Run")
    logger.info("=" * 60)

    # ── Step 1: Raw data ──────────────────────────────────────────────────────
    if os.path.exists(RAW_DATA_PATH):
        logger.info("Step 1/7 — Loading existing raw dataset from %s", RAW_DATA_PATH)
        raw_df = load_data(RAW_DATA_PATH)
    else:
        logger.info("Step 1/7 — Generating synthetic dataset…")
        raw_df = generate_synthetic_data()
        save_data(raw_df, RAW_DATA_PATH)

    # ── Step 2: Preprocessing ─────────────────────────────────────────────────
    logger.info("Step 2/7 — Preprocessing…")
    clean_df = preprocess(raw_df)
    save_data(clean_df, PROCESSED_DATA_PATH)

    # ── Step 3: Elasticity estimation ─────────────────────────────────────────
    logger.info("Step 3/7 — Estimating price elasticity per product…")
    elasticity_df = compute_all_elasticities(clean_df)
    logger.info("\n%s", elasticity_df[["product_id", "category", "elasticity", "r_squared"]].to_string(index=False))

    # ── Step 4: Demand model construction ────────────────────────────────────
    logger.info("Step 4/7 — Building demand models…")
    models = build_demand_models(elasticity_df)

    # ── Step 5: Batch optimisation ────────────────────────────────────────────
    logger.info("Step 5/7 — Running batch price optimisation…")
    results_df = run_batch_optimization(models, elasticity_df, price_range_pct=0.30)
    logger.info("\n%s", results_df[["product_id", "current_price", "optimal_price", "expected_revenue_increase_pct"]].to_string(index=False))

    # ── Step 6: Save JSON results ─────────────────────────────────────────────
    logger.info("Step 6/7 — Saving results to %s", OUTPUTS_JSON)
    output_payload = {
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "pipeline_summary": {
            "total_products":      int(results_df["product_id"].nunique()),
            "avg_revenue_uplift":  round(float(results_df["expected_revenue_increase_pct"].mean()), 2),
            "max_revenue_uplift":  round(float(results_df["expected_revenue_increase_pct"].max()), 2),
        },
        "optimization_results": results_df.to_dict(orient="records"),
        "elasticity_summary":   elasticity_df[
            ["product_id", "category", "elasticity", "r_squared", "avg_price", "n_observations"]
        ].to_dict(orient="records"),
    }
    save_json(output_payload, OUTPUTS_JSON)

    # ── Step 7: Visualisations ────────────────────────────────────────────────
    logger.info("Step 7/7 — Generating visualisation plots…")
    os.makedirs(RESULTS_DIR, exist_ok=True)

    # Elasticity summary bar chart
    plot_elasticity_summary(
        elasticity_df,
        os.path.join(RESULTS_DIR, "elasticity_summary.png"),
    )

    # Revenue comparison bar chart
    plot_revenue_comparison(
        results_df,
        os.path.join(RESULTS_DIR, "revenue_comparison.png"),
    )

    # Per-product price vs demand and revenue curves
    price_lookup = elasticity_df.set_index("product_id")["avg_price"].to_dict()
    opt_lookup   = results_df.set_index("product_id")["optimal_price"].to_dict()

    for pid, model in models.items():
        current = price_lookup.get(pid, model.A)
        optimal = opt_lookup.get(pid, current)

        plot_price_vs_demand(
            model, current,
            os.path.join(RESULTS_DIR, f"{pid}_price_vs_demand.png"),
        )
        plot_price_vs_revenue(
            model, current, optimal,
            os.path.join(RESULTS_DIR, f"{pid}_price_vs_revenue.png"),
        )

    logger.info("=" * 60)
    logger.info("  Pipeline complete. Outputs saved to: %s", RESULTS_DIR)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
