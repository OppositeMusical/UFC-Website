from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id"))
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    fighter_a_id: Mapped[int] = mapped_column(ForeignKey("fighters.id"), nullable=False)
    fighter_b_id: Mapped[int] = mapped_column(ForeignKey("fighters.id"), nullable=False)
    stat_category: Mapped[str] = mapped_column(String(50), nullable=False)
    line_value: Mapped[float] = mapped_column(Float, nullable=False)
    direction_predicted: Mapped[str] = mapped_column(String(10), nullable=False)  # over | under
    confidence_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    fighter_a = relationship("Fighter", foreign_keys=[fighter_a_id])
    fighter_b = relationship("Fighter", foreign_keys=[fighter_b_id])
