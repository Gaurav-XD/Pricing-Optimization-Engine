"""
revenue_model.py
----------------
Per-product demand and revenue models derived from log-log regression parameters.

The demand model is the direct analytical form of the log-log regression:

    log(Q) = β₀ + β₁ · log(P)
    ⟹  Q(P) = exp(β₀) · P^β₁  =  A · P^ε

Where:
    A   = exp(β₀)  — scale/amplitude parameter
    ε   = β₁       — price elasticity of demand

Revenue function:
    R(P) = P · Q(P) = A · P^(1 + ε)

The revenue-maximising price (unconstrained) satisfies dR/dP = 0:
    P* = ∞  when ε > -1  (inelastic, keep raising price)
    No finite optimum when ε ≤ -1 without a price ceiling constraint.
Therefore the optimizer uses a bounded grid search (see optimizer.py).
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict

logger = logging.getLogger(__name__)


class DemandModel:
    """
    Power-law demand model for a single product.

    Attributes:
        product_id: Product identifier.
        elasticity: Price elasticity of demand (β₁ from log-log regression).
        intercept:  Log-log regression intercept (β₀).
        A:          Scale parameter exp(β₀).
    """

    def __init__(self, product_id: str, elasticity: float, intercept: float) -> None:
        self.product_id = product_id
        self.elasticity = elasticity
        self.intercept  = intercept
        self.A          = np.exp(intercept)   # Q(P) = A · P^elasticity

    # ── Prediction ────────────────────────────────────────────────────────────

    def predict_demand(self, price: float) -> float:
        """
        Predict quantity sold at a given price.

        Q(P) = A · P^ε

        Args:
            price: Price to evaluate. Must be > 0.

        Returns:
            Non-negative predicted demand.

        Raises:
            ValueError: If price ≤ 0.
        """
        if price <= 0:
            raise ValueError(f"Price must be positive, got {price}.")
        return max(0.0, self.A * (price ** self.elasticity))

    def predict_revenue(self, price: float) -> float:
        """
        Predict revenue at a given price.

        R(P) = P · Q(P)

        Args:
            price: Price to evaluate. Must be > 0.

        Returns:
            Non-negative predicted revenue.
        """
        return price * self.predict_demand(price)

    # ── Curve Generation ─────────────────────────────────────────────────────

    def revenue_curve(
        self,
        price_min: float,
        price_max: float,
        n_points: int = 100,
    ) -> pd.DataFrame:
        """
        Generate price, demand, and revenue arrays over a price range.

        Useful for plotting and for the grid-search optimiser.

        Args:
            price_min: Lower bound of the price range.
            price_max: Upper bound of the price range.
            n_points:  Number of evenly spaced points.

        Returns:
            DataFrame with columns: price, predicted_demand, predicted_revenue.
        """
        if price_min <= 0 or price_max <= price_min:
            raise ValueError(
                f"Invalid price range: [{price_min}, {price_max}]. "
                "Both must be positive and price_min < price_max."
            )
        prices   = np.linspace(price_min, price_max, n_points)
        demands  = np.array([self.predict_demand(p) for p in prices])
        revenues = prices * demands

        return pd.DataFrame({
            "price":              prices,
            "predicted_demand":   demands,
            "predicted_revenue":  revenues,
        })

    def __repr__(self) -> str:
        return (
            f"DemandModel(product_id='{self.product_id}', "
            f"elasticity={self.elasticity:.4f}, A={self.A:.4f})"
        )


# ── Factory ───────────────────────────────────────────────────────────────────

def build_demand_models(elasticity_df: pd.DataFrame) -> Dict[str, DemandModel]:
    """
    Instantiate DemandModel objects for all products in the elasticity table.

    Args:
        elasticity_df: DataFrame with columns product_id, elasticity, intercept.

    Returns:
        Dict mapping product_id → DemandModel.

    Raises:
        ValueError: If required columns are missing.
    """
    required = {"product_id", "elasticity", "intercept"}
    missing  = required - set(elasticity_df.columns)
    if missing:
        raise ValueError(f"elasticity_df is missing columns: {missing}")

    models: Dict[str, DemandModel] = {}
    for _, row in elasticity_df.iterrows():
        model = DemandModel(
            product_id=row["product_id"],
            elasticity=row["elasticity"],
            intercept=row["intercept"],
        )
        models[row["product_id"]] = model
        logger.debug("Built %r", model)

    logger.info("Built %d demand models.", len(models))
    return models
