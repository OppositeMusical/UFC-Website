from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import Base


class MarketPrediction(Base):
    """A priced market (method of victory, method-in-round, round reached).

    Deliberately a separate table from `Prediction` rather than nullable
    columns bolted onto it. A stat prop and a moneyline market answer
    different questions: one has a line and an over/under call, the other has
    a price and a probability. `Prediction.stat_category`, `line_value` and
    `direction_predicted` are all NOT NULL, and SQLite cannot relax a NOT NULL
    without rebuilding the table - so reusing it would have meant either a
    risky migration on every existing install, or storing a moneyline in a
    column named `line_value` and hoping nobody read it literally.

    A new table needs no migration at all: `Base.metadata.create_all()` runs
    at startup and creates whatever is missing.
    """

    __tablename__ = "market_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id"))
    platform: Mapped[str] = mapped_column(String(20), nullable=False)

    # fighter_a is the fighter the bet names ("A beats B by KO"). For a draw
    # or a round-reached market the bet is on the bout rather than on either
    # corner, but both fighters are still recorded - they are what the stats
    # were drawn from.
    fighter_a_id: Mapped[int] = mapped_column(ForeignKey("fighters.id"), nullable=False)
    fighter_b_id: Mapped[int] = mapped_column(ForeignKey("fighters.id"), nullable=False)

    market_type: Mapped[str] = mapped_column(String(30), nullable=False)
    victory_method: Mapped[str | None] = mapped_column(String(20))  # null for round_reached
    round_number: Mapped[int | None] = mapped_column(Integer)  # null for plain method
    question: Mapped[str] = mapped_column(Text, nullable=False)

    moneyline: Mapped[int] = mapped_column(Integer, nullable=False)
    model_probability_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    implied_probability_pct: Mapped[float] = mapped_column(Float, nullable=False)
    edge_pct: Mapped[float] = mapped_column(Float, nullable=False)
    verdict: Mapped[str] = mapped_column(String(20), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    fighter_a = relationship("Fighter", foreign_keys=[fighter_a_id])
    fighter_b = relationship("Fighter", foreign_keys=[fighter_b_id])
