"""HTTP client for www.ufc.com - the only scrape target this app uses.

See docs/SPEC.md section 2.1/9 for why: UFCStats.com now gates every page
behind a JS proof-of-work anti-bot challenge, and ESPN's robots.txt
explicitly disallows AI crawlers. ufc.com's robots.txt states a 15-second
crawl-delay and this client honors it on every request - no concurrency,
no aggressive retries on 403/429.
"""
from __future__ import annotations

import logging
import time

import requests

from app.config import Config

logger = logging.getLogger(__name__)

USER_AGENT = (
    "UFCPredictorApp/1.0 (personal MMA analytics project; "
    "respects robots.txt crawl-delay)"
)


class UfcClient:
    def __init__(self, base_url: str | None = None, crawl_delay: float | None = None):
        self.base_url = (base_url or Config.UFC_BASE_URL).rstrip("/")
        self.crawl_delay = (
            crawl_delay if crawl_delay is not None else Config.UFC_CRAWL_DELAY_SECONDS
        )
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._last_request_at: float | None = None

    def _throttle(self) -> None:
        if self._last_request_at is None:
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.crawl_delay - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def get(self, path_or_url: str, max_retries: int = 3) -> requests.Response | None:
        """Returns the response, or None if the request ultimately failed.
        Never raises for a failed fetch - callers should treat None as
        "skip this one" so a single bad page doesn't kill a long-running sync.
        """
        url = path_or_url if path_or_url.startswith("http") else f"{self.base_url}{path_or_url}"
        attempt = 0
        while attempt < max_retries:
            self._throttle()
            try:
                resp = self.session.get(url, timeout=30)
            except requests.exceptions.RequestException as exc:
                logger.warning("request failed for %s: %s", url, exc)
                self._last_request_at = time.monotonic()
                attempt += 1
                time.sleep(2**attempt)
                continue
            self._last_request_at = time.monotonic()
            if resp.status_code in (403, 429):
                logger.error(
                    "received HTTP %s for %s - stopping rather than retrying aggressively",
                    resp.status_code,
                    url,
                )
                return None
            if resp.status_code >= 500:
                attempt += 1
                time.sleep(2**attempt)
                continue
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp
        return None
