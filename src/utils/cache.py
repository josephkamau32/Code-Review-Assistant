"""
Cache frequently accessed data to reduce API calls and improve performance
"""

from functools import lru_cache
import hashlib
import pickle
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
        return str(self.cache_dir / f"{hash_key}.pkl")
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value"""
        cache_file = self._get_cache_key(key)
        
        if not Path(cache_file).exists():
            return None
        
        try:
            with open(cache_file, 'rb') as f:
                data = pickle.load(f)
                logger.debug(f"Cache hit: {key}")
                return data
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
            return None
    
    def set(self, key: str, value: Any):
        """Set cached value"""
        cache_file = self._get_cache_key(key)
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(value, f)
                logger.debug(f"Cached: {key}")
        except Exception as e:
            logger.warning(f"Cache write error: {e}")
    
    def clear(self):
        """Clear all cache"""
        for cache_file in self.cache_dir.glob("*.pkl"):
            cache_file.unlink()
        logger.info("Cache cleared")
