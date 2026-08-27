"""Image ingestion from an e-commerce listing URL.

The weakest requirement in the spec, and worth naming as such: marketplace HTML is
adversarial to scrapers and changes without notice. This module does the honest minimum —
fetch the page, take the largest `og:image`/`twitter:image`, fall back to the biggest
`<img>` — and returns a clear error otherwise. It does not pretend to be a scraper for any
specific marketplace, because such a thing would break before the demo.
"""

from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# A browser-like UA. Not evasion — many CDNs return 403 to the default httpx UA and the
# request is an ordinary public-page fetch either way.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,image/*;q=0.8",
}

MAX_IMAGE_BYTES = 12 * 1024 * 1024
_IMAGE_META = ("og:image:secure_url", "og:image", "twitter:image", "twitter:image:src")


class IngestError(Exception):
    """Ingestion failed for a reason the operator can act on. Message is user-facing."""


def _absolute(base: str, candidate: str) -> str:
    return candidate if candidate.startswith(("http://", "https://")) else urljoin(base, candidate)


def _find_image_url(html: str, page_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    # Ordered by how deliberately the site chose the image: OG tags are curated, <img>
    # tags are whatever happened to be in the DOM.
    for prop in _IMAGE_META:
        tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
        if tag and tag.get("content"):
            return _absolute(page_url, tag["content"].strip())

    widest: tuple[int, str] | None = None
    for img in soup.find_all("img"):
        src = (img.get("src") or img.get("data-src") or "").strip()
        if not src or src.startswith("data:"):
            continue
        try:
            width = int(str(img.get("width", "0")).strip() or 0)
        except ValueError:
            width = 0
        if widest is None or width > widest[0]:
            widest = (width, _absolute(page_url, src))

    return widest[1] if widest else None


def fetch_image(url: str) -> bytes:
    """Fetch the primary product image for a listing URL.

    Raises IngestError with an operator-readable message on any failure.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise IngestError("Enter a full http(s) URL, e.g. https://example.com/product/123")

    try:
        with httpx.Client(headers=_HEADERS, follow_redirects=True, timeout=15.0) as client:
            response = client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            # The URL may be the image itself rather than a listing page.
            if content_type.startswith("image/"):
                image_bytes = response.content
            else:
                image_url = _find_image_url(response.text, str(response.url))
                if not image_url:
                    raise IngestError(
                        "No product image found on that page. Save the label image and "
                        "upload it directly."
                    )
                image_response = client.get(image_url)
                image_response.raise_for_status()
                image_bytes = image_response.content
    except httpx.HTTPStatusError as exc:
        raise IngestError(
            f"The page returned HTTP {exc.response.status_code}. Many marketplaces block "
            "automated requests — upload the label image instead."
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning("URL ingestion failed for %s: %s", url, exc)
        raise IngestError("Could not reach that URL. Check the link or upload the image.") from exc

    if not image_bytes:
        raise IngestError("The image at that URL was empty.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise IngestError("That image is larger than 12 MB.")
    return image_bytes
