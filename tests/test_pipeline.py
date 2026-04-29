"""
tests/test_pipeline.py
----------------------
Unit and integration tests for the Pricing Optimisation Engine.

Run from the project root:
    pytest tests/ -v

Coverage scope:
  - Data generation          (TestDataGeneration)
  - Preprocessing            (TestPreprocessing)
  - Elasticity estimation    (TestElasticity)
  - Demand / revenue model   (TestDemandModel)
  - Price optimiser          (TestOptimizer)
  - Full end-to-end pipeline (TestEndToEndPipeline)
  - FastAPI endpoints        (TestAPI)
"""

import os
import sys
import pytest
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

# ── Path setup ────────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.data_loader    import generate_synthetic_data
from src.preprocessing  import (
    preprocess, cast_types, handle_missing_values,
    remove_outliers_iqr, engineer_features,
)
from src.elasticity     import compute_all_elasticities, compute_elasticity_for_product
from src.revenue_model  import DemandModel, build_demand_models
from src.optimizer      import optimize_price_for_product, run_batch_optimization


# ── Module-scoped fixtures (computed once per test session) ───────────────────

@pytest.fixture(scope="module")
def raw_data():
    return generate_synthetic_data(seed=42)


@pytest.fixture(scope="module")
def clean_data(raw_data):
    return preprocess(raw_data)


@pytest.fixture(scope="module")
def elasticity_df(clean_data):
    return compute_all_elasticities(clean_data)


@pytest.fixture(scope="module")
def demand_models(elasticity_df):
    return build_demand_models(elasticity_df)


# ── 1. Data Generation ────────────────────────────────────────────────────────

class TestDataGeneration:

    def test_schema_columns_present(self, raw_data):
        required = {"product_id", "category", "date", "price", "quantity_sold"}
        assert required.issubset(set(raw_data.columns))

    def test_ten_distinct_products(self, raw_data):
        assert raw_data["product_id"].nunique() == 10

    def test_all_prices_positive(self, raw_data):
        assert (raw_data["price"] > 0).all()

    def test_all_quantities_non_negative(self, raw_data):
        assert (raw_data["quantity_sold"] >= 0).all()

    def test_reproducibility_with_same_seed(self):
        df1 = generate_synthetic_data(seed=42)
        df2 = generate_synthetic_data(seed=42)
        pd.testing.assert_frame_equal(df1, df2)

    def test_different_seeds_produce_different_data(self):
        df1 = generate_synthetic_data(seed=1)
        df2 = generate_synthetic_data(seed=2)
        assert not df1["price"].equals(df2["price"])


# ── 2. Preprocessing ──────────────────────────────────────────────────────────

class TestPreprocessing:

    def test_log_features_created(self, clean_data):
        for col in ("log_price", "log_quantity", "revenue"):
            assert col in clean_data.columns, f"Missing column: {col}"

    def test_no_nulls_in_key_columns(self, clean_data):
        nulls = clean_data[["price", "quantity_sold", "log_price", "log_quantity"]].isnull().sum()
        assert nulls.sum() == 0, f"Found nulls: {nulls[nulls > 0]}"

    def test_all_prices_positive_after_preprocessing(self, clean_data):
        assert (clean_data["price"] > 0).all()

    def test_missing_value_imputation(self):
        df = pd.DataFrame({
            "product_id":    ["P001"] * 8,
            "category":      ["Electronics"] * 8,
            "date":          pd.date_range("2023-01-01", periods=8, freq="W"),
            "price":         [100, None, 110, 95, 105, 100, 98, 102],
            "quantity_sold": [200, 190, None, 210, 195, 200, 205, None],
        })
        result = handle_missing_values(df)
        assert result["price"].isnull().sum() == 0
        assert result["quantity_sold"].isnull().sum() == 0

    def test_outlier_removal_eliminates_extreme_value(self):
        df = pd.DataFrame({
            "product_id":    ["P001"] * 25,
            "price":         [100.0] * 24 + [99_999.0],
            "quantity_sold": [200] * 25,
        })
        result = remove_outliers_iqr(df, multiplier=1.5)
        assert len(result) < len(df), "Extreme outlier was not removed."

    def test_log_price_equals_numpy_log(self):
        df = pd.DataFrame({
            "product_id": ["P001"],
            "category":   ["Electronics"],
            "date":       pd.to_datetime(["2023-06-15"]),
            "price":      [100.0],
            "quantity_sold": [200],
        })
        result = engineer_features(df)
        assert np.isclose(result["log_price"].iloc[0],    np.log(100))
        assert np.isclose(result["log_quantity"].iloc[0], np.log(200))
        assert result["revenue"].iloc[0] == 100 * 200


# ── 3. Elasticity ─────────────────────────────────────────────────────────────

class TestElasticity:

    def test_elasticity_computed_for_all_products(self, clean_data, elasticity_df):
        n_products = clean_data["product_id"].nunique()
        assert len(elasticity_df) == n_products

    def test_elasticity_negative_for_all_products(self, elasticity_df):
        # Law of demand: higher price → lower quantity
        positive = elasticity_df[elasticity_df["elasticity"] >= 0]
        assert positive.empty, f"Positive elasticity detected:\n{positive}"

    def test_r_squared_above_threshold(self, elasticity_df):
        # Log-log model should explain a meaningful share of variance.
        # Inelastic / noisy products (e.g. Food) naturally have lower R²;
        # a threshold of 0.35 ensures the model is better than chance.
        low_r2 = elasticity_df[elasticity_df["r_squared"] < 0.35]
        assert low_r2.empty, f"Low R² products:\n{low_r2[['product_id', 'r_squared']]}"

    def test_p_value_str_never_bare_zero(self, elasticity_df):
        # p_value_str must never display as "0.0" — use "< 0.0001" for near-zero values
        bad = elasticity_df[elasticity_df["p_value_str"] == "0.0"]
        assert bad.empty, f"p_value_str shows bare '0.0' for: {bad['product_id'].tolist()}"

    def test_p_value_str_significance_all_products(self, elasticity_df):
        # All elasticity estimates should be statistically significant
        for _, row in elasticity_df.iterrows():
            assert row["p_value_str"] == "< 0.0001" or float(row["p_value_str"]) < 0.05, \
                f"{row['product_id']} has non-significant elasticity: p = {row['p_value_str']}"

    def test_required_columns_in_output(self, elasticity_df):
        required = {"product_id", "elasticity", "intercept", "r_squared",
                    "p_value", "p_value_str", "n_observations"}
        assert required.issubset(set(elasticity_df.columns))

    def test_skips_product_with_too_few_rows(self):
        tiny = pd.DataFrame({
            "product_id":    ["P999"] * 3,
            "category":      ["Test"] * 3,
            "log_price":     [4.6, 4.7, 4.8],
            "log_quantity":  [5.2, 5.1, 5.0],
            "price":         [100, 110, 121],
            "quantity_sold": [200, 180, 160],
        })
        result = compute_elasticity_for_product(tiny)
        assert result is None


# ── 4. Demand Model ───────────────────────────────────────────────────────────

class TestDemandModel:

    def test_demand_decreases_with_price(self, demand_models):
        model = demand_models["P001"]
        assert model.predict_demand(50) > model.predict_demand(200)

    def test_revenue_equals_price_times_demand(self, demand_models):
        model = demand_models["P001"]
        price = 100.0
        assert np.isclose(model.predict_revenue(price), price * model.predict_demand(price))

    def test_negative_price_raises_value_error(self, demand_models):
        with pytest.raises(ValueError):
            demand_models["P001"].predict_demand(-10)

    def test_zero_price_raises_value_error(self, demand_models):
        with pytest.raises(ValueError):
            demand_models["P001"].predict_demand(0)

    def test_revenue_curve_shape(self, demand_models):
        curve = demand_models["P001"].revenue_curve(50, 200, n_points=50)
        assert len(curve) == 50
        assert set(curve.columns) == {"price", "predicted_demand", "predicted_revenue"}

    def test_revenue_curve_invalid_range_raises(self, demand_models):
        with pytest.raises(ValueError):
            demand_models["P001"].revenue_curve(200, 50)  # min > max


# ── 5. Optimiser ──────────────────────────────────────────────────────────────

class TestOptimizer:

    def test_optimal_price_within_search_range(self, demand_models):
        model = demand_models["P001"]
        current = 150.0
        result  = optimize_price_for_product(model, current, price_range_pct=0.30)
        assert current * 0.70 <= result["optimal_price"] <= current * 1.30

    def test_optimal_revenue_gte_current_revenue(self, demand_models):
        result = optimize_price_for_product(demand_models["P001"], 150.0)
        assert result["optimal_revenue"] >= result["current_revenue"]

    def test_result_contains_required_keys(self, demand_models):
        result   = optimize_price_for_product(demand_models["P001"], 150.0)
        required = {
            "product_id", "current_price", "optimal_price",
            "current_revenue", "optimal_revenue",
            "expected_revenue_increase_pct", "elasticity",
        }
        assert required.issubset(set(result.keys()))

    def test_simulation_dataframe_in_result(self, demand_models):
        result = optimize_price_for_product(demand_models["P001"], 150.0)
        assert isinstance(result["simulation"], pd.DataFrame)
        assert len(result["simulation"]) == 200

    def test_invalid_price_raises_value_error(self, demand_models):
        with pytest.raises(ValueError):
            optimize_price_for_product(demand_models["P001"], current_price=-50)

    def test_batch_returns_all_products(self, demand_models, elasticity_df):
        batch = run_batch_optimization(demand_models, elasticity_df)
        assert len(batch) == len(demand_models)

    def test_batch_no_negative_revenue_increase(self, demand_models, elasticity_df):
        batch = run_batch_optimization(demand_models, elasticity_df)
        assert (batch["expected_revenue_increase_pct"] >= 0).all()


# ── 6. End-to-end pipeline ────────────────────────────────────────────────────

class TestEndToEndPipeline:

    def test_full_pipeline_produces_valid_results(self):
        raw           = generate_synthetic_data(seed=99)
        clean         = preprocess(raw)
        elasticity_df = compute_all_elasticities(clean)
        models        = build_demand_models(elasticity_df)
        results       = run_batch_optimization(models, elasticity_df)

        assert len(results) > 0
        assert "optimal_price"                 in results.columns
        assert "expected_revenue_increase_pct" in results.columns
        assert (results["optimal_price"] > 0).all()

    def test_pipeline_deterministic_with_same_seed(self):
        def run(seed):
            raw  = generate_synthetic_data(seed=seed)
            df   = preprocess(raw)
            edf  = compute_all_elasticities(df)
            mdls = build_demand_models(edf)
            return run_batch_optimization(mdls, edf)

        r1 = run(7)
        r2 = run(7)
        pd.testing.assert_frame_equal(
            r1.drop(columns=["product_id"]).reset_index(drop=True),
            r2.drop(columns=["product_id"]).reset_index(drop=True),
        )


# ── 7. FastAPI endpoints ──────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def api_client():
    from api.main import app
    with TestClient(app) as client:
        yield client


class TestAPI:

    def test_health_endpoint_returns_200(self, api_client):
        response = api_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_products_endpoint_returns_list(self, api_client):
        response = api_client.get("/products")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 10  # 10 synthetic products

    def test_products_have_required_fields(self, api_client):
        response = api_client.get("/products")
        product  = response.json()[0]
        for field in ("product_id", "category", "elasticity", "r_squared", "p_value_str"):
            assert field in product

    def test_optimize_price_known_product(self, api_client):
        response = api_client.post(
            "/optimize-price",
            json={"product_id": "P001", "current_price": 150.0},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["optimal_price"] > 0
        assert "elasticity" in body
        assert "interpretation" in body

    def test_optimize_price_case_insensitive(self, api_client):
        r1 = api_client.post("/optimize-price", json={"product_id": "p001", "current_price": 150.0})
        r2 = api_client.post("/optimize-price", json={"product_id": "P001", "current_price": 150.0})
        assert r1.status_code == 200
        assert r1.json()["optimal_price"] == r2.json()["optimal_price"]

    def test_optimize_price_unknown_product_returns_404(self, api_client):
        response = api_client.post(
            "/optimize-price",
            json={"product_id": "UNKNOWN", "current_price": 100.0},
        )
        assert response.status_code == 404

    def test_optimize_price_negative_price_returns_422(self, api_client):
        response = api_client.post(
            "/optimize-price",
            json={"product_id": "P001", "current_price": -50.0},
        )
        assert response.status_code == 422

    def test_revenue_curve_endpoint(self, api_client):
        response = api_client.get(
            "/revenue-curve/P001",
            params={"current_price": 150.0, "range_pct": 0.20},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["product_id"] == "P001"
        assert len(body["data"]) == 100
