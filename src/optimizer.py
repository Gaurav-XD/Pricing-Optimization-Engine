"""
optimizer.py
------------
Price optimisation engine.

Strategy: bounded grid-search (brute-force simulation)
---------------------------------------------------------
For each product we simulate N evenly spaced price points within ±range% of
the current price and evaluate the predicted revenue at each point.  We then
return the price that maximises revenue together with the % improvement over
the current price.

Why grid-search rather than gradient-based optimisation?
- Transparent and auditable (can show the full simulation table).
- No convergence issues for the power-law revenue function.
- Fast enough at N=200 for interactive use.

For problems with profit constraints or cost structures, the grid can be
extended to include a margin floor — see the `cost_per_unit` parameter.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Optional

from .revenue_model import DemandModel

logger = logging.getLogger(__name__)


def optimize_price_for_product(
    model: DemandModel,
    current_price: float,
    price_range_pct: float = 0.30,
    n_simulations: int = 200,
    cost_per_unit: Optional[float] = None,
) -> Dict:
    """
    Find the revenue-maximising price for a product within a bounded range.

    The search space is [current_price × (1 - range), current_price × (1 + range)].

    Args:
        model:           DemandModel for the product.
        current_price:   Current selling price (must be > 0).
        price_range_pct: Fractional search radius around current price (default ±30 %).
        n_simulations:   Number of candidate price points (resolution of the grid).
        cost_per_unit:   Optional unit cost for profit maximisation.
                         If provided, the engine maximises (P - cost) × Q instead of P × Q.

    Returns:
        Dict with keys:
            product_id, current_price, optimal_price,
            current_revenue, optimal_revenue,
            expected_revenue_increase_pct, elasticity,
            simulation (DataFrame of all evaluated price points).

    Raises:
        ValueError: If current_price ≤ 0.
    """
    if current_price <= 0:
        raise ValueError(f"current_price must be positive, got {current_price}.")

    price_min = max(0.01, current_price * (1.0 - price_range_pct))
    price_max = current_price * (1.0 + price_range_pct)

    prices  = np.linspace(price_min, price_max, n_simulations)
    demands = np.array([model.predict_demand(p) for p in prices])

    if cost_per_unit is not None:
        # Profit maximisation mode
        objective = (prices - cost_per_unit) * demands
        objective_label = "predicted_profit"
    else:
        # Revenue maximisation mode (default)
        objective = prices * demands
        objective_label = "predicted_revenue"

    revenues  = prices * demands  # always record revenue regardless of objective
    optimal_idx     = int(np.argmax(objective))
    optimal_price   = float(prices[optimal_idx])
    optimal_revenue = float(revenues[optimal_idx])
    current_revenue = float(model.predict_revenue(current_price))

    revenue_increase_pct = (
        (optimal_revenue - current_revenue) / current_revenue * 100.0
        if current_revenue > 0 else 0.0
    )

    # Full simulation table (useful for visualisations and auditing)
    simulation_df = pd.DataFrame({
        "price":              prices,
        "predicted_demand":   demands,
        "predicted_revenue":  revenues,
        objective_label:      objective,
    })

    logger.debug(
        "Optimised %s: current=$%.2f optimal=$%.2f Δrev=%.1f%%",
        model.product_id, current_price, optimal_price, revenue_increase_pct,
    )

    return {
        "product_id":                   model.product_id,
        "current_price":                round(current_price, 2),
        "optimal_price":                round(optimal_price, 2),
        "current_revenue":              round(current_revenue, 2),
        "optimal_revenue":              round(optimal_revenue, 2),
        "expected_revenue_increase_pct": round(revenue_increase_pct, 2),
        "elasticity":                   round(model.elasticity, 4),
        "simulation":                   simulation_df,
    }


def run_batch_optimization(
    models: Dict[str, DemandModel],
    elasticity_df: pd.DataFrame,
    price_range_pct: float = 0.30,
    cost_map: Optional[Dict[str, float]] = None,
) -> pd.DataFrame:
    """
    Run price optimisation for every product using its average historical price.

    Args:
        models:          Dict of product_id → DemandModel.
        elasticity_df:   DataFrame with avg_price per product (from elasticity.py).
        price_range_pct: Search radius passed to optimize_price_for_product.
        cost_map:        Optional dict of product_id → unit cost for profit mode.

    Returns:
        DataFrame with one optimisation summary row per product.
    """
    price_lookup = elasticity_df.set_index("product_id")["avg_price"].to_dict()
    results = []

    for product_id, model in models.items():
        current_price = price_lookup.get(product_id)
        if not current_price or current_price <= 0:
            logger.warning("Skipping %s — no valid average price found.", product_id)
            continue

        cost = cost_map.get(product_id) if cost_map else None
        result = optimize_price_for_product(
            model=model,
            current_price=current_price,
            price_range_pct=price_range_pct,
            cost_per_unit=cost,
        )
        # Exclude the simulation DataFrame from the batch summary
        summary = {k: v for k, v in result.items() if k != "simulation"}
        results.append(summary)

    df_results = pd.DataFrame(results)
    logger.info(
        "Batch optimisation complete. %d products processed.", len(df_results)
    )
    return df_results
