import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import cache


def test_is_cache_fresh(tmp_path: Path, monkeypatch):
    test_dir = tmp_path / "cache"
    test_dir.mkdir()

    monkeypatch.setattr(cache, "CACHE_DIR", test_dir, raising=False)

    file_path = cache.cache_path("2025-01-01", "2025-01-07")
    file_path.write_text("{}", encoding="utf-8")

    assert cache.is_cache_fresh(file_path)

    stale_time = datetime.now(timezone.utc) - timedelta(hours=25)
    timestamp = stale_time.timestamp()
    os.utime(file_path, (timestamp, timestamp))

    assert cache.is_cache_fresh(file_path) is False
