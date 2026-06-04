"""SQLAlchemy-Modelle für Zeitreihen und Historie."""

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


class Base(DeclarativeBase):
    pass


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
    output_dir: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
