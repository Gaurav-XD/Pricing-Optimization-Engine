"""
preprocessing.py
----------------
Cleans and prepares raw pricing data for modelling.

Pipeline steps:
  1. cast_types          — Enforce correct dtypes
  2. handle_missing      — Fill or drop missing values
  3. remove_outliers_iqr — IQR-based outlier removal per product
  4. engineer_features   — Derived columns (log transforms, revenue, time parts)

All functions are pure (return new DataFrames) to support easy testing and
pipeline composition.
"""

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── Type Casting ──────────────────────────────────────────────────────────────

def cast_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    Coerce columns to their expected data types.
    Parsing errors produce NaN, which are handled downstream.
    """
    df = df.copy()
    df["date"]          = pd.to_datetime(df["date"], errors="coerce")
    df["price"]         = pd.to_numeric(df["price"], errors="coerce")
    df["quantity_sold"] = pd.to_numeric(df["quantity_sold"], errors="coerce")
    df["product_id"]    = df["product_id"].astype(str).str.strip()
    df["category"]      = df["category"].astype(str).str.strip()
    return df


# ── Missing Value Handling ────────────────────────────────────────────────────

def handle_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Impute or remove missing values.

    Strategy:
    - price / quantity_sold: fill with per-product median (robust to skew).
    - Any remaining nulls in key columns: drop the row.
    - Enforce non-negative price and quantity constraints.
    """
    df = df.copy()
    initial_len = len(df)

    # Per-product median imputation
    for col in ("price", "quantity_sold"):
        df[col] = df.groupby("product_id")[col].transform(
            lambda x: x.fillna(x.median())
        )

    # Drop rows where imputation still failed (product with all-null prices, etc.)
    df.dropna(subset=["price", "quantity_sold", "date", "product_id"], inplace=True)

    # Sanity guards
    df = df[df["price"] > 0]
    df = df[df["quantity_sold"] >= 0]

    dropped = initial_len - len(df)
    if dropped:
        logger.warning("handle_missing_values: dropped %d rows.", dropped)

    return df


# ── Outlier Removal ───────────────────────────────────────────────────────────

def remove_outliers_iqr(
    df: pd.DataFrame,
    columns: list = None,
    multiplier: float = 3.0,
) -> pd.DataFrame:
    """
    Remove extreme values using the Tukey IQR fence per product group.

    A multiplier of 3.0 is intentionally conservative — it targets only extreme
    data errors (e.g. data-entry mistakes) while preserving legitimate spikes.

    Args:
        df:         Input DataFrame.
        columns:    Columns to inspect. Defaults to ['price', 'quantity_sold'].
        multiplier: IQR multiplier for fence width.

    Returns:
        Cleaned DataFrame with index reset.
    """
    if columns is None:
        columns = ["price", "quantity_sold"]

    df = df.copy()
    keep_mask = pd.Series(True, index=df.index)

    for col in columns:
        q1 = df.groupby("product_id")[col].transform("quantile", 0.25)
        q3 = df.groupby("product_id")[col].transform("quantile", 0.75)
        iqr = q3 - q1
        lower = q1 - multiplier * iqr
        upper = q3 + multiplier * iqr
        keep_mask &= df[col].between(lower, upper)

    removed = (~keep_mask).sum()
    if removed:
        logger.info("remove_outliers_iqr: removed %d outlier rows.", removed)

    return df[keep_mask].reset_index(drop=True)


# ── Feature Engineering ───────────────────────────────────────────────────────

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create derived columns used in modelling and visualisation.

    New columns:
    - log_price:    ln(price)   — dependent variable in log-log regression
    - log_quantity: ln(quantity)— predictor in log-log regression
    - revenue:      price × quantity_sold
    - year, month, quarter: temporal features for EDA
    """
    df = df.copy()
    df["log_price"]    = np.log(df["price"])
    df["log_quantity"] = np.log(df["quantity_sold"].clip(lower=1))  # clip avoids log(0)
    df["revenue"]      = df["price"] * df["quantity_sold"]
    df["year"]         = df["date"].dt.year
    df["month"]        = df["date"].dt.month
    df["quarter"]      = df["date"].dt.quarter
    return df


# ── Full Pipeline ─────────────────────────────────────────────────────────────

def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """
    Run the complete preprocessing pipeline in order.

    Args:
        df: Raw DataFrame (from data_loader.load_data or generate_synthetic_data).

    Returns:
        Clean, feature-enriched DataFrame ready for modelling.
    """
    logger.info("Starting preprocessing pipeline on %d rows…", len(df))
    df = cast_types(df)
    df = handle_missing_values(df)
    df = remove_outliers_iqr(df)
    df = engineer_features(df)
    logger.info("Preprocessing complete — output shape: %s.", df.shape)
    return df
