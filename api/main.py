"""
api/main.py
-----------
FastAPI application for the Pricing Optimisation Engine — Full Stack v2.0

Endpoints
---------
GET  /health                           — Liveness / readiness check
GET  /stats                            — Aggregate portfolio statistics (dashboard KPIs)
GET  /products                         — List products with elasticity metadata
POST /optimize-price                   — Recommend an optimal price (auto-saved to DB)
GET  /revenue-curve/{product_id}       — Revenue curve data for a price range
GET  /history                          — List all optimisation runs from the DB
DELETE /history/{run_id}               — Delete a single history record
DELETE /history                        — Clear all history records
"""

import os
import sys
import logging
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

# ── Path setup ────────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils import setup_logging
from src.data_loader import generate_synthetic_data, load_data, save_data
from src.preprocessing import preprocess
from src.elasticity import compute_all_elasticities
from src.revenue_model import build_demand_models
from src.optimizer import optimize_price_for_product

from api.database import engine, get_db
from api.db_models import OptimizationRun, Base

setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

RAW_DATA_PATH       = os.path.join(PROJECT_ROOT, os.getenv("DATA_PATH", "data/raw/pricing_data.csv"))
PROCESSED_DATA_PATH = os.path.join(PROJECT_ROOT, os.getenv("PROCESSED_DATA_PATH", "data/processed/clean_data.csv"))

app_state: Dict = {}


# ── Startup / shutdown ────────────────────────────────────────────────────────

def _bootstrap_engine() -> None:
    if not os.path.exists(RAW_DATA_PATH):
        logger.info("Raw dataset not found — generating synthetic data…")
        raw_df = generate_synthetic_data()
        save_data(raw_df, RAW_DATA_PATH)
    else:
        raw_df = load_data(RAW_DATA_PATH)

    clean_df      = preprocess(raw_df)
    save_data(clean_df, PROCESSED_DATA_PATH)
    elasticity_df = compute_all_elasticities(clean_df)
    models        = build_demand_models(elasticity_df)

    app_state["models"]        = models
    app_state["elasticity_df"] = elasticity_df


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== Pricing Optimisation Engine v2.0 — starting up ===")
    Base.metadata.create_all(bind=engine)
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
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:4173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas ───────────────────────────────────────────────────────────────────

class OptimizeRequest(BaseModel):
    product_id: str = Field(..., examples=["P001"])
    current_price: float = Field(..., gt=0, examples=[150.0])
    price_range_pct: Optional[float] = Field(default=0.30, ge=0.05, le=0.80)
    cost_per_unit: Optional[float] = Field(default=None, gt=0)

    @field_validator("product_id")
    @classmethod
    def normalise_product_id(cls, v: str) -> str:
        return v.strip().upper()


class OptimizeResponse(BaseModel):
    run_id: int
    product_id: str
    category: str
    current_price: float
    optimal_price: float
    current_revenue: float
    optimal_revenue: float
    expected_revenue_increase: float
    elasticity: float
    interpretation: str


class ProductInfo(BaseModel):
    product_id: str
    category: str
    elasticity: float
    price_elasticity_category: str
    r_squared: float
    p_value_str: str
    avg_price: float
    avg_quantity: float
    n_observations: int
    current_price: float
    optimal_price: float
    current_revenue: float
    optimal_revenue: float
    expected_revenue_increase_pct: float


class HistoryRecord(BaseModel):
    id: int
    product_id: str
    category: Optional[str]
    current_price: float
    optimal_price: float
    current_revenue: float
    optimal_revenue: float
    expected_revenue_increase_pct: float
    price_range_pct: float
    cost_per_unit: Optional[float]
    elasticity: float
    interpretation: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health_check():
    models_loaded = len(app_state.get("models", {}))
    return {"status": "healthy" if models_loaded > 0 else "degraded",
            "models_loaded": models_loaded, "version": "2.0.0"}


@app.get("/stats", tags=["System"])
def get_stats():
    edf    = app_state.get("elasticity_df")
    models = app_state.get("models", {})
    if edf is None:
        raise HTTPException(status_code=503, detail="Models not yet initialised.")

    from src.optimizer import run_batch_optimization
    results = run_batch_optimization(models, edf, price_range_pct=0.30)

    total_current = float(results["current_revenue"].sum())
    total_optimal = float(results["optimal_revenue"].sum())
    uplift_pct    = (total_optimal / total_current - 1.0) * 100

    most_elastic_row    = edf.loc[edf["elasticity"].idxmin()]
    most_inelastic_row  = edf.loc[edf["elasticity"].idxmax()]

    def _row_summary(row):
        return {
            "product_id": row["product_id"],
            "elasticity": round(float(row["elasticity"]), 4),
            "category":   row.get("category", ""),
        }

    return {
        "total_products":            len(models),
        "avg_elasticity":            round(float(edf["elasticity"].mean()), 4),
        "elastic_products":          int((edf["elasticity"] < -1).sum()),
        "inelastic_products":        int((edf["elasticity"] >= -1).sum()),
        "portfolio_current_revenue": round(total_current, 2),
        "portfolio_optimal_revenue": round(total_optimal, 2),
        "portfolio_uplift_pct":      round(uplift_pct, 2),
        "most_elastic":   _row_summary(most_elastic_row),
        "most_inelastic": _row_summary(most_inelastic_row),
    }


@app.get("/products", response_model=List[ProductInfo], tags=["Products"])
def list_products():
    elasticity_df = app_state.get("elasticity_df")
    models        = app_state.get("models", {})
    if elasticity_df is None:
        raise HTTPException(status_code=503, detail="Models not yet initialised.")

    from src.optimizer import run_batch_optimization
    results = run_batch_optimization(models, elasticity_df, price_range_pct=0.30)
    # results columns include: product_id, current_price, optimal_price,
    #                           current_revenue, optimal_revenue, expected_revenue_increase_pct

    edf = elasticity_df.copy()
    if "price_elasticity_category" not in edf.columns:
        edf["price_elasticity_category"] = edf["elasticity"].apply(
            lambda e: "Elastic" if e < -1 else "Inelastic"
        )

    merge_cols = ["product_id", "current_price", "optimal_price",
                  "current_revenue", "optimal_revenue", "expected_revenue_increase_pct"]
    available  = [c for c in merge_cols if c in results.columns]
    merged = edf.merge(results[available], on="product_id", how="left")

    cols = [
        "product_id", "category", "elasticity", "price_elasticity_category",
        "r_squared", "p_value_str", "avg_price", "avg_quantity", "n_observations",
        "current_price", "optimal_price", "current_revenue", "optimal_revenue",
        "expected_revenue_increase_pct",
    ]
    cols = [c for c in cols if c in merged.columns]
    return merged[cols].fillna(0).to_dict(orient="records")


@app.post("/optimize-price", response_model=OptimizeResponse, tags=["Optimisation"])
def optimize_price(request: OptimizeRequest, db: Session = Depends(get_db)):
    models        = app_state.get("models", {})
    elasticity_df = app_state.get("elasticity_df")

    if request.product_id not in models:
        raise HTTPException(
            status_code=404,
            detail=f"Product '{request.product_id}' not found. Available IDs: {sorted(models.keys())}",
        )

    model  = models[request.product_id]
    result = optimize_price_for_product(
        model=model,
        current_price=request.current_price,
        price_range_pct=request.price_range_pct,
        cost_per_unit=request.cost_per_unit,
    )

    category = ""
    if elasticity_df is not None:
        row = elasticity_df[elasticity_df["product_id"] == request.product_id]
        if not row.empty:
            category = str(row.iloc[0]["category"])

    ε          = result["elasticity"]
    rev_change = result["expected_revenue_increase_pct"]
    sensitivity = (
        "elastic (highly price-sensitive)" if abs(ε) > 1
        else "unit elastic"                if abs(ε) == 1
        else "inelastic (price-insensitive)"
    )
    direction = "increase" if result["optimal_price"] > request.current_price else "decrease"
    interpretation = (
        f"Demand is {sensitivity} (ε = {ε:.2f}). "
        f"A price {direction} to ${result['optimal_price']:.2f} is projected to "
        f"{'improve' if rev_change >= 0 else 'change'} weekly revenue by {abs(rev_change):.1f}%."
    )

    run = OptimizationRun(
        product_id                    = result["product_id"],
        category                      = category,
        current_price                 = result["current_price"],
        optimal_price                 = result["optimal_price"],
        current_revenue               = result["current_revenue"],
        optimal_revenue               = result["optimal_revenue"],
        expected_revenue_increase_pct = rev_change,
        price_range_pct               = request.price_range_pct,
        cost_per_unit                 = request.cost_per_unit,
        elasticity                    = ε,
        interpretation                = interpretation,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    return OptimizeResponse(
        run_id=run.id, product_id=result["product_id"], category=category,
        current_price=result["current_price"], optimal_price=result["optimal_price"],
        current_revenue=result["current_revenue"], optimal_revenue=result["optimal_revenue"],
        expected_revenue_increase=rev_change, elasticity=ε, interpretation=interpretation,
    )


@app.get("/revenue-curve/{product_id}", tags=["Analysis"])
def get_revenue_curve(
    product_id: str,
    current_price: float = Query(..., gt=0),
    range_pct: float     = Query(0.30, ge=0.05, le=0.80),
):
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


@app.get("/history", response_model=List[HistoryRecord], tags=["History"])
def get_history(
    limit: int = Query(100, ge=1, le=500),
    product_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(OptimizationRun).order_by(OptimizationRun.created_at.desc())
    if product_id:
        q = q.filter(OptimizationRun.product_id == product_id.strip().upper())
    runs = q.limit(limit).all()
    return [
        HistoryRecord(
            id=r.id, product_id=r.product_id, category=r.category,
            current_price=r.current_price, optimal_price=r.optimal_price,
            current_revenue=r.current_revenue, optimal_revenue=r.optimal_revenue,
            expected_revenue_increase_pct=r.expected_revenue_increase_pct,
            price_range_pct=r.price_range_pct, cost_per_unit=r.cost_per_unit,
            elasticity=r.elasticity, interpretation=r.interpretation,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in runs
    ]


@app.delete("/history/{run_id}", tags=["History"])
def delete_history_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(OptimizationRun).filter(OptimizationRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    db.delete(run)
    db.commit()
    return {"deleted": run_id}


@app.delete("/history", tags=["History"])
def clear_history(db: Session = Depends(get_db)):
    count = db.query(OptimizationRun).count()
    db.query(OptimizationRun).delete()
    db.commit()
    return {"deleted_count": count}
