"""Date and validity primitives shared by map datasets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import TypeAlias

DateLike: TypeAlias = date | datetime | str | int


def coerce_date(value: DateLike) -> date:
    """Return deterministic calendar date from supported public date forms.

    Integer years resolve to January 1. Datetimes intentionally discard time and
    timezone because territory validity has calendar-day resolution.
    """

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, int):
        if value < 1 or value > 9999:
            raise ValueError(f"year outside supported range 1..9999: {value}")
        return date(value, 1, 1)
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as error:
            raise ValueError(f"date must use ISO YYYY-MM-DD form: {value!r}") from error
    raise TypeError(f"unsupported date value: {type(value).__name__}")


@dataclass(frozen=True, slots=True, init=False)
class ValidityInterval:
    """Half-open calendar interval ``[start, end)``.

    Missing start or end represents an unbounded side. Adjacent versions may share
    one transition date without overlapping.
    """

    start: date | None
    end: date | None

    def __init__(self, start: DateLike | None = None, end: DateLike | None = None) -> None:
        normalized_start = None if start is None else coerce_date(start)
        normalized_end = None if end is None else coerce_date(end)
        if (
            normalized_start is not None
            and normalized_end is not None
            and normalized_start >= normalized_end
        ):
            raise ValueError(
                "validity interval start must precede end: "
                f"{normalized_start.isoformat()} >= {normalized_end.isoformat()}"
            )
        object.__setattr__(self, "start", normalized_start)
        object.__setattr__(self, "end", normalized_end)

    def contains(self, value: DateLike) -> bool:
        """Return whether date falls inside half-open interval."""

        instant = coerce_date(value)
        return (self.start is None or instant >= self.start) and (
            self.end is None or instant < self.end
        )

    def overlaps(self, other: ValidityInterval) -> bool:
        """Return whether this interval shares any valid instant with another."""

        left = max(self.start or date.min, other.start or date.min)
        right = min(self.end or date.max, other.end or date.max)
        return left < right

    def to_dict(self) -> dict[str, str | None]:
        """Return canonical JSON/YAML representation."""

        return {
            "end": None if self.end is None else self.end.isoformat(),
            "start": None if self.start is None else self.start.isoformat(),
        }

