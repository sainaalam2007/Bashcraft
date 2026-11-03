"""
URL Normalization, Canonicalization, and Classification Engine.
Handles RFC 3986 compliance, duplicate URL deduplication, fragment stripping,
dot-segment resolution, port normalization, and internal vs. external classification.
"""

import os
import posixpath
import re
from typing import Optional, Tuple
from urllib.parse import urlparse, urlunparse, urljoin, parse_qsl, urlencode


# Standard analytics query parameters that do not alter page content
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "msclkid", "mc_cid", "mc_eid", "_hsenc", "_hsmi"
}

# Non-web document / static asset extensions that shouldn't be crawled as HTML pages
NON_HTML_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp", ".tiff",
    ".mp3", ".mp4", ".avi", ".mov", ".webm", ".mkv", ".wav",
    ".pdf", ".zip", ".tar", ".gz", ".rar", ".7z", ".exe", ".dmg", ".apk",
    ".css", ".js", ".mjs", ".woff", ".woff2", ".ttf", ".eot", ".otf"
}

# Non-crawlable URI schemes
SPECIAL_SCHEMES = {"mailto", "tel", "javascript", "data", "sms", "callto"}


class URLNormalizer:
    """Provides bulletproof URL normalization, canonicalization, and classification."""

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Validates if the provided string is a syntactically valid HTTP/HTTPS URL."""
        if not url or not isinstance(url, str):
            return False
        url = url.strip()
        try:
            parsed = urlparse(url)
            return (
                parsed.scheme in ("http", "https")
                and bool(parsed.netloc)
                and "." in parsed.netloc
            )
        except Exception:
            return False

    @staticmethod
    def get_domain(url: str) -> str:
        """Extracts the normalized domain/netloc (e.g. bashcraftclub.vercel.app)."""
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            # Remove default ports if present
            if netloc.endswith(":80") and parsed.scheme == "http":
                netloc = netloc[:-3]
            elif netloc.endswith(":443") and parsed.scheme == "https":
                netloc = netloc[:-4]
            return netloc
        except Exception:
            return ""

    @classmethod
    def normalize(cls, raw_url: str, base_url: Optional[str] = None) -> Optional[str]:
        """
        Normalizes a URL to its canonical form:
        - Resolves relative URLs against base_url
        - Normalizes scheme to lowercase (preserves http/https)
        - Normalizes host to lowercase and removes default ports (80, 443)
        - Removes fragments (#section)
        - Cleans duplicate path slashes and resolves dot segments (/a/b/../c -> /a/c)
        - Standardizes trailing slashes (preserves root '/', strips subpath trailing slashes)
        - Strips tracking query parameters (utm_*, etc.) and sorts remaining params
        """
        if not raw_url or not isinstance(raw_url, str):
            return None

        clean = raw_url.strip()
        if not clean or clean.startswith("#"):
            return None

        # Resolve relative URLs if base_url is provided
        if base_url:
            clean = urljoin(base_url, clean)

        try:
            parsed = urlparse(clean)
        except Exception:
            return None

        # Only process http and https schemes
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            return None

        netloc = parsed.netloc.lower()
        if not netloc:
            return None

        # Remove default ports
        if (scheme == "http" and netloc.endswith(":80")) or (
            scheme == "https" and netloc.endswith(":443")
        ):
            netloc = netloc.rsplit(":", 1)[0]

        # Normalize path
        path = parsed.path or "/"
        # Resolve dot-segments like /events/../about -> /about
        path = posixpath.normpath(path)
        if not path.startswith("/"):
            path = "/" + path

        # Preserve root slash, but strip trailing slashes on sub-paths for consistency
        # e.g. /about/ -> /about, but / remains /
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]

        # Clean query parameters: remove tracking params, sort remaining keys
        query = ""
        if parsed.query:
            query_pairs = parse_qsl(parsed.query, keep_blank_values=False)
            filtered_pairs = [
                (k, v) for k, v in query_pairs if k.lower() not in TRACKING_PARAMS
            ]
            if filtered_pairs:
                filtered_pairs.sort(key=lambda x: x[0])
                query = urlencode(filtered_pairs)

        # Discard fragments (#...) completely for canonical URL
        fragment = ""

        canonical = urlunparse((scheme, netloc, path, "", query, fragment))
        return canonical

    @classmethod
    def is_internal(cls, target_url: str, base_url: str) -> bool:
        """
        Determines whether a target URL belongs to the internal website domain.
        Subdomains or identical hosts (with/without www) are treated as internal.
        """
        target_domain = cls.get_domain(target_url)
        base_domain = cls.get_domain(base_url)

        if not target_domain or not base_domain:
            return False

        # Exact match
        if target_domain == base_domain:
            return True

        # Handle www vs non-www
        base_no_www = base_domain.removeprefix("www.")
        target_no_www = target_domain.removeprefix("www.")
        if base_no_www == target_no_www:
            return True

        # Subdomain match
        if target_no_www.endswith("." + base_no_www):
            return True

        return False

    @classmethod
    def is_crawlable_html_page(cls, url: str) -> bool:
        """
        Determines if the URL points to an HTML webpage rather than a static asset
        (images, CSS, JS, documents, videos).
        """
        parsed = urlparse(url)
        path = parsed.path.lower()
        _, ext = os.path.splitext(path)
        if ext and ext in NON_HTML_EXTENSIONS:
            return False
        return True

    @classmethod
    def classify_href(cls, href: str, base_url: str) -> Tuple[str, Optional[str]]:
        """
        Categorizes a raw href found on a page into:
        - ('special', scheme) for mailto, tel, javascript
        - ('anchor', href) for same-page hash fragments
        - ('asset', url) for images/files/css
        - ('internal_page', canonical_url) for internal crawlable pages
        - ('external', canonical_url) for external links
        - ('invalid', None) for unparseable links
        """
        if not href or not isinstance(href, str):
            return ("invalid", None)

        href = href.strip()
        if not href:
            return ("invalid", None)

        # Check special schemes
        for scheme in SPECIAL_SCHEMES:
            if href.lower().startswith(f"{scheme}:"):
                return ("special", href)

        if href.startswith("#"):
            return ("anchor", href)

        # Normalize relative to base
        normalized = cls.normalize(href, base_url=base_url)
        if not normalized:
            return ("invalid", None)

        # Check if asset
        if not cls.is_crawlable_html_page(normalized):
            return ("asset", normalized)

        # Check internal vs external
        if cls.is_internal(normalized, base_url):
            return ("internal_page", normalized)
        else:
            return ("external", normalized)
