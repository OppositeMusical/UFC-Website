"""Fighter discovery via ufc.com's own sitemap - the site's explicit,
sanctioned way to enumerate every URL it wants crawled, including every
/athlete/<slug> profile. Confirmed live: sitemap.xml is a sitemap index
listing ~20+ `?page=N` sub-sitemaps, each with ~140+ athlete URLs.
"""
from __future__ import annotations

import logging
import re

from app.services.scraper.ufc_client import UfcClient

logger = logging.getLogger(__name__)

SITEMAP_INDEX_PATH = "/sitemap.xml"
SUB_SITEMAP_RE = re.compile(r"<loc>(https://www\.ufc\.com/sitemap\.xml\?page=\d+)</loc>")
ATHLETE_URL_RE = re.compile(r"https://www\.ufc\.com/athlete/([a-z0-9-]+)")


def discover_athlete_slugs(client: UfcClient) -> list[str]:
    resp = client.get(SITEMAP_INDEX_PATH)
    if resp is None:
        logger.error("could not fetch the ufc.com sitemap index")
        return []

    sub_sitemap_urls = SUB_SITEMAP_RE.findall(resp.text)
    if not sub_sitemap_urls:
        # Some responses may already be a flat sitemap rather than an index.
        return sorted(set(ATHLETE_URL_RE.findall(resp.text)))

    slugs: set[str] = set()
    for sub_url in sub_sitemap_urls:
        sub_resp = client.get(sub_url)
        if sub_resp is None:
            continue
        slugs.update(ATHLETE_URL_RE.findall(sub_resp.text))
    return sorted(slugs)
