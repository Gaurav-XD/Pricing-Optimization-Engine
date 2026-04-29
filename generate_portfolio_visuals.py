"""
generate_portfolio_visuals.py
-----------------------------
Generates high-quality, portfolio-ready visualisations for the
Pricing Optimisation Engine.  Saves all outputs to /results/.

Run from project root:
    python generate_portfolio_visuals.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.colors import LinearSegmentedColormap
import seaborn as sns

from src.data_loader   import generate_synthetic_data
from src.preprocessing import preprocess
from src.elasticity    import compute_all_elasticities
from src.revenue_model import build_demand_models
from src.optimizer     import run_batch_optimization, optimize_price_for_product
from src.utils         import setup_logging

setup_logging()

# ── Style constants ────────────────────────────────────────────────────────────
BLUE    = "#2563EB"
GREEN   = "#16A34A"
RED     = "#DC2626"
PURPLE  = "#7C3AED"
ORANGE  = "#D97706"
GRAY    = "#6B7280"
LIGHT_B = "#BFDBFE"
LIGHT_G = "#BBF7D0"

sns.set_theme(style="whitegrid", font="DejaVu Sans")
plt.rcParams.update({
    "figure.dpi":        150,
    "savefig.dpi":       150,
    "savefig.bbox":      "tight",
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "font.size":         11,
})

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS, exist_ok=True)


# ── Data bootstrap ─────────────────────────────────────────────────────────────
raw      = generate_synthetic_data(seed=42)
clean    = preprocess(raw)
edf      = compute_all_elasticities(clean)
models   = build_demand_models(edf)
results  = run_batch_optimization(models, edf, price_range_pct=0.30)
price_lk = edf.set_index("product_id")["avg_price"].to_dict()
opt_lk   = results.set_index("product_id")["optimal_price"].to_dict()


# ══════════════════════════════════════════════════════════════════════════════
# 1.  ELASTICITY SUMMARY  (horizontal bar + category legend)
# ══════════════════════════════════════════════════════════════════════════════
def fig1_elasticity_summary():
    df = edf.sort_values("elasticity").copy()
    cats      = df["category"].unique()
    palette   = ["#2563EB", "#16A34A", "#D97706", "#7C3AED", "#DC2626"]
    cat_color = dict(zip(sorted(cats), palette))

    fig, ax = plt.subplots(figsize=(12, 6))

    bars = ax.barh(
        df["product_id"],
        df["elasticity"],
        color=[cat_color[c] for c in df["category"]],
        edgecolor="white",
        linewidth=0.8,
        height=0.65,
    )

    # Unit-elastic reference line
    ax.axvline(-1, color=GRAY, linestyle="--", linewidth=1.4, zorder=0, label="Unit elastic  (ε = −1)")

    # Value labels
    for bar, val in zip(bars, df["elasticity"]):
        ax.text(
            val + 0.04, bar.get_y() + bar.get_height() / 2,
            f"{val:.2f}", va="center", ha="left", fontsize=9.5,
            color="#1e293b", fontweight="bold",
        )

    # Category legend
    patches = [mpatches.Patch(color=cat_color[c], label=c) for c in sorted(cats)]
    l1 = ax.legend(handles=patches, title="Category", loc="lower right",
                   framealpha=0.95, fontsize=9)
    ax.add_artist(l1)
    ax.legend(loc="lower left", framealpha=0.95, fontsize=9)

    ax.set_xlabel("Price Elasticity of Demand  (ε)", labelpad=8)
    ax.set_title("Price Elasticity by Product\n"
                 "Elastic products (|ε| > 1) benefit from price reductions; "
                 "inelastic products from price increases",
                 fontweight="bold", pad=12)
    ax.set_xlim(df["elasticity"].min() * 1.18, 0.5)

    # Elastic / inelastic zone shading
    ax.axvspan(df["elasticity"].min() * 1.18, -1, alpha=0.04, color=BLUE, zorder=0)
    ax.axvspan(-1, 0.5, alpha=0.04, color=GREEN, zorder=0)
    ax.text(-1.85, -0.85, "ELASTIC ZONE", fontsize=8, color=BLUE, alpha=0.6, style="italic")
    ax.text(-0.90, -0.85, "INELASTIC ZONE", fontsize=8, color=GREEN, alpha=0.6, style="italic")

    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS, "01_elasticity_summary.png"))
    plt.close()
    print("  Saved: 01_elasticity_summary.png")


# ══════════════════════════════════════════════════════════════════════════════
# 2.  REVENUE UPLIFT  (grouped bar: current vs optimal)
# ══════════════════════════════════════════════════════════════════════════════
def fig2_revenue_uplift():
    df = results.merge(edf[["product_id", "category"]], on="product_id")
    df = df.sort_values("expected_revenue_increase_pct", ascending=False).copy()
    x  = np.arange(len(df))
    w  = 0.36

    fig, axes = plt.subplots(2, 1, figsize=(13, 9),
                              gridspec_kw={"height_ratios": [2.5, 1], "hspace": 0.35})

    # — Top panel: revenue bars —
    ax = axes[0]
    b1 = ax.bar(x - w/2, df["current_revenue"] / 1000, width=w,
                label="Current Revenue", color=LIGHT_B, edgecolor=BLUE, linewidth=0.8)
    b2 = ax.bar(x + w/2, df["optimal_revenue"] / 1000, width=w,
                label="Optimal Revenue", color=LIGHT_G, edgecolor=GREEN, linewidth=0.8)

    ax.set_xticks(x)
    ax.set_xticklabels(
        [f"{row['product_id']}\n{row['category'].split()[0]}" for _, row in df.iterrows()],
        fontsize=9,
    )
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}K"))
    ax.set_ylabel("Predicted Weekly Revenue")
    ax.set_title("Current vs Optimal Weekly Revenue per Product", fontweight="bold", pad=10)
    ax.legend(framealpha=0.95)

    # Uplift annotation arrows
    for i, row in enumerate(df.itertuples()):
        uplift = row.expected_revenue_increase_pct
        ax.annotate(
            f"+{uplift:.1f}%",
            xy=(i + w/2, row.optimal_revenue / 1000),
            xytext=(0, 6), textcoords="offset points",
            ha="center", fontsize=7.5, color=GREEN, fontweight="bold",
        )

    # — Bottom panel: % uplift bar chart —
    ax2 = axes[1]
    colors_bar = [GREEN if v > 10 else ORANGE if v > 5 else GRAY
                  for v in df["expected_revenue_increase_pct"]]
    ax2.bar(x, df["expected_revenue_increase_pct"], color=colors_bar, edgecolor="white")
    ax2.set_xticks(x)
    ax2.set_xticklabels(df["product_id"], fontsize=9)
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax2.set_ylabel("Revenue Uplift")
    ax2.set_title("Expected Revenue Uplift (%)", fontweight="bold", pad=8)
    ax2.axhline(y=df["expected_revenue_increase_pct"].mean(), color=RED,
                linestyle="--", linewidth=1.2,
                label=f"Average uplift  {df['expected_revenue_increase_pct'].mean():.1f}%")
    ax2.legend(fontsize=9, framealpha=0.95)

    plt.savefig(os.path.join(RESULTS, "02_revenue_uplift.png"))
    plt.close()
    print("  Saved: 02_revenue_uplift.png")


# ══════════════════════════════════════════════════════════════════════════════
# 3.  PRICE vs DEMAND + REVENUE  (2×2 showcase: P001, P002, P005, P009)
# ══════════════════════════════════════════════════════════════════════════════
def fig3_showcase_curves():
    showcase = [
        ("P001", "Electronics — Highly Elastic"),
        ("P002", "Electronics — Most Elastic"),
        ("P005", "Food — Inelastic"),
        ("P009", "Home — Highly Elastic"),
    ]

    fig, axes = plt.subplots(2, 4, figsize=(18, 9))
    fig.suptitle("Price vs Demand & Revenue Curves — Selected Products",
                 fontweight="bold", fontsize=13, y=1.01)

    for col, (pid, label) in enumerate(showcase):
        model   = models[pid]
        curr    = float(price_lk[pid])
        opt     = float(opt_lk[pid])
        pmin    = curr * 0.50
        pmax    = curr * 1.50
        curve   = model.revenue_curve(pmin, pmax, n_points=300)

        # — Demand curve —
        ax_d = axes[0][col]
        ax_d.plot(curve["price"], curve["predicted_demand"],
                  color=BLUE, linewidth=2.2)
        ax_d.axvline(curr, color=RED, linestyle="--", linewidth=1.5,
                     label=f"Current ${curr:,.0f}")
        ax_d.axvline(opt, color=PURPLE, linestyle="-.", linewidth=1.5,
                     label=f"Optimal ${opt:,.0f}")
        ax_d.fill_between(curve["price"], curve["predicted_demand"],
                           alpha=0.08, color=BLUE)
        ax_d.set_title(f"{pid}\n{label}", fontsize=9.5, fontweight="bold")
        ax_d.set_xlabel("Price ($)", fontsize=8.5)
        ax_d.set_ylabel("Demand (units)", fontsize=8.5)
        ax_d.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax_d.legend(fontsize=7.5, framealpha=0.9)
        ax_d.tick_params(labelsize=8)

        # — Revenue curve —
        ax_r = axes[1][col]
        rev_peak_idx = curve["predicted_revenue"].idxmax()
        rev_peak_p   = curve.loc[rev_peak_idx, "price"]

        ax_r.plot(curve["price"], curve["predicted_revenue"] / 1000,
                  color=GREEN, linewidth=2.2)
        ax_r.fill_between(curve["price"], curve["predicted_revenue"] / 1000,
                           alpha=0.08, color=GREEN)
        ax_r.axvline(curr, color=RED, linestyle="--", linewidth=1.5,
                     label=f"Current ${curr:,.0f}")
        ax_r.axvline(opt, color=PURPLE, linestyle="-.", linewidth=1.5,
                     label=f"Optimal ${opt:,.0f}")

        # Mark the peak
        ax_r.axvline(rev_peak_p, color=ORANGE, linestyle=":", linewidth=1.2,
                     label=f"Model peak ${rev_peak_p:,.0f}")

        ε   = edf.set_index("product_id").loc[pid, "elasticity"]
        pct = results.set_index("product_id").loc[pid, "expected_revenue_increase_pct"]
        ax_r.set_title(f"ε = {ε:.2f}  |  Uplift: +{pct:.1f}%",
                        fontsize=9, color="#1e293b")
        ax_r.set_xlabel("Price ($)", fontsize=8.5)
        ax_r.set_ylabel("Revenue ($K)", fontsize=8.5)
        ax_r.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}K"))
        ax_r.legend(fontsize=7.5, framealpha=0.9)
        ax_r.tick_params(labelsize=8)

    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS, "03_price_demand_revenue_showcase.png"), bbox_inches="tight")
    plt.close()
    print("  Saved: 03_price_demand_revenue_showcase.png")


# ══════════════════════════════════════════════════════════════════════════════
# 4.  DEMAND SCATTER + REGRESSION FIT  (log-log space, 4 products)
# ══════════════════════════════════════════════════════════════════════════════
def fig4_regression_fit():
    showcase = ["P001", "P002", "P005", "P009"]
    fig, axes = plt.subplots(1, 4, figsize=(17, 4.5))
    fig.suptitle("Log-Log Regression Fit: log(Price) vs log(Quantity)",
                 fontweight="bold", fontsize=12, y=1.02)

    for ax, pid in zip(axes, showcase):
        grp = clean[clean["product_id"] == pid]
        r2  = float(edf.set_index("product_id").loc[pid, "r_squared"])
        e   = float(edf.set_index("product_id").loc[pid, "elasticity"])

        ax.scatter(grp["log_price"], grp["log_quantity"],
                   alpha=0.35, s=18, color=BLUE, label="Observed")

        # Regression line
        x_line = np.linspace(grp["log_price"].min(), grp["log_price"].max(), 200)
        model  = models[pid]
        y_line = np.log(model.A) + e * x_line
        ax.plot(x_line, y_line, color=RED, linewidth=2.0,
                label=f"OLS fit  ε={e:.2f}")

        # Confidence band (±1.96 SE of residuals)
        resid   = grp["log_quantity"].values - (np.log(model.A) + e * grp["log_price"].values)
        se_band = 1.96 * resid.std()
        ax.fill_between(x_line, y_line - se_band, y_line + se_band,
                        alpha=0.12, color=RED)

        ax.set_title(f"{pid}  —  R² = {r2:.3f}", fontweight="bold", fontsize=10)
        ax.set_xlabel("log(Price)", fontsize=9)
        ax.set_ylabel("log(Quantity)", fontsize=9)
        ax.legend(fontsize=8.5, framealpha=0.9)
        ax.tick_params(labelsize=8.5)

    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS, "04_log_log_regression_fit.png"), bbox_inches="tight")
    plt.close()
    print("  Saved: 04_log_log_regression_fit.png")


# ══════════════════════════════════════════════════════════════════════════════
# 5.  OPTIMISATION HEATMAP  (price × product revenue matrix)
# ══════════════════════════════════════════════════════════════════════════════
def fig5_revenue_heatmap():
    product_ids  = sorted(models.keys())
    price_steps  = np.linspace(0.60, 1.40, 17)   # ±40% in 5% steps
    matrix       = np.zeros((len(product_ids), len(price_steps)))

    for i, pid in enumerate(product_ids):
        model = models[pid]
        base  = float(price_lk[pid])
        for j, pct in enumerate(price_steps):
            matrix[i, j] = model.predict_revenue(base * pct)

    # Normalise each row to % of base-price revenue (column index=8 ≈ 1.00)
    base_col = np.argmin(np.abs(price_steps - 1.0))
    matrix_pct = (matrix / matrix[:, base_col:base_col+1] - 1.0) * 100

    labels_x = [f"{int((p - 1)*100):+d}%" for p in price_steps]
    labels_y = [f"{pid} ({edf.set_index('product_id').loc[pid,'category']})" for pid in product_ids]

    fig, ax = plt.subplots(figsize=(14, 6))
    cmap = LinearSegmentedColormap.from_list("rev", [RED, "#FEF3C7", GREEN], N=256)
    im = ax.imshow(matrix_pct, aspect="auto", cmap=cmap,
                   vmin=-40, vmax=40)

    # Cell annotations
    for i in range(len(product_ids)):
        for j in range(len(price_steps)):
            val = matrix_pct[i, j]
            color = "white" if abs(val) > 22 else "#1e293b"
            ax.text(j, i, f"{val:+.0f}%", ha="center", va="center",
                    fontsize=7.5, color=color, fontweight="bold")

    # Mark the optimal cell per row
    for i, pid in enumerate(product_ids):
        best_j = int(np.argmax(matrix_pct[i]))
        ax.add_patch(plt.Rectangle(
            (best_j - 0.5, i - 0.5), 1, 1,
            fill=False, edgecolor="white", linewidth=2.5
        ))

    ax.set_xticks(range(len(price_steps)))
    ax.set_xticklabels(labels_x, fontsize=8.5)
    ax.set_yticks(range(len(product_ids)))
    ax.set_yticklabels(labels_y, fontsize=9)
    ax.set_xlabel("Price Change from Current  (%)", labelpad=8)
    ax.set_title("Revenue Impact Heatmap — % Change vs Current Revenue\n"
                 "White-bordered cell = optimal price per product",
                 fontweight="bold", pad=10)

    cbar = plt.colorbar(im, ax=ax, shrink=0.85, pad=0.02)
    cbar.set_label("Revenue Δ (%)", fontsize=9)

    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS, "05_revenue_heatmap.png"), bbox_inches="tight")
    plt.close()
    print("  Saved: 05_revenue_heatmap.png")


# ══════════════════════════════════════════════════════════════════════════════
# 6.  SIMULATION WATERFALL  (P001 single-product deep-dive)
# ══════════════════════════════════════════════════════════════════════════════
def fig6_simulation_waterfall():
    pid     = "P001"
    model   = models[pid]
    curr    = float(price_lk[pid])
    result  = optimize_price_for_product(model, curr, price_range_pct=0.30)
    sim     = result["simulation"]
    opt_p   = result["optimal_price"]
    opt_r   = result["optimal_revenue"]
    curr_r  = result["current_revenue"]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle(f"P001 (Electronics) — Price Optimisation Deep-Dive\n"
                 f"Elasticity: {model.elasticity:.2f}  |  "
                 f"Revenue Uplift: +{result['expected_revenue_increase_pct']:.1f}%",
                 fontweight="bold", fontsize=11, y=1.02)

    # — Left: demand simulation —
    ax = axes[0]
    ax.plot(sim["price"], sim["predicted_demand"],
            color=BLUE, linewidth=2.2, label="Predicted demand")
    ax.axvline(curr, color=RED, linestyle="--", linewidth=1.8,
               label=f"Current  ${curr:.2f}")
    ax.axvline(opt_p, color=PURPLE, linestyle="-.", linewidth=1.8,
               label=f"Optimal  ${opt_p:.2f}")
    ax.fill_between(sim["price"], sim["predicted_demand"], alpha=0.07, color=BLUE)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_xlabel("Price ($)")
    ax.set_ylabel("Predicted Units Sold")
    ax.set_title("Price vs Demand Curve", fontweight="bold")
    ax.legend(framealpha=0.95)

    # — Right: revenue simulation with shaded gain —
    ax2 = axes[1]
    rev_k = sim["predicted_revenue"] / 1000
    ax2.plot(sim["price"], rev_k, color=GREEN, linewidth=2.2, label="Predicted revenue")
    ax2.fill_between(sim["price"], rev_k, alpha=0.08, color=GREEN)

    # Shade the gain region
    gain_mask = sim["price"] <= opt_p
    ax2.fill_between(
        sim.loc[gain_mask, "price"],
        curr_r / 1000,
        sim.loc[gain_mask, "predicted_revenue"] / 1000,
        alpha=0.18, color=GREEN,
        label=f"Revenue gain region  (+{result['expected_revenue_increase_pct']:.1f}%)",
    )

    ax2.axvline(curr, color=RED, linestyle="--", linewidth=1.8,
                label=f"Current  ${curr:.2f}  (${curr_r/1000:,.1f}K)")
    ax2.axvline(opt_p, color=PURPLE, linestyle="-.", linewidth=1.8,
                label=f"Optimal  ${opt_p:.2f}  (${opt_r/1000:,.1f}K)")
    ax2.axhline(curr_r / 1000, color=RED, linestyle=":", linewidth=1.0, alpha=0.5)
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}K"))
    ax2.set_xlabel("Price ($)")
    ax2.set_ylabel("Revenue ($K / week)")
    ax2.set_title("Price vs Revenue Curve", fontweight="bold")
    ax2.legend(framealpha=0.95, fontsize=8.5)

    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS, "06_P001_deep_dive.png"), bbox_inches="tight")
    plt.close()
    print("  Saved: 06_P001_deep_dive.png")


# ══════════════════════════════════════════════════════════════════════════════
# 7.  CATEGORY SUMMARY  (box plots + metrics table)
# ══════════════════════════════════════════════════════════════════════════════
def fig7_category_summary():
    raw_cat = raw.copy()
    raw_cat["date"] = pd.to_datetime(raw_cat["date"])
    raw_cat["revenue"] = raw_cat["price"] * raw_cat["quantity_sold"]

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle("Category-Level Pricing Analysis", fontweight="bold", fontsize=12, y=1.02)

    palette = {"Electronics": BLUE, "Clothing": PURPLE, "Food": GREEN,
               "Sports": ORANGE, "Home": RED}

    # — Price distribution by category —
    for cat, grp in raw_cat.groupby("category"):
        axes[0].hist(grp["price"], bins=30, alpha=0.55, color=palette[cat],
                     label=cat, edgecolor="white", linewidth=0.4)
    axes[0].set_xlabel("Price ($)")
    axes[0].set_ylabel("Frequency")
    axes[0].set_title("Price Distribution by Category", fontweight="bold")
    axes[0].legend(fontsize=8.5)

    # — Average elasticity per category —
    cat_e = edf.groupby("category")["elasticity"].mean().sort_values()
    colors_cat = [palette[c] for c in cat_e.index]
    axes[1].barh(cat_e.index, cat_e.values, color=colors_cat, edgecolor="white", height=0.5)
    axes[1].axvline(-1, color=GRAY, linestyle="--", linewidth=1.2,
                    label="Unit elastic (ε = −1)")
    for i, (cat, val) in enumerate(cat_e.items()):
        axes[1].text(val + 0.04, i, f"{val:.2f}", va="center", fontsize=9.5, fontweight="bold")
    axes[1].set_xlabel("Mean Price Elasticity")
    axes[1].set_title("Average Elasticity by Category", fontweight="bold")
    axes[1].legend(fontsize=8.5)

    # — Revenue uplift by category —
    res_cat = results.merge(edf[["product_id", "category"]], on="product_id")
    cat_up  = res_cat.groupby("category")["expected_revenue_increase_pct"].mean().sort_values(ascending=False)
    colors_up = [palette[c] for c in cat_up.index]
    bars = axes[2].bar(cat_up.index, cat_up.values, color=colors_up,
                       edgecolor="white", width=0.5)
    for bar, val in zip(bars, cat_up.values):
        axes[2].text(bar.get_x() + bar.get_width()/2, val + 0.5,
                     f"+{val:.1f}%", ha="center", fontsize=9.5, fontweight="bold")
    axes[2].set_ylabel("Avg Revenue Uplift (%)")
    axes[2].set_title("Average Revenue Uplift by Category", fontweight="bold")
    axes[2].tick_params(axis="x", rotation=15)

    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS, "07_category_summary.png"), bbox_inches="tight")
    plt.close()
    print("  Saved: 07_category_summary.png")


# ══════════════════════════════════════════════════════════════════════════════
# 8.  WEEKLY REVENUE TREND  (time series per category)
# ══════════════════════════════════════════════════════════════════════════════
def fig8_revenue_trend():
    raw_ts = raw.copy()
    raw_ts["date"]    = pd.to_datetime(raw_ts["date"])
    raw_ts["revenue"] = raw_ts["price"] * raw_ts["quantity_sold"]

    weekly = (
        raw_ts.groupby(["date", "category"])["revenue"]
        .sum().reset_index()
    )

    palette = {"Electronics": BLUE, "Clothing": PURPLE, "Food": GREEN,
               "Sports": ORANGE, "Home": RED}

    fig, ax = plt.subplots(figsize=(14, 5))

    for cat, grp in weekly.groupby("category"):
        grp = grp.sort_values("date")
        # Rolling 4-week average for smoother line
        smooth = grp["revenue"].rolling(4, min_periods=1).mean()
        ax.plot(grp["date"], grp["revenue"] / 1000, alpha=0.18,
                color=palette[cat], linewidth=1)
        ax.plot(grp["date"], smooth / 1000, color=palette[cat],
                linewidth=2.0, label=cat)

    ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%b '%y"))
    ax.xaxis.set_major_locator(plt.matplotlib.dates.MonthLocator(interval=3))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}K"))
    ax.set_ylabel("Weekly Revenue ($K)")
    ax.set_title("Weekly Revenue Trend by Category  (2022 – 2024)\n"
                 "Solid line = 4-week rolling average",
                 fontweight="bold", pad=10)
    ax.legend(framealpha=0.95)
    ax.grid(axis="x", alpha=0.3)
    sns.despine(ax=ax)

    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS, "08_weekly_revenue_trend.png"), bbox_inches="tight")
    plt.close()
    print("  Saved: 08_weekly_revenue_trend.png")


# ══════════════════════════════════════════════════════════════════════════════
# Run all
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 55)
    print("  Generating Portfolio Visualisations")
    print("=" * 55)
    fig1_elasticity_summary()
    fig2_revenue_uplift()
    fig3_showcase_curves()
    fig4_regression_fit()
    fig5_revenue_heatmap()
    fig6_simulation_waterfall()
    fig7_category_summary()
    fig8_revenue_trend()
    print()
    print("  All 8 charts saved to:", RESULTS)
    print("=" * 55)
