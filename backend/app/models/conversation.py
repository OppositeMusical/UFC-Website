from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), default="New Chat")
    platform: Mapped[str | None] = mapped_column(String(20))  # prizepicks | draftkings | kalshi | None
    fighter_a_id: Mapped[int | None] = mapped_column(ForeignKey("fighters.id"))
    fighter_b_id: Mapped[int | None] = mapped_column(ForeignKey("fighters.id"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.id"
    )
    fighter_a = relationship("Fighter", foreign_keys=[fighter_a_id])
    fighter_b = relationship("Fighter", foreign_keys=[fighter_b_id])
