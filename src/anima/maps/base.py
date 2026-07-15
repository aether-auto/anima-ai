"""Date and validity primitives shared by map datasets."""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import TypeAlias

_SIGNED_ISO_DATE = re.compile(r"(?P<year>[+-]?\d{4,})-(?P<month>\d{2})-(?P<day>\d{2})")


@dataclass(frozen=True, order=True, slots=True)
class MapDate:
    """Signed proleptic Gregorian date supporting historical BCE years.

    Negative years use BCE labels directly: year ``-44`` means 44 BCE. Year zero
    does not exist in this public chronology.
    """

    year: int
    month: int = 1
    day: int = 1

    def __post_init__(self) -> None:
        for field_name, value in (
            ("year", self.year),
            ("month", self.month),
            ("day", self.day),
        ):
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"map date {field_name} must be integer")
        if self.year == 0:
            raise ValueError("map date chronology has no year zero")
        if self.month < 1 or self.month > 12:
            raise ValueError(f"map date month outside 1..12: {self.month}")
        # BCE labels are one off from astronomical numbering (44 BCE is
        # astronomical year -43), which is what leap-year rules apply to.
        astronomical_year = self.year + 1 if self.year < 0 else self.year
        maximum_day = calendar.monthrange(astronomical_year, self.month)[1]
        if self.day < 1 or self.day > maximum_day:
            raise ValueError(
                f"map date day outside 1..{maximum_day} for "
                f"{self.year}-{self.month:02d}: {self.day}"
            )

    def isoformat(self) -> str:
        if self.year < 0:
            year = f"-{abs(self.year):04d}"
        elif self.year > 9999:
            year = f"+{self.year}"
        else:
            year = f"{self.year:04d}"
        return f"{year}-{self.month:02d}-{self.day:02d}"


DateLike: TypeAlias = MapDate | date | datetime | str | int


def coerce_date(value: DateLike) -> MapDate:
    """Return deterministic calendar date from supported public date forms.

    Integer years resolve to January 1. Datetimes intentionally discard time and
    timezone because territory validity has calendar-day resolution.
    """

    if isinstance(value, MapDate):
        return value
    if isinstance(value, datetime):
        return MapDate(value.year, value.month, value.day)
    if isinstance(value, date):
        return MapDate(value.year, value.month, value.day)
    if isinstance(value, bool):
        raise TypeError("unsupported date value: bool")
    if isinstance(value, int):
        return MapDate(value)
    if isinstance(value, str):
        matched = _SIGNED_ISO_DATE.fullmatch(value)
        if matched is None:
            raise ValueError(f"date must use signed ISO YYYY-MM-DD form: {value!r}")
        return MapDate(
            int(matched.group("year")),
            int(matched.group("month")),
            int(matched.group("day")),
        )
    raise TypeError(f"unsupported date value: {type(value).__name__}")


@dataclass(frozen=True, slots=True, init=False)
class ValidityInterval:
    """Half-open calendar interval ``[start, end)``.

    Missing start or end represents an unbounded side. Adjacent versions may share
    one transition date without overlapping.
    """

    start: MapDate | None
    end: MapDate | None

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

        if self.end is not None and other.start is not None and self.end <= other.start:
            return False
        if other.end is not None and self.start is not None and other.end <= self.start:
            return False
        return True

    def to_dict(self) -> dict[str, str | None]:
        """Return canonical JSON/YAML representation."""

        return {
            "end": None if self.end is None else self.end.isoformat(),
            "start": None if self.start is None else self.start.isoformat(),
        }
