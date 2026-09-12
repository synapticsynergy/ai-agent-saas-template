"""Reference-application domain model: saved evening plans."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin, new_id

if TYPE_CHECKING:  # pragma: no cover
    pass

PLAN_STATUSES = ("draft", "saved", "archived")
STOP_CATEGORIES = ("dinner", "music", "drinks", "activity", "dessert", "coffee")


class Plan(Base, TenantMixin, TimestampMixin):
    __tablename__ = "plans"
    __table_args__ = (Index("ix_plans_org_created", "organization_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")

    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estimated_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    estimated_walk_distance_km: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Correlates a saved plan with the agent run that produced it, so a support
    # question about "why did it pick that bar" is answerable from a trace.
    agent_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    stops: Mapped[list[PlanStop]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="PlanStop.position",
        lazy="selectin",
    )


class PlanStop(Base, TimestampMixin):
    __tablename__ = "plan_stops"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")

    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)

    plan: Mapped[Plan] = relationship(back_populates="stops")


class UserPreference(Base, TenantMixin, TimestampMixin):
    __tablename__ = "user_preferences"
    __table_args__ = (
        Index("uq_user_preferences_org_user", "organization_id", "user_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)

    default_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_walk_distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    dietary_notes: Mapped[str | None] = mapped_column(String(300), nullable=True)
    preferred_categories: Mapped[str | None] = mapped_column(String(300), nullable=True)
