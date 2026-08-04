from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import Base


class ScrapeCheckpoint(Base):
    __tablename__ = "scrape_checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fighter_slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | done | error
    last_attempt_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
