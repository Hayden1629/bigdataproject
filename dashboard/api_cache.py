"""
api_cache.py

Persistent disk cache for external API calls.  Survives server restarts so
repeated lookups for the same drug never hit the network again.

Usage (stack under @st.cache_data so in-session calls are instant):

    @st.cache_data(ttl=3600, show_spinner=False)
    @disk_cache(ttl=86400)
    def my_api_fn(drug_name: str) -> dict:
        ...

Cache files are stored as pickle in:
    <project_root>/dashboard/cache/api/
"""

from __future__ import annotations

import hashlib
import json
import pickle
import time
from functools import wraps
from pathlib import Path

# Store alongside the other parquet cache files
_CACHE_DIR = Path(__file__).parent / "cache" / "api"


def _cache_path(fn_name: str, args: tuple, kwargs: dict) -> Path:
    try:
        key_str = json.dumps([fn_name, list(args), sorted(kwargs.items())], default=str)
    except Exception:
        key_str = f"{fn_name}{args}{kwargs}"
    digest = hashlib.md5(key_str.encode()).hexdigest()
    return _CACHE_DIR / f"{fn_name}_{digest}.pkl"


def disk_cache(ttl: int = 86400):
    """
    Decorator that persists a function's return value to disk.

    Parameters
    ----------
    ttl : seconds before a cached entry is considered stale (default 24 h)
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path = _cache_path(fn.__name__, args, kwargs)

            # Cache hit?
            if path.exists():
                age = time.time() - path.stat().st_mtime
                if age < ttl:
                    try:
                        with path.open("rb") as f:
                            return pickle.load(f)  # noqa: S301
                    except Exception:
                        pass  # corrupt file — fall through to re-fetch

            # Cache miss — call the real function
            result = fn(*args, **kwargs)

            # Persist (best-effort; never crash the app on write failure)
            try:
                tmp = path.with_suffix(".tmp")
                with tmp.open("wb") as f:
                    pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
                tmp.replace(path)
            except Exception:
                pass

            return result

        # Expose a helper so callers can manually bust the cache for a drug
        def invalidate(*args, **kwargs):
            path = _cache_path(fn.__name__, args, kwargs)
            path.unlink(missing_ok=True)

        wrapper.invalidate = invalidate
        return wrapper

    return decorator
