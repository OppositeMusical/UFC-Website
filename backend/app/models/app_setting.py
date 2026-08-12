from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import Base

# Well-known keys stored in this table.
#
# A "last_fighter_sync_at" key used to live here too. It was write-only by
# 0.5.4 - the Settings card that read it reported "Never synced" on seeded
# installs, and the fix was to measure the fighters table instead
# (services/status.py), which left nothing reading the setting. Old rows in
# existing databases are harmless; they are simply never consulted.
KEY_ACTIVE_PROVIDER = "active_provider"
KEY_ACTIVE_OLLAMA_MODEL = "active_ollama_model"
KEY_SCHEMA_VERSION = "schema_version"

CURRENT_SCHEMA_VERSION = "1"


class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[str | None] = mapped_column(String(2000))
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow
    )
