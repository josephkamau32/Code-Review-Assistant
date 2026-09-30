"""
Tests for DiskCache security and JSON serialization (SEC-02)
"""

from pathlib import Path
from src.utils.cache import DiskCache


def test_cache_round_trip_json(tmp_path: Path):
    """Test round-trip read/write of JSON-serializable data types"""
    cache = DiskCache(cache_dir=str(tmp_path))

    test_data = {
        "repo": "owner/repo",
        "pr_number": 42,
        "score": 0.95,
        "tags": ["python", "security", "rag"],
        "active": True,
        "metadata": {"nested": "value", "count": 10},
    }

    cache.set("test_key", test_data)
    result = cache.get("test_key")

    assert result == test_data


def test_cache_miss_returns_none(tmp_path: Path):
    """Test that a non-existent key returns None"""
    cache = DiskCache(cache_dir=str(tmp_path))
    assert cache.get("non_existent_key") is None


def test_cache_corrupted_file_fails_safely(tmp_path: Path):
    """Test that corrupted/malformed JSON in cache file treats as cache miss and does not crash (SEC-02)"""
    cache = DiskCache(cache_dir=str(tmp_path))
    key = "corrupted_key"
    cache_file = Path(cache._get_cache_key(key))

    # Write malformed non-JSON data into the cache file
    cache_file.write_text(
        "{this is corrupted malformed json: not valid!!!", encoding="utf-8"
    )

    # Should log warning and return None safely instead of raising JSONDecodeError
    result = cache.get(key)
    assert result is None


def test_cache_non_serializable_fails_safely(tmp_path: Path):
    """Test that attempting to cache non-JSON-serializable data does not crash the app"""
    cache = DiskCache(cache_dir=str(tmp_path))

    class NonSerializableObject:
        pass

    # Should log warning and not crash
    cache.set("bad_key", NonSerializableObject())
    assert cache.get("bad_key") is None


def test_cache_clear(tmp_path: Path):
    """Test clearing all cache entries"""
    cache = DiskCache(cache_dir=str(tmp_path))
    cache.set("key1", {"item": 1})
    cache.set("key2", {"item": 2})

    assert cache.get("key1") is not None
    assert cache.get("key2") is not None

    cache.clear()

    assert cache.get("key1") is None
    assert cache.get("key2") is None
