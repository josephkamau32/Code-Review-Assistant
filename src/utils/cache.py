"""
Cache frequently accessed data to reduce API calls and improve performance
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Optional
from loguru import logger


class DiskCache:
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, key: str) -> str:
        """Generate cache file path from key"""
        hash_key = hashlib.md5(key.encode()).hexdigest()
        return str(self.cache_dir / f"{hash_key}.json")

    def get(self, key: str) -> Optional[Any]:
        """Get cached value safely using JSON deserialization (SEC-02)"""
        cache_file = self._get_cache_key(key)

        if not Path(cache_file).exists():
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.debug(f"Cache hit: {key}")
                return data
        except Exception as e:
            logger.warning(f"Cache read error for {key}: {e} - treating as cache miss")
            return None

    def set(self, key: str, value: Any):
        """Set cached value safely using JSON serialization (SEC-02)"""
        cache_file = self._get_cache_key(key)

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(value, f)
                logger.debug(f"Cached: {key}")
        except Exception as e:
            logger.warning(f"Cache write error for {key}: {e}")

    def clear(self):
        """Clear all cache files"""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
        for legacy_file in self.cache_dir.glob("*.pkl"):
            legacy_file.unlink()
        logger.info("Cache cleared")
