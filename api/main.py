"""
api/main.py
-----------
FastAPI application for the Pricing Optimisation Engine.

Endpoints
---------
GET  /health                           — Liveness / readiness check
GET  /products                         — List products with elasticity metadata
POST /optimize-price                   — Recommend an optimal price
GET  /revenue-curve/{product_id}       — Revenue curve data for a price range

Startup
-------
On application start the engine:
  1. Generates (or loads) the raw pricing dataset.
  2. Runs the preprocessing pipeline.
  3. Estimates price elasticity per product.
  4. Builds per-product demand models.

All models are held in app_state (module-level dict) and shared across requests.
"""

import os
import sys
import logging
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

# ── Path setup ────────────────────────────────────────────────────────────────
# Ensure the project root is importable regardless of working directory.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils import setup_logging
from src.data_loader import generate_synthetic_data, load_data, save_data
from src.preprocessing import preprocess
from src.elasticity import compute_all_elasticities
from src.revenue_model import build_demand_models
from src.optimizer import optimize_price_for_product

setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# ── Resolved file paths ───────────────────────────────────────────────────────
RAW_DATA_PATH       = os.path.join(PROJECT_ROOT, os.getenv("DATA_PATH", "data/raw/pricing_data.csv"))
PROCESSED_DATA_PATH = os.path.join(PROJECT_ROOT, os.getenv("PROCESSED_DATA_PATH", "data/processed/clean_data.csv"))

# ── Shared application state (populated at startup) ───────────────────────────
app_state: Dict = {}


# ── Startup / shutdown ────────────────────────────────────────────────────────

def _bootstrap_engine() -> None:
    """
    Generate or load data, run the full modelling pipeline, and populate app_state.
    Called once during application lifespan startup.
    """
    # Step 1 — Raw data
    if not os.path.exists(RAW_DATA_PATH):
        logger.info("Raw dataset not found — generating synthetic data…")
        raw_df = generate_synthetic_data()
        save_data(raw_df, RAW_DATA_PATH)
    else:
        raw_df = load_data(RAW_DATA_PATH)

    # Step 2 — Preprocessing
    clean_df = preprocess(raw_df)
    save_data(clean_df, PROCESSED_DATA_PATH)

    # Step 3 — Elasticity estimation
    elasticity_df = compute_all_elasticities(clean_df)

    # Step 4 — Demand model construction
    models = build_demand_models(elasticity_df)

    app_state["models"]       = models
    app_state["elasticity_df"] = elasticity_df


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== Pricing Optimisation Engine — starting up ===")
    _bootstrap_engine()
    logger.info("Engine ready. %d product models loaded.", len(app_state["models"]))
    yield
    logger.info("=== Pricing Optimisation Engine — shutting down ===")


# ── Application ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Pricing Optimisation Engine",
    description=(
        "Analyses historical price-demand relationships, estimates price elasticity, "
        "and recommends the revenue-maximising price for each product."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ── Request / Response schemas ────────────────────────────────────────────────

class OptimizeRequest(BaseModel):
    product_id: str = Field(
        ...,
        examples=["P001"],
        description="Product identifier (case-insensitive).",
    )
    current_price: float = Field(
        ...,
        gt=0,
        examples=[150.0],
        description="Current selling price. Must be greater than zero.",
    )
    price_range_pct: Optional[float] = Field(
        default=0.30,
        ge=0.05,
        le=0.80,
        description="Search radius as a fraction of current price (0.05 – 0.80).",
    )

    @field_validator("product_id")
    @classmethod
    def normalise_product_id(cls, v: str) -> str:
        return v.strip().upper()


class OptimizeResponse(BaseModel):
    product_id: str
    current_price: float
    optimal_price: float
    current_revenue: float
    optimal_revenue: float
    expected_revenue_increase: float = Field(
        ..., description="Expected revenue improvement in percentage points."
    )
    elasticity: float
    interpretation: str


class ProductInfo(BaseModel):
    product_id: str
    category: str
    elasticity: float
    r_squared: float
    p_value_str: str = Field(..., description="Human-readable significance (e.g. '< 0.0001')")
    avg_price: float
    avg_quantity: float
    n_observations: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"], summary="Health check")
def health_check():
    """
    Returns HTTP 200 when the API is running and all models are loaded.
    Use this as a liveness/readiness probe.
    """
    models_loaded = len(app_state.get("models", {}))
    return {
        "status":        "healthy" if models_loaded > 0 else "degraded",
        "models_loaded": models_loaded,
        "version":       "1.0.0",
    }


@app.get(
    "/products",
    response_model=List[ProductInfo],
    tags=["Products"],
    summary="List all products with elasticity metadata",
)
def list_products():
    """
    Returns all products with their estimated price elasticity,
    model fit statistics, and historical averages.
    """
    elasticity_df = app_state.get("elasticity_df")
    if elasticity_df is None:
        raise HTTPException(status_code=503, detail="Models not yet initialised.")

    cols = ["product_id", "category", "elasticity", "r_squared",
            "p_value_str", "avg_price", "avg_quantity", "n_observations"]
    return elasticity_df[cols].to_dict(orient="records")


@app.post(
    "/optimize-price",
    response_model=OptimizeResponse,
    tags=["Optimisation"],
    summary="Recommend an optimal price for a product",
)
def optimize_price(request: OptimizeRequest):
    """
    Given a product and its current price, returns the price that is
    expected to maximise revenue within ±price_range_pct of the current price.

    The engine:
    1. Retrieves the pre-built demand model (fitted from historical data).
    2. Simulates revenue across 200 candidate prices in the search range.
    3. Returns the candidate with the highest predicted revenue.
    """
    models = app_state.get("models", {})

    if request.product_id not in models:
        available = sorted(models.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Product '{request.product_id}' not found. Available IDs: {available}",
        )

    model  = models[request.product_id]
    result = optimize_price_for_product(
        model=model,
        current_price=request.current_price,
        price_range_pct=request.price_range_pct,
    )

    # Human-readable interpretation
    ε          = result["elasticity"]
    rev_change = result["expected_revenue_increase_pct"]
    sensitivity = (
        "elastic (highly price-sensitive)"   if abs(ε) > 1
        else "unit elastic"                  if abs(ε) == 1
        else "inelastic (price-insensitive)"
    )
    direction = "increase" if result["optimal_price"] > request.current_price else "decrease"
    interpretation = (
        f"Demand is {sensitivity} (ε = {ε:.2f}). "
        f"A price {direction} to ${result['optimal_price']:.2f} is projected to "
        f"{'improve' if rev_change >= 0 else 'change'} weekly revenue by {abs(rev_change):.1f}%."
    )

    return OptimizeResponse(
        product_id=result["product_id"],
        current_price=result["current_price"],
        optimal_price=result["optimal_price"],
        current_revenue=result["current_revenue"],
        optimal_revenue=result["optimal_revenue"],
        expected_revenue_increase=result["expected_revenue_increase_pct"],
        elasticity=result["elasticity"],
        interpretation=interpretation,
    )


@app.get(
    "/revenue-curve/{product_id}",
    tags=["Analysis"],
    summary="Revenue curve data for a given product and price range",
)
def get_revenue_curve(
    product_id: str,
    current_price: float = Query(..., gt=0, description="Reference price point."),
    range_pct: float     = Query(0.30, ge=0.05, le=0.80, description="Price range radius."),
):
    """
    Returns the predicted demand and revenue at 100 price points within
    [current_price × (1 - range_pct), current_price × (1 + range_pct)].

    Suitable for rendering a revenue curve in a frontend dashboard.
    """
    pid    = product_id.strip().upper()
    models = app_state.get("models", {})

    if pid not in models:
        raise HTTPException(status_code=404, detail=f"Product '{pid}' not found.")

    model     = models[pid]
    price_min = current_price * (1.0 - range_pct)
    price_max = current_price * (1.0 + range_pct)
    curve     = model.revenue_curve(price_min, price_max, n_points=100)

    return {
        "product_id": pid,
        "price_range": {"min": round(price_min, 2), "max": round(price_max, 2)},
        "data": curve.round(4).to_dict(orient="records"),
    }
