from datetime import datetime, timedelta
from typing import Dict, List

from fastapi import HTTPException


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = timedelta(seconds=window_seconds)
        self.hits: Dict[str, List[datetime]] = {}

    def check(self, key: str) -> None:
        now = datetime.utcnow()
        window_start = now - self.window
        entries = self.hits.get(key, [])
        entries = [ts for ts in entries if ts >= window_start]

        if len(entries) >= self.limit:
            oldest_in_window = min(entries) if entries else now
            retry_after = int(max(1, (oldest_in_window + self.window - now).total_seconds()))
            raise HTTPException(
                status_code=429,
                detail={
                    "message": "Rate limit exceeded",
                    "retry_after_seconds": retry_after,
                },
            )

        entries.append(now)
        self.hits[key] = entries

    def clear(self, key: str) -> None:
        if key in self.hits:
            del self.hits[key]

    def clear_prefix(self, prefix: str) -> None:
        for key in list(self.hits.keys()):
            if key.startswith(prefix):
                del self.hits[key]

from app.core.config import settings


ai_rate_limiter = RateLimiter(limit=20, window_seconds=60)
auth_login_rate_limiter = RateLimiter(
    limit=settings.auth_login_max_attempts,
    window_seconds=settings.auth_login_window_seconds,
)
