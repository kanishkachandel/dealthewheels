from __future__ import annotations
import json
from typing import Optional
from redis import Redis
from redis.exceptions import RedisError
from app.core.config import get_settings


class RunningTotalsCache:
    """Write-through cache; the database remains the allocation source of truth."""
    def __init__(self):
        try:
            self.client = Redis.from_url(get_settings().redis_url, decode_responses=True, socket_connect_timeout=0.2)
            self.client.ping()
        except RedisError:
            self.client = None

    def put(self, zone_id: str, trip_type: str, values: dict[str, int]) -> None:
        if self.client:
            self.client.setex(f"running-totals:{zone_id}:{trip_type}", 3600, json.dumps(values))

    def get(self, zone_id: str, trip_type: str) -> Optional[dict[str, int]]:
        if not self.client:
            return None
        value = self.client.get(f"running-totals:{zone_id}:{trip_type}")
        return json.loads(value) if value else None


running_totals_cache = RunningTotalsCache()
