"""SQLAlchemy-Modelle fuer Zeitreihen und Historie."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

EntityType = str  # 'series' | 'correlation' | 'tsa'


class Base(DeclarativeBase):
    pass


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TimeSeries(Base):
    __tablename__ = "time_series"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    source_file: Mapped[str | None] = mapped_column(String(512))
    value_column: Mapped[str | None] = mapped_column(String(64))
    date_column: Mapped[str | None] = mapped_column(String(64))
    first_date: Mapped[date | None] = mapped_column(Date)
    last_date: Mapped[date | None] = mapped_column(Date)
    observation_count: Mapped[int] = mapped_column(default=0)
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    observations: Mapped[list[Observation]] = relationship(
        back_populates="series", cascade="all, delete-orphan"
    )


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint("series_id", "obs_date", name="uq_observations_series_date"),
        Index("ix_observations_series_date", "series_id", "obs_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("time_series.id"), nullable=False)
    obs_date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)

    series: Mapped[TimeSeries] = relationship(back_populates="observations")


class UploadHistory(Base):
    __tablename__ = "upload_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    series_id: Mapped[int | None] = mapped_column(ForeignKey("time_series.id"))
    rows_imported: Mapped[int] = mapped_column(default=0)
    note: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CorrelationHistory(Base):
    __tablename__ = "correlation_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    series_a_slug: Mapped[str] = mapped_column(String(120), nullable=False)
    series_b_slug: Mapped[str] = mapped_column(String(120), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    max_lag: Mapped[int] = mapped_column(default=0)
    aligned_observations: Mapped[int] = mapped_column(default=0)
    best_lag: Mapped[int | None] = mapped_column()
    best_correlation: Mapped[float | None] = mapped_column(Float)
    analysis_mode: Mapped[str | None] = mapped_column(String(32))
    run_name: Mapped[str | None] = mapped_column(String(256))
    output_dir: Mapped[str | None] = mapped_column(String(1024))
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TsaHistory(Base):
    __tablename__ = "tsa_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    series_slug: Mapped[str] = mapped_column(String(120), nullable=False)
    analysis_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="thesis")
    models: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    train_start: Mapped[date | None] = mapped_column(Date)
    train_end: Mapped[date | None] = mapped_column(Date)
    forecast_end: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="fertig")
    output_dir: Mapped[str | None] = mapped_column(String(1024))
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    forecast_values: Mapped[list[TsaForecastValue]] = relationship(
        back_populates="tsa_history", cascade="all, delete-orphan"
    )


class TsaForecastValue(Base):
    """Prognose- und Quantilwerte eines TSA-Laufs (Niveau)."""

    __tablename__ = "tsa_forecast_values"
    __table_args__ = (
        Index("ix_tsa_forecast_history", "tsa_history_id"),
        Index("ix_tsa_forecast_lookup", "tsa_history_id", "model", "obs_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tsa_history_id: Mapped[int] = mapped_column(ForeignKey("tsa_history.id"), nullable=False)
    model: Mapped[str] = mapped_column(String(32), nullable=False)
    obs_date: Mapped[date] = mapped_column(Date, nullable=False)
    field: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)

    tsa_history: Mapped[TsaHistory] = relationship(back_populates="forecast_values")


class EntityTagLink(Base):
    """n:m Zuordnung Tags zu Serie, Korrelation oder TSA-Lauf."""

    __tablename__ = "entity_tag_links"
    __table_args__ = (
        UniqueConstraint(
            "entity_type", "entity_id", "tag_id", name="uq_entity_tag_links"
        ),
        Index("ix_entity_tag_links_tag", "tag_id"),
        Index("ix_entity_tag_links_entity", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[int] = mapped_column(nullable=False)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tag: Mapped[Tag] = relationship()
