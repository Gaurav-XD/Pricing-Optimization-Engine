"""
elasticity.py
-------------
Estimates price elasticity of demand per product using log-log OLS regression.

Model specification:
    log(Q) = β₀ + β₁ · log(P) + ε

Where:
    β₁  = price elasticity of demand (PED)
    β₀  = log of the scale parameter A (where Q = A · P^β₁)

Interpretation of β₁:
    β₁ < -1   → elastic demand  (price-sensitive; revenue decreases with price increases)
    β₁ = -1   → unit elastic    (revenue unchanged by price changes)
    -1 < β₁ < 0 → inelastic demand (price-insensitive; revenue increases with price)
"""

import logging
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from scipy import stats
from typing import Optional

logger = logging.getLogger(__name__)


def _compute_p_value(X: np.ndarray, y: np.ndarray, y_pred: np.ndarray, coef: float) -> Optional[float]:
    """
    Compute two-tailed p-value for the regression slope via t-test.

    Uses stats.t.sf (survival function) instead of 1 - stats.t.cdf because for
    large t-statistics (|t| > ~45) the CDF saturates to 1.0 in floating-point,
    causing 1 - CDF to underflow to 0.0.  sf computes the tail probability
    directly and handles extreme t-values without loss of precision.

    Args:
        X:      1-D feature array (log_price values).
        y:      Target array (log_quantity values).
        y_pred: Predicted target array.
        coef:   Regression slope (elasticity estimate).

    Returns:
        p-value as a float, or None if it cannot be computed.
    """
    n = len(y)
    if n <= 2:
        return None

    ss_res = np.sum((y - y_pred) ** 2)
    x_var  = np.sum((X - X.mean()) ** 2)

    if x_var == 0:
        return None

    se      = np.sqrt(ss_res / (n - 2)) / np.sqrt(x_var)
    t_stat  = coef / se
    # sf is numerically stable for extreme t-values (avoids 1 - 1 = 0 underflow)
    p_value = 2.0 * stats.t.sf(abs(t_stat), df=n - 2)
    return float(p_value)


def compute_elasticity_for_product(group: pd.DataFrame) -> Optional[dict]:
    """
    Fit a log-log OLS regression and extract the elasticity for one product.

    Args:
        group: Slice of the preprocessed DataFrame for a single product.
               Must contain 'log_price' and 'log_quantity' columns.

    Returns:
        Dict with elasticity statistics, or None if the group is too small.
    """
    min_obs = 5
    if len(group) < min_obs:
        logger.warning(
            "Product %s: only %d observations — skipping (need ≥ %d).",
            group["product_id"].iloc[0], len(group), min_obs,
        )
        return None

    X = group["log_price"].values.reshape(-1, 1)
    y = group["log_quantity"].values

    model = LinearRegression()
    model.fit(X, y)

    elasticity = float(model.coef_[0])
    intercept  = float(model.intercept_)
    y_pred     = model.predict(X).flatten()

    # R² — proportion of variance in log(Q) explained by log(P)
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r_squared = float(1.0 - ss_res / ss_tot) if ss_tot != 0 else 0.0

    p_value = _compute_p_value(X.flatten(), y, y_pred, elasticity)

    # Human-readable significance string: avoids misleading "p = 0.0" in reports
    if p_value is None:
        p_value_str = "n/a"
    elif p_value < 0.0001:
        p_value_str = "< 0.0001"
    elif p_value < 0.001:
        p_value_str = f"{p_value:.4f}"
    else:
        p_value_str = f"{p_value:.4f}"

    return {
        "elasticity":     round(elasticity, 4),
        "intercept":      round(intercept, 4),
        "r_squared":      round(max(0.0, r_squared), 4),
        "p_value":        p_value,           # raw float for programmatic use
        "p_value_str":    p_value_str,       # display string for humans / API
        "n_observations": len(y),
    }


def compute_all_elasticities(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute price elasticity for every product in the dataset.

    Args:
        df: Preprocessed DataFrame containing 'log_price', 'log_quantity',
            'product_id', and 'category' columns.

    Returns:
        DataFrame (one row per product) with elasticity and model statistics.

    Raises:
        ValueError: If required columns are absent.
    """
    required = {"log_price", "log_quantity", "product_id", "category"}
    missing  = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns for elasticity calculation: {missing}")

    results = []
    for product_id, group in df.groupby("product_id"):
        stats_dict = compute_elasticity_for_product(group)
        if stats_dict is None:
            continue

        stats_dict["product_id"]   = product_id
        stats_dict["category"]     = group["category"].iloc[0]
        stats_dict["avg_price"]    = round(float(group["price"].mean()), 2)
        stats_dict["avg_quantity"] = round(float(group["quantity_sold"].mean()), 2)
        results.append(stats_dict)

    elasticity_df = pd.DataFrame(results)
    logger.info("Computed elasticity for %d products.", len(elasticity_df))
    return elasticity_df
