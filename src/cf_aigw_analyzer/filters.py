"""Cloudflare AI Gateway log filter mapping."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

MAX_PER_PAGE = 50
ORDER_BY_CHOICES = ("created_at", "provider", "model", "model_type", "success", "cached")
DIRECTION_CHOICES = ("asc", "desc")


def parse_datetime(value: str | None) -> str | None:
    """Normalize common date inputs to the Cloudflare API UTC format."""

    if not value:
        return None

    value = value.strip()
    if "T" in value:
        return value

    patterns = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d",
    )
    for pattern in patterns:
        try:
            parsed = datetime.strptime(value, pattern)
            return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    return value


@dataclass(slots=True)
class LogFilters:
    page: int = 1
    per_page: int = MAX_PER_PAGE
    order_by: str | None = None
    direction: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    model: str | None = None
    provider: str | None = None
    model_type: str | None = None
    search: str | None = None
    cached: bool | None = None
    success: bool | None = None
    feedback: int | None = None
    min_cost: float | None = None
    max_cost: float | None = None
    min_duration: float | None = None
    max_duration: float | None = None
    min_tokens_in: int | None = None
    max_tokens_in: int | None = None
    min_tokens_out: int | None = None
    max_tokens_out: int | None = None
    min_total_tokens: int | None = None
    max_total_tokens: int | None = None
    meta_info: bool = False

    @classmethod
    def from_args(cls, args: Any) -> "LogFilters":
        return cls(
            page=max(1, getattr(args, "page", 1) or 1),
            per_page=min(max(1, getattr(args, "per_page", MAX_PER_PAGE) or MAX_PER_PAGE), MAX_PER_PAGE),
            order_by=getattr(args, "order_by", None),
            direction=getattr(args, "direction", None),
            start_date=getattr(args, "start_date", None),
            end_date=getattr(args, "end_date", None),
            model=getattr(args, "model", None),
            provider=getattr(args, "provider", None),
            model_type=getattr(args, "model_type", None),
            search=getattr(args, "search", None),
            cached=getattr(args, "cached", None),
            success=getattr(args, "success", None),
            feedback=getattr(args, "feedback", None),
            min_cost=getattr(args, "min_cost", None),
            max_cost=getattr(args, "max_cost", None),
            min_duration=getattr(args, "min_duration", None),
            max_duration=getattr(args, "max_duration", None),
            min_tokens_in=getattr(args, "min_tokens_in", None),
            max_tokens_in=getattr(args, "max_tokens_in", None),
            min_tokens_out=getattr(args, "min_tokens_out", None),
            max_tokens_out=getattr(args, "max_tokens_out", None),
            min_total_tokens=getattr(args, "min_total_tokens", None),
            max_total_tokens=getattr(args, "max_total_tokens", None),
            meta_info=bool(getattr(args, "meta_info", False)),
        )

    def to_api_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {
            "page": self.page,
            "per_page": min(self.per_page, MAX_PER_PAGE),
        }

        optional = {
            "order_by": self.order_by,
            "order_by_direction": self.direction,
            "start_date": parse_datetime(self.start_date),
            "end_date": parse_datetime(self.end_date),
            "model": self.model,
            "provider": self.provider,
            "model_type": self.model_type,
            "search": self.search,
            "feedback": self.feedback,
            "min_cost": self.min_cost,
            "max_cost": self.max_cost,
            "min_duration": self.min_duration,
            "max_duration": self.max_duration,
            "min_tokens_in": self.min_tokens_in,
            "max_tokens_in": self.max_tokens_in,
            "min_tokens_out": self.min_tokens_out,
            "max_tokens_out": self.max_tokens_out,
            "min_total_tokens": self.min_total_tokens,
            "max_total_tokens": self.max_total_tokens,
        }
        for key, value in optional.items():
            if value is not None and value != "":
                params[key] = value

        if self.cached is not None:
            params["cached"] = str(self.cached).lower()
        if self.success is not None:
            params["success"] = str(self.success).lower()
        if self.meta_info:
            params["meta_info"] = "true"

        return params
