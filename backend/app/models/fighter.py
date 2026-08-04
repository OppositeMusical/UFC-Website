from __future__ import annotations

import datetime as dt

from sqlalchemy import Date, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import Base


class Fighter(Base):
    __tablename__ = "fighters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ufc_slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    nickname: Mapped[str | None] = mapped_column(String(255))
    weight_class: Mapped[str | None] = mapped_column(String(100))
    stance: Mapped[str | None] = mapped_column(String(50))

    height_in: Mapped[float | None] = mapped_column(Float)
    reach_in: Mapped[float | None] = mapped_column(Float)
    leg_reach_in: Mapped[float | None] = mapped_column(Float)
    dob: Mapped[dt.date | None] = mapped_column(Date)

    wins: Mapped[int | None] = mapped_column(Integer)
    losses: Mapped[int | None] = mapped_column(Integer)
    draws: Mapped[int | None] = mapped_column(Integer)
    no_contests: Mapped[int | None] = mapped_column(Integer)

    status: Mapped[str | None] = mapped_column(String(50))
    place_of_birth: Mapped[str | None] = mapped_column(String(255))
    trains_at: Mapped[str | None] = mapped_column(String(255))
    octagon_debut: Mapped[str | None] = mapped_column(String(50))

    slpm: Mapped[float | None] = mapped_column(Float)
    sapm: Mapped[float | None] = mapped_column(Float)
    sig_str_defense_pct: Mapped[float | None] = mapped_column(Float)
    td_avg: Mapped[float | None] = mapped_column(Float)
    td_defense_pct: Mapped[float | None] = mapped_column(Float)
    sub_avg: Mapped[float | None] = mapped_column(Float)
    knockdown_avg: Mapped[float | None] = mapped_column(Float)
    avg_fight_time: Mapped[str | None] = mapped_column(String(20))

    source_url: Mapped[str | None] = mapped_column(String(500))
    roster_synced_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    stats_scraped_at: Mapped[dt.datetime | None] = mapped_column(DateTime)

    @property
    def record(self) -> str:
        return f"{self.wins or 0}-{self.losses or 0}-{self.draws or 0}"

    def to_summary_text(self) -> str:
        """Natural-language summary used as the ChromaDB document body."""
        parts = [f"{self.name}"]
        if self.nickname:
            parts.append(f'"{self.nickname}"')
        if self.weight_class:
            parts.append(f"({self.weight_class})")
        parts.append(f"- record {self.record}.")
        stat_bits = []
        if self.slpm is not None:
            stat_bits.append(f"Significant strikes landed: {self.slpm}/min")
        if self.sapm is not None:
            stat_bits.append(f"absorbed: {self.sapm}/min")
        if self.sig_str_defense_pct is not None:
            stat_bits.append(f"striking defense {self.sig_str_defense_pct}%")
        if stat_bits:
            parts.append(". ".join(stat_bits).capitalize() + ".")
        td_bits = []
        if self.td_avg is not None:
            td_bits.append(f"Takedowns: {self.td_avg} avg per 15 min")
        if self.td_defense_pct is not None:
            td_bits.append(f"defense {self.td_defense_pct}%")
        if td_bits:
            parts.append(", ".join(td_bits) + ".")
        if self.sub_avg is not None:
            parts.append(f"Submissions: {self.sub_avg} avg per 15 min.")
        if self.knockdown_avg is not None:
            parts.append(f"Knockdown avg: {self.knockdown_avg}.")
        if self.stance:
            parts.append(f"Stance: {self.stance}.")
        if self.reach_in is not None:
            parts.append(f"Reach: {self.reach_in}in.")
        return " ".join(parts)

    def to_metadata(self) -> dict:
        return {
            "name": self.name,
            "weight_class": self.weight_class or "",
            "stance": self.stance or "",
            "wins": self.wins or 0,
            "losses": self.losses or 0,
            "draws": self.draws or 0,
            "slpm": self.slpm or 0.0,
            "sapm": self.sapm or 0.0,
            "td_avg": self.td_avg or 0.0,
            "sub_avg": self.sub_avg or 0.0,
            "sig_str_defense_pct": self.sig_str_defense_pct or 0.0,
            "td_defense_pct": self.td_defense_pct or 0.0,
        }
