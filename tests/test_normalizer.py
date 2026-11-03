"""
Unit tests for URLNormalizer and classification.
Validates RFC 3986 compliance, duplicate URL normalization, and edge case handling.
"""

import pytest
from core.normalizer import URLNormalizer


class TestURLNormalizer:

    def test_valid_urls(self):
        assert URLNormalizer.is_valid_url("https://bashcraftclub.vercel.app/")
        assert URLNormalizer.is_valid_url("http://example.com/page")
        assert URLNormalizer.is_valid_url("https://sub.domain.org/path?q=1")
        assert not URLNormalizer.is_valid_url("not_a_url")
        assert not URLNormalizer.is_valid_url("ftp://example.com")
        assert not URLNormalizer.is_valid_url("")
        assert not URLNormalizer.is_valid_url("javascript:void(0)")

    def test_canonical_normalization(self):
        base = "https://bashcraftclub.vercel.app"

        # Case normalization
        assert URLNormalizer.normalize("HTTPS://BASHCRAFTCLUB.VERCEL.APP/about") == "https://bashcraftclub.vercel.app/about"

        # Trailing slash consistency (subpaths stripped, root kept)
        assert URLNormalizer.normalize("https://bashcraftclub.vercel.app/about/") == "https://bashcraftclub.vercel.app/about"
        assert URLNormalizer.normalize("https://bashcraftclub.vercel.app/") == "https://bashcraftclub.vercel.app/"

        # Default port removal
        assert URLNormalizer.normalize("http://example.com:80/path") == "http://example.com/path"
        assert URLNormalizer.normalize("https://example.com:443/path") == "https://example.com/path"

        # Dot-segment path resolution
        assert URLNormalizer.normalize("https://example.com/events/../about") == "https://example.com/about"
        assert URLNormalizer.normalize("https://example.com/a/b/./c") == "https://example.com/a/b/c"

        # Fragment stripping
        assert URLNormalizer.normalize("https://example.com/about#team-section") == "https://example.com/about"
        assert URLNormalizer.normalize("https://bashcraftclub.vercel.app/#form-section") == "https://bashcraftclub.vercel.app/"

        # Relative path resolution
        assert URLNormalizer.normalize("/events", base_url=base) == "https://bashcraftclub.vercel.app/events"
        assert URLNormalizer.normalize("team", base_url=base) == "https://bashcraftclub.vercel.app/team"

    def test_tracking_params_removal(self):
        url = "https://bashcraftclub.vercel.app/events?utm_source=twitter&utm_medium=social&page=2"
        normalized = URLNormalizer.normalize(url)
        # utm_* params removed, functional param page=2 preserved
        assert normalized == "https://bashcraftclub.vercel.app/events?page=2"

    def test_internal_vs_external(self):
        base = "https://bashcraftclub.vercel.app"

        # Same host
        assert URLNormalizer.is_internal("https://bashcraftclub.vercel.app/about", base)
        # www vs non-www
        assert URLNormalizer.is_internal("https://www.bashcraftclub.vercel.app/about", base)
        # Subdomain
        assert URLNormalizer.is_internal("https://api.bashcraftclub.vercel.app/v1", base)
        # External websites
        assert not URLNormalizer.is_internal("https://github.com/BashCraftClub", base)
        assert not URLNormalizer.is_internal("https://instagram.com/bashcraft.vit", base)
        assert not URLNormalizer.is_internal("https://google.com", base)

    def test_classify_href(self):
        base = "https://bashcraftclub.vercel.app"

        # Internal page
        cat, url = URLNormalizer.classify_href("/about", base)
        assert cat == "internal_page"
        assert url == "https://bashcraftclub.vercel.app/about"

        # External
        cat, url = URLNormalizer.classify_href("https://github.com/BashCraftClub", base)
        assert cat == "external"

        # Asset
        cat, url = URLNormalizer.classify_href("/assets/index.js", base)
        assert cat == "asset"

        # Special
        cat, val = URLNormalizer.classify_href("mailto:contact@bashcraft.org", base)
        assert cat == "special"

        # Anchor
        cat, val = URLNormalizer.classify_href("#section-1", base)
        assert cat == "anchor"

