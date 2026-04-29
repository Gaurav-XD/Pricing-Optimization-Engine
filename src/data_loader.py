"""
data_loader.py
--------------
Generates synthetic pricing & demand data and provides a loader for CSV datasets.

Synthetic data is built on a power-law demand model:
    Q = Q_base * (P / P_base) ^ elasticity * noise

This creates realistic, non-linear price-demand relationships where higher
prices lead to lower quantity sold, with per-product elasticity variation
and weekly seasonality.
"""

import os
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Product Catalogue ──────────────────────────────────────────────────────────
# Each product has a base price, base weekly demand, and a true elasticity.
# The optimizer should recover values close to these from the regression.
PRODUCT_CATALOGUE = {
    "P001": {"category": "Electronics", "base_price": 150.0, "base_demand": 500,  "elasticity": -1.80},
    "P002": {"category": "Electronics", "base_price": 250.0, "base_demand": 300,  "elasticity": -2.10},
    "P003": {"category": "Clothing",    "base_price":  60.0, "base_demand": 800,  "elasticity": -1.20},
    "P004": {"category": "Clothing",    "base_price":  90.0, "base_demand": 600,  "elasticity": -1.50},
    "P005": {"category": "Food",        "base_price":  20.0, "base_demand": 2000, "elasticity": -0.80},
    "P006": {"category": "Food",        "base_price":  35.0, "base_demand": 1200, "elasticity": -0.90},
    "P007": {"category": "Sports",      "base_price": 120.0, "base_demand": 400,  "elasticity": -1.60},
    "P008": {"category": "Sports",      "base_price":  80.0, "base_demand": 550,  "elasticity": -1.30},
    "P009": {"category": "Home",        "base_price": 200.0, "base_demand": 250,  "elasticity": -1.90},
    "P010": {"category": "Home",        "base_price":  45.0, "base_demand": 900,  "elasticity": -1.10},
}


def generate_synthetic_data(
    start_date: str = "2022-01-01",
    end_date: str = "2024-12-31",
    price_variation: float = 0.30,
    noise_level: float = 0.15,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate a synthetic weekly pricing & demand dataset.

    For each product and each week in the date range:
    - Price is drawn from a uniform distribution around the base price.
    - Demand follows a power-law: Q = Q_base * (P / P_base)^elasticity
    - Log-normal noise is added to simulate real-world variation.
    - A mild sinusoidal seasonal factor peaks in Q4 (holiday effect).

    Args:
        start_date:      First date in the range (inclusive).
        end_date:        Last date in the range (inclusive).
        price_variation: Maximum fractional deviation from base price (±).
        noise_level:     Std-dev of the log-normal noise multiplier.
        seed:            Random seed for reproducibility.

    Returns:
        DataFrame with columns: product_id, category, date, price, quantity_sold.
    """
    np.random.seed(seed)
    records = []
    date_range = pd.date_range(start=start_date, end=end_date, freq="W")

    for product_id, meta in PRODUCT_CATALOGUE.items():
        base_price  = meta["base_price"]
        base_demand = meta["base_demand"]
        elasticity  = meta["elasticity"]
        category    = meta["category"]

        for date in date_range:
            # Randomly vary the price within the allowed band
            price_multiplier = 1.0 + np.random.uniform(-price_variation, price_variation)
            price = round(base_price * price_multiplier, 2)

            # Power-law demand response to price change
            demand_base = base_demand * ((price / base_price) ** elasticity)

            # Multiplicative log-normal noise (always keeps demand positive)
            noise = np.random.lognormal(mean=0.0, sigma=noise_level)
            quantity = demand_base * noise

            # Mild seasonal effect: +10 % peak in summer (month 6), trough in winter
            seasonal_boost = 1.0 + 0.10 * np.sin(2 * np.pi * (date.month - 3) / 12)
            quantity = max(1, int(quantity * seasonal_boost))

            records.append({
                "product_id":    product_id,
                "category":      category,
                "date":          date.strftime("%Y-%m-%d"),
                "price":         price,
                "quantity_sold": quantity,
            })

    df = pd.DataFrame(records)
    logger.info(
        "Generated %d synthetic records for %d products (%s → %s).",
        len(df), len(PRODUCT_CATALOGUE), start_date, end_date,
    )
    return df


def load_data(filepath: str) -> pd.DataFrame:
    """
    Load a pricing dataset from CSV with schema validation.

    Args:
        filepath: Absolute or relative path to the CSV file.

    Returns:
        DataFrame with at least the required columns.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError:        If required columns are missing.
    """
    required_columns = {"product_id", "price", "quantity_sold", "date", "category"}

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Data file not found: {filepath}")

    df = pd.read_csv(filepath, parse_dates=["date"])

    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")

    logger.info("Loaded %d records from '%s'.", len(df), filepath)
    return df


def save_data(df: pd.DataFrame, filepath: str) -> None:
    """
    Persist a DataFrame to CSV, creating parent directories as needed.

    Args:
        df:       DataFrame to save.
        filepath: Destination path.
    """
    parent = os.path.dirname(filepath)
    if parent:
        os.makedirs(parent, exist_ok=True)
    df.to_csv(filepath, index=False)
    logger.info("Saved %d records to '%s'.", len(df), filepath)
