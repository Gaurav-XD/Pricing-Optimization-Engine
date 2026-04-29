"""
utils.py
--------
Shared utilities for the Pricing Optimisation Engine.

Sections:
  1. Logging      — setup_logging()
  2. Plotting     — price vs demand, price vs revenue, elasticity bar chart
  3. Serialisation— NumpyEncoder, save_json, load_json
"""

import os
import json
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from typing import Any

# ── Seaborn theme (applied once on import) ────────────────────────────────────
sns.set_theme(style="whitegrid", palette="muted", font_scale=1.05)


# ── 1. Logging ────────────────────────────────────────────────────────────────

def setup_logging(level: str = "INFO") -> None:
    """
    Configure the root logger with a consistent, readable format.

    Args:
        level: Logging level string ('DEBUG', 'INFO', 'WARNING', 'ERROR').
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ── 2. Plotting ───────────────────────────────────────────────────────────────

def _ensure_dir(filepath: str) -> None:
    """Create parent directories for a file path if they do not exist."""
    parent = os.path.dirname(filepath)
    if parent:
        os.makedirs(parent, exist_ok=True)


def plot_price_vs_demand(
    model,
    current_price: float,
    output_path: str,
) -> None:
    """
    Render a price vs predicted demand curve for a single product.

    A vertical dashed line marks the current price.

    Args:
        model:         DemandModel instance.
        current_price: Current selling price (shown as reference line).
        output_path:   Destination PNG path.
    """
    price_min = current_price * 0.50
    price_max = current_price * 1.50
    curve = model.revenue_curve(price_min, price_max, n_points=200)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(curve["price"], curve["predicted_demand"], color="#2563EB", linewidth=2.5)
    ax.axvline(
        x=current_price, color="#DC2626", linestyle="--", linewidth=1.5,
        label=f"Current Price  ${current_price:,.2f}",
    )
    ax.set_xlabel("Price  ($)")
    ax.set_ylabel("Predicted Demand  (units)")
    ax.set_title(
        f"Price vs Demand  —  {model.product_id}",
        fontweight="bold",
    )
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.legend(frameon=True)
    sns.despine(ax=ax)

    _ensure_dir(output_path)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_price_vs_revenue(
    model,
    current_price: float,
    optimal_price: float,
    output_path: str,
) -> None:
    """
    Render a price vs predicted revenue curve for a single product.

    Vertical lines mark the current price and the revenue-maximising price.

    Args:
        model:         DemandModel instance.
        current_price: Current selling price.
        optimal_price: Revenue-maximising price returned by the optimiser.
        output_path:   Destination PNG path.
    """
    price_min = current_price * 0.50
    price_max = current_price * 1.50
    curve = model.revenue_curve(price_min, price_max, n_points=200)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(curve["price"], curve["predicted_revenue"], color="#16A34A", linewidth=2.5)
    ax.axvline(
        x=current_price, color="#DC2626", linestyle="--", linewidth=1.5,
        label=f"Current Price   ${current_price:,.2f}",
    )
    ax.axvline(
        x=optimal_price, color="#7C3AED", linestyle="-.", linewidth=1.5,
        label=f"Optimal Price   ${optimal_price:,.2f}",
    )
    ax.set_xlabel("Price  ($)")
    ax.set_ylabel("Predicted Revenue  ($)")
    ax.set_title(
        f"Price vs Revenue  —  {model.product_id}",
        fontweight="bold",
    )
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax.legend(frameon=True)
    sns.despine(ax=ax)

    _ensure_dir(output_path)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_elasticity_summary(
    elasticity_df: pd.DataFrame,
    output_path: str,
) -> None:
    """
    Horizontal bar chart showing price elasticity per product, coloured by category.

    A reference line at ε = -1 separates elastic from inelastic products.

    Args:
        elasticity_df: DataFrame with columns product_id, elasticity, category.
        output_path:   Destination PNG path.
    """
    df = elasticity_df.sort_values("elasticity").copy()
    categories    = df["category"].unique()
    palette       = sns.color_palette("Set2", n_colors=len(categories))
    category_color = dict(zip(categories, palette))
    bar_colors     = [category_color[c] for c in df["category"]]

    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.barh(df["product_id"], df["elasticity"], color=bar_colors, edgecolor="white")

    ax.axvline(
        x=-1, color="#6B7280", linestyle="--", linewidth=1.2,
        label="Unit elastic  (ε = −1)",
    )
    ax.set_xlabel("Price Elasticity of Demand  (ε)")
    ax.set_title("Price Elasticity by Product", fontweight="bold")
    ax.legend(frameon=True)

    # Value labels inside bars
    for bar, val in zip(bars, df["elasticity"]):
        ax.text(
            val - 0.05, bar.get_y() + bar.get_height() / 2.0,
            f"{val:.2f}", va="center", ha="right",
            fontsize=9, color="white", fontweight="bold",
        )

    # Category legend patches
    import matplotlib.patches as mpatches
    legend_patches = [
        mpatches.Patch(color=category_color[c], label=c) for c in categories
    ]
    ax.legend(handles=legend_patches + ax.get_legend_handles_labels()[0][-1:], frameon=True)

    sns.despine(ax=ax, left=False)
    _ensure_dir(output_path)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_revenue_comparison(
    results_df: pd.DataFrame,
    output_path: str,
) -> None:
    """
    Grouped bar chart comparing current vs optimal revenue per product.

    Args:
        results_df: Batch optimisation results DataFrame.
        output_path: Destination PNG path.
    """
    df  = results_df.sort_values("expected_revenue_increase_pct", ascending=False)
    x   = np.arange(len(df))
    w   = 0.38

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.bar(x - w / 2, df["current_revenue"], width=w, label="Current Revenue",
           color="#93C5FD", edgecolor="white")
    ax.bar(x + w / 2, df["optimal_revenue"], width=w, label="Optimal Revenue",
           color="#4ADE80", edgecolor="white")

    ax.set_xticks(x)
    ax.set_xticklabels(df["product_id"], rotation=30, ha="right")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.set_ylabel("Weekly Revenue  ($)")
    ax.set_title("Current vs Optimal Revenue per Product", fontweight="bold")
    ax.legend(frameon=True)
    sns.despine(ax=ax)

    _ensure_dir(output_path)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ── 3. Serialisation ──────────────────────────────────────────────────────────

class NumpyEncoder(json.JSONEncoder):
    """JSON encoder that safely serialises NumPy scalar and array types."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        return super().default(obj)


def save_json(data: Any, filepath: str) -> None:
    """
    Serialise data to a JSON file using NumpyEncoder.

    Args:
        data:     Python object (dict, list, etc.) to serialise.
        filepath: Destination path. Parent directories are created if needed.
    """
    _ensure_dir(filepath)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, cls=NumpyEncoder)


def load_json(filepath: str) -> Any:
    """
    Load JSON data from a file.

    Args:
        filepath: Path to the JSON file.

    Returns:
        Parsed Python object.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)
