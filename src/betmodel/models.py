from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String, unique=True, index=True)


class Fixture(Base):
    __tablename__ = "fixtures"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String, index=True)
    provider_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    competition: Mapped[str] = mapped_column(String, index=True)
    season: Mapped[str] = mapped_column(String)
    kickoff: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    match_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    home_team: Mapped[str] = mapped_column(String, index=True)
    away_team: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="SCHEDULED")
    __table_args__ = (UniqueConstraint("source", "provider_id", name="uq_fixture_provider"),)


class TeamMatchStat(Base):
    __tablename__ = "team_match_stats"
    id: Mapped[int] = mapped_column(primary_key=True)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.id"), index=True)
    team_name: Mapped[str] = mapped_column(String, index=True)
    is_home: Mapped[int] = mapped_column(Integer)
    goals: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    shots: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    shots_on_target: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    corners: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cards: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.id"), index=True)
    source: Mapped[str] = mapped_column(String)
    bookmaker: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    market_key: Mapped[str] = mapped_column(String, index=True)
    selection: Mapped[str] = mapped_column(String)
    line: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    decimal_odds: Mapped[float] = mapped_column(Float)
    source_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    received_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProviderMapping(Base):
    __tablename__ = "provider_mappings"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String)
    entity_type: Mapped[str] = mapped_column(String)
    provider_key: Mapped[str] = mapped_column(String)
    canonical_key: Mapped[str] = mapped_column(String)
    __table_args__ = (UniqueConstraint("source", "entity_type", "provider_key", name="uq_provider_mapping"),)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    model_name: Mapped[str] = mapped_column(String, index=True)
    version: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.id"), index=True)
    model_version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("model_versions.id"), nullable=True)
    market_key: Mapped[str] = mapped_column(String)
    selection: Mapped[str] = mapped_column(String)
    probability: Mapped[float] = mapped_column(Float)
    lower_bound: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    upper_bound: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    feature_cutoff: Mapped[datetime] = mapped_column(DateTime)


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    target_label: Mapped[str] = mapped_column(String)
    total_odds: Mapped[float] = mapped_column(Float)
    joint_probability: Mapped[float] = mapped_column(Float)
    expected_value: Mapped[float] = mapped_column(Float)
    quality_grade: Mapped[str] = mapped_column(String)


class RecommendationLeg(Base):
    __tablename__ = "recommendation_legs"
    id: Mapped[int] = mapped_column(primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(ForeignKey("recommendations.id"), index=True)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.id"), index=True)
    market_key: Mapped[str] = mapped_column(String)
    selection: Mapped[str] = mapped_column(String)
    decimal_odds: Mapped[float] = mapped_column(Float)
    model_probability: Mapped[float] = mapped_column(Float)
