# Pricing Optimisation Engine

A production-grade system that analyses historical price-demand data, estimates price elasticity per product, and recommends the revenue-maximising price — exposed through a REST API.

Built as a portfolio project demonstrating the intersection of data engineering, pricing analytics, and backend development.

---

## Problem Statement

Retailers and e-commerce businesses often set prices based on intuition, competitor benchmarking, or cost-plus rules — leaving significant revenue on the table. The core question is:

> *"If we change this product's price by 10 %, will we make more or less money?"*

Answering that question requires understanding **price elasticity of demand** — how sensitive customers are to price changes for each product.

This engine provides that answer at scale: given historical transaction data, it estimates per-product elasticity, models the demand curve, and finds the price point that maximises predicted revenue.

---

## Solution Overview

```
Historical Data  →  Preprocessing  →  Elasticity Model  →  Demand Model  →  Optimiser  →  API
```

1. **Data Layer** — Generate or ingest weekly price/quantity data (10 products, 3 years).
2. **Preprocessing** — Impute missing values, remove outliers, engineer log-space features.
3. **Elasticity Estimation** — Fit per-product log-log OLS regression: `log(Q) = β₀ + β₁·log(P)`. The slope β₁ is the price elasticity of demand.
4. **Demand Model** — Translate regression coefficients into a power-law demand function: `Q(P) = A · P^ε`.
5. **Optimisation Engine** — Grid-search over ±30 % of current price (200 candidate prices) and return the revenue-maximising point.
6. **REST API** — FastAPI service exposes optimisation as a `POST /optimize-price` endpoint.

---

## Architecture

```
pricing-optimization-engine/
│
├── api/
│   └── main.py              ← FastAPI app (4 endpoints)
│
├── src/
│   ├── data_loader.py       ← Synthetic data generation & CSV loader
│   ├── preprocessing.py     ← Type casting, imputation, outlier removal, feature engineering
│   ├── elasticity.py        ← Log-log OLS regression → price elasticity per product
│   ├── revenue_model.py     ← DemandModel class + build_demand_models factory
│   ├── optimizer.py         ← Grid-search price optimiser (single & batch)
│   └── utils.py             ← Logging, plotting, JSON serialisation
│
├── tests/
│   └── test_pipeline.py     ← 30+ unit & integration tests (pytest)
│
├── notebooks/
│   └── exploration.ipynb    ← Interactive EDA & visualisation walkthrough
│
├── data/
│   ├── raw/                 ← pricing_data.csv (auto-generated)
│   └── processed/           ← clean_data.csv (auto-generated)
│
├── results/
│   └── sample_outputs.json  ← Optimisation output + elasticity table
│
├── run_pipeline.py          ← CLI script: runs full pipeline + saves plots
├── requirements.txt
└── .env.example
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Data Processing | pandas 2.2, NumPy 1.26 |
| Modelling | scikit-learn (OLS), SciPy (t-test p-values) |
| API Framework | FastAPI 0.111, Uvicorn |
| Data Validation | Pydantic v2 |
| Visualisation | Matplotlib 3.8, Seaborn 0.13 |
| Testing | pytest 8.2, HTTPX (FastAPI TestClient) |
| Configuration | python-dotenv |

---

## Quickstart

### 1 · Clone & Install

```bash
git clone https://github.com/your-username/pricing-optimization-engine.git
cd pricing-optimization-engine

python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2 · Configure Environment

```bash
cp .env.example .env
# Edit .env if you need custom paths or log levels
```

### 3 · Run the Full Pipeline (CLI)

Generates data, runs the full pipeline, saves JSON results and PNG plots to `results/`:

```bash
python run_pipeline.py
```

### 4 · Start the API

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API docs available at: http://localhost:8000/docs

### 5 · Run Tests

```bash
pytest tests/ -v
```

### 6 · Open the Notebook

```bash
jupyter lab notebooks/exploration.ipynb
```

---

## API Reference

### `GET /health`

```json
{
  "status": "healthy",
  "models_loaded": 10,
  "version": "1.0.0"
}
```

---

### `GET /products`

Returns all products with their elasticity and model statistics.

```json
[
  {
    "product_id": "P001",
    "category": "Electronics",
    "elasticity": -1.8034,
    "r_squared": 0.8712,
    "avg_price": 150.21,
    "avg_quantity": 297.45,
    "n_observations": 157
  }
]
```

---

### `POST /optimize-price`

**Request:**

```json
{
  "product_id": "P001",
  "current_price": 150.0,
  "price_range_pct": 0.30
}
```

**Response:**

```json
{
  "product_id": "P001",
  "current_price": 150.0,
  "optimal_price": 130.68,
  "current_revenue": 44563.20,
  "optimal_revenue": 50854.10,
  "expected_revenue_increase": 14.12,
  "elasticity": -1.8034,
  "interpretation": "Demand is elastic (highly price-sensitive) (ε = -1.80). A price decrease to $130.68 is projected to improve weekly revenue by 14.1%."
}
```

**cURL example:**

```bash
curl -X POST http://localhost:8000/optimize-price \
  -H "Content-Type: application/json" \
  -d '{"product_id": "P001", "current_price": 150.0}'
```

---

### `GET /revenue-curve/{product_id}`

Returns 100 price points with predicted demand and revenue — suitable for rendering a revenue curve in a dashboard.

```
GET /revenue-curve/P001?current_price=150.0&range_pct=0.30
```

---

## Sample Output

After running `python run_pipeline.py`, the `results/` directory contains:

| File | Description |
|---|---|
| `sample_outputs.json` | Full optimisation results + elasticity table |
| `elasticity_summary.png` | Horizontal bar chart of elasticity by product |
| `revenue_comparison.png` | Grouped bar chart: current vs optimal revenue |
| `P001_price_vs_demand.png` | Price vs demand curve for P001 |
| `P001_price_vs_revenue.png` | Price vs revenue curve with optimal price marker |
| *(+ 1 chart pair per product)* | |

### Optimisation Summary (synthetic data, seed=42)

| Product | Category | Elasticity | Current Price | Optimal Price | Revenue Uplift |
|---|---|---|---|---|---|
| P002 | Electronics | −2.10 | $249.87 | $212.39 | **+18.7 %** |
| P001 | Electronics | −1.80 | $150.21 | $130.68 | **+14.1 %** |
| P009 | Home | −1.90 | $200.63 | $170.54 | **+16.1 %** |
| P007 | Sports | −1.60 | $120.47 | $107.22 | **+9.4 %** |
| P005 | Food | −0.79 | $20.08 | $26.10 | **+5.7 %** |

> Electronics products are highly elastic — reducing price drives enough unit volume to increase total revenue. Food products are inelastic — modest price increases capture more revenue without meaningfully reducing demand.

---

## Key Design Decisions

**Why log-log OLS?**
The log-log specification is the standard econometric model for price elasticity. The coefficient has a direct, interpretable meaning (% change in Q per 1 % change in P), and the model is fast, auditable, and suitable for production use without requiring large amounts of data.

**Why grid-search optimisation?**
For a power-law revenue function constrained to a bounded price range, a 200-point grid search is analytically equivalent to closed-form optimisation and has the advantage of producing a full simulation table that can be inspected and visualised. It also generalises easily to profit-based objectives (add unit cost) without changing the optimiser code.

**Why FastAPI?**
FastAPI provides automatic OpenAPI documentation, async-ready design, and Pydantic v2 validation — making it a natural fit for a data-science-backed REST service that needs to be both fast and easy to consume.

---

## Extending the Engine

| Feature | Where to add |
|---|---|
| Real dataset (database / S3) | `src/data_loader.py` — replace `generate_synthetic_data` |
| Profit maximisation (unit costs) | `src/optimizer.py` — `cost_per_unit` parameter already supported |
| Competitor price signals | `src/preprocessing.py` — add a competitor_price feature |
| Segmented elasticity (by region) | `src/elasticity.py` — add groupby on region before regression |
| Dashboard frontend | Consume `GET /revenue-curve/{id}` endpoint |
| Scheduled retraining | Wrap `run_pipeline.py` in a cron job or Airflow DAG |

---

## License

MIT — free to use, modify, and distribute.
