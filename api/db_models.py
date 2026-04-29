"""
api/db_models.py
----------------
SQLAlchemy ORM models for persisting optimisation history.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from api.database import Base


class OptimizationRun(Base):
    __tablename__ = "optimization_runs"

    id                           = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id                   = Column(String, nullable=False, index=True)
    category                     = Column(String, nullable=True)
    current_price                = Column(Float, nullable=False)
    optimal_price                = Column(Float, nullable=False)
    current_revenue              = Column(Float, nullable=False)
    optimal_revenue              = Column(Float, nullable=False)
    expected_revenue_increase_pct = Column(Float, nullable=False)
    price_range_pct              = Column(Float, nullable=False)
    cost_per_unit                = Column(Float, nullable=True)
    elasticity                   = Column(Float, nullable=False)
    interpretation               = Column(String, nullable=True)
    created_at                   = Column(DateTime(timezone=True), server_default=func.now())
