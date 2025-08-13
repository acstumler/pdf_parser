# models.py
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Boolean, DateTime,
    ForeignKey, Text, JSON, UniqueConstraint, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# -----------------------------------------------------------------------------
# Engine / Session
# -----------------------------------------------------------------------------
# Use Postgres in prod via: DATABASE_URL=postgresql+psycopg2://user:pass@host/db
# Falls back to local SQLite for dev.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./lumiledger.db")

# echo=True for SQL debugging locally if you want to see SQL queries
engine = create_engine(DATABASE_URL, echo=False, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()

# -----------------------------------------------------------------------------
# Helper: “big app” style tenant isolation
# - Every table that stores user data includes user_id and is indexed by it.
# - user_id should be your auth subject (e.g., Firebase uid).
# -----------------------------------------------------------------------------

class User(Base):
    """
    Represents an authenticated tenant (end-user).
    user_id is expected to be a stable ID from your auth provider (e.g., Firebase uid).
    """
    __tablename__ = "users"

    id = Column(String, primary_key=True)  # e.g., Firebase uid
    email = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships (optional)
    rules = relationship("VendorRule", back_populates="user", cascade="all, delete-orphan")
    memories = relationship("ClassificationMemory", back_populates="user", cascade="all, delete-orphan")
    events = relationship("ClassificationEvent", back_populates="user", cascade="all, delete-orphan")


class ChartOfAccount(Base):
    """
    Your canonical chart of accounts. Populate from LumiLedger Chart of Accounts.xlsx.
    Keep this global, not per-user, so all users share the canonical codes and names.
    """
    __tablename__ = "chart_of_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False)            # e.g. "6100"
    name = Column(String, nullable=False)            # e.g. "Meals & Entertainment"
    type = Column(String, nullable=True)             # e.g. "Expense"
    parent_code = Column(String, nullable=True)      # optional hierarchy support
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("code", name="uq_chart_of_accounts_code"),
        Index("ix_chart_of_accounts_code", "code"),
    )


class VendorRule(Base):
    """
    Deterministic rules (system or curated) that map a normalized vendor to an account code.
    No regex or keyword heuristics here. Keep it strict and predictable.
    """
    __tablename__ = "vendor_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)  # tenant scope
    vendor_normalized = Column(String, nullable=False)  # pre-normalized merchant string
    account_code = Column(String, nullable=False)       # must exist in ChartOfAccount.code
    source = Column(String, nullable=False, default="system")  # "system" | "user"
    confidence = Column(Float, nullable=False, default=1.0)    # deterministic -> 1.0
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="rules")

    __table_args__ = (
        # A user should not have duplicate rules for the same normalized vendor
        UniqueConstraint("user_id", "vendor_normalized", name="uq_vendor_rules_user_vendor"),
        Index("ix_vendor_rules_user_vendor", "user_id", "vendor_normalized"),
        Index("ix_vendor_rules_user_account", "user_id", "account_code"),
    )


class ClassificationMemory(Base):
    """
    Learned memory from user corrections/accepts. Higher precedence than AI, lower than strict VendorRule.
    One row per (user, vendor_normalized) with the best-known mapping.
    """
    __tablename__ = "classification_memory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    vendor_normalized = Column(String, nullable=False)
    account_code = Column(String, nullable=False)
    confidence = Column(Float, nullable=False, default=0.9)  # adaptive
    source = Column(String, nullable=False, default="user")  # "user" | "ai"
    hits = Column(Integer, nullable=False, default=0)        # how many times we used it
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="memories")

    __table_args__ = (
        UniqueConstraint("user_id", "vendor_normalized", name="uq_memory_user_vendor"),
        Index("ix_memory_user_vendor", "user_id", "vendor_normalized"),
        Index("ix_memory_user_account", "user_id", "account_code"),
    )


class ClassificationEvent(Base):
    """
    Full audit log of classification attempts and outcomes.
    Use this to prove data lineage, improve the model, and restore user trust.
    """
    __tablename__ = "classification_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Raw transaction inputs (do not store sensitive PII beyond what you need)
    raw_description = Column(Text, nullable=False)
    amount = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    tx_date = Column(String, nullable=True)  # store as ISO date string or use Date

    # Classifier outputs
    suggested_account_code = Column(String, nullable=True)
    final_account_code = Column(String, nullable=True)  # after overrides/memory/user edits
    chosen_by = Column(String, nullable=True)  # "rules" | "memory" | "ai" | "user_override"
    confidence = Column(Float, nullable=True)

    # Versioning / explainability
    rules_version = Column(String, nullable=True)   # e.g., version tag from your XLS import
    model_version = Column(String, nullable=True)   # e.g., "llm-2025-08-01"
    trace = Column(JSON, nullable=True)             # structured step-by-step reasoning (safe to store)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="events")

    __table_args__ = (
        Index("ix_events_user_created", "user_id", "created_at"),
    )


# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------
def init_db() -> None:
    """
    Create tables if they don't exist. Call this once at startup.
    For production, prefer proper migrations (e.g., Alembic).
    """
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    FastAPI dependency helper:

        from fastapi import Depends
        from models import get_db

        @app.get("/something")
        def endpoint(db = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
