"""CBR USD/RUB rate — cached in SQLite, refreshed hourly."""
import logging

import httpx

from . import config, db

_TTL_SECONDS = 3600
_KEY = "USD_RUB"

log = logging.getLogger(__name__)


async def get_usd_rub() -> float:
    """Return current USD/RUB rate. Uses cache within TTL, refetches when stale.

    Falls back to last known rate if the fetch fails. Raises if nothing is available.
    """
    cached = db.get_cached_rate(_KEY, _TTL_SECONDS)
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(config.CBR_RATE_URL)
            resp.raise_for_status()
            value = float(resp.json()["Valute"]["USD"]["Value"])
        db.set_cached_rate(_KEY, value)
        log.info("CBR USD/RUB refreshed: %.4f", value)
        return value
    except Exception:
        log.exception("CBR fetch failed, falling back to last known rate")
        stale = db.get_last_rate(_KEY)
        if stale is None:
            raise
        return stale
