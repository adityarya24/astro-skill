"""Serializable dataclasses for the astro MCP service.

These models are deliberately plain: only strings, floats, and other primitives
so they survive JSON round-trips when returned from MCP tool calls.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class BirthDetails:
    dob: str
    tob: str
    place: str
    lat: float
    lon: float
    timezone_name: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ClientProfile:
    client_id: str
    display_name: str
    birth: BirthDetails | None
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "client_id": self.client_id,
            "display_name": self.display_name,
            "birth": self.birth.to_dict() if self.birth else None,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ReportRecord:
    report_id: str
    client_id: str
    report_type: str
    path: str
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)
