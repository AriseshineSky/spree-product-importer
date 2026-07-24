"""Persistent per-store daily upload quota (local JSON file)."""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULT_QUOTA_DIR = Path("~/.em_celery/spree_import_quota").expanduser()


def _today_in_tz(tz_name: str) -> str:
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    return datetime.now(tz).date().isoformat()


class DailyUploadQuota:
    """Track successful uploads for a store within a timezone calendar day."""

    def __init__(
        self,
        store_code: str,
        limit: int,
        *,
        timezone: str = "America/Chicago",
        state_dir: Path | str | None = None,
        clock_date: date | None = None,
    ):
        self.store_code = store_code
        self.limit = max(0, int(limit or 0))
        self.timezone = timezone
        self.state_dir = Path(state_dir or DEFAULT_QUOTA_DIR).expanduser()
        self._clock_date = clock_date
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.state_dir / f"{store_code}.json"
        self._date, self._uploaded = self._load()

    @property
    def enabled(self) -> bool:
        return self.limit > 0

    @property
    def uploaded(self) -> int:
        return self._uploaded

    @property
    def remaining(self) -> int | None:
        if not self.enabled:
            return None
        return max(0, self.limit - self._uploaded)

    @property
    def is_exhausted(self) -> bool:
        if not self.enabled:
            return False
        return self._uploaded >= self.limit

    def _today(self) -> str:
        if self._clock_date is not None:
            return self._clock_date.isoformat()
        return _today_in_tz(self.timezone)

    def _load(self) -> tuple[str, int]:
        today = self._today()
        if not self.path.is_file():
            return today, 0
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return today, 0
        if data.get("date") != today:
            return today, 0
        try:
            uploaded = int(data.get("uploaded", 0))
        except (TypeError, ValueError):
            uploaded = 0
        return today, max(0, uploaded)

    def _save(self) -> None:
        payload = {"date": self._date, "uploaded": self._uploaded}
        self.state_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(payload, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(tmp, self.path)

    def record(self, count: int) -> None:
        if count <= 0:
            return
        today = self._today()
        if today != self._date:
            self._date = today
            self._uploaded = 0
        self._uploaded += count
        self._save()

    def take(self, requested: int) -> int:
        """Return how many of ``requested`` may still be uploaded."""
        if requested <= 0:
            return 0
        if not self.enabled:
            return requested
        rem = self.remaining
        assert rem is not None
        return min(requested, rem)
