"""
Unit and integration tests for WebCrawler traversal.
Validates loop prevention (Page A -> B -> C -> A), max depth constraints,
max page constraints, and broken link handling.
"""

from unittest.mock import MagicMock, patch
import httpx
import pytest

from core.config import CrawlConfig
from core.crawler import WebCrawler
from core.models import LinkStatus


class TestWebCrawlerEngine:

    def test_loop_prevention(self):
        """
        Tests circular reference loop:
        Page A (/) -> Page B (/b) -> Page C (/c) -> Page A (/)
        Crawler must not loop indefinitely and must visit each page once.
        """
        html_a = '<html><head><title>Page A</title></head><body><a href="/b">Go to B</a></body></html>'
        html_b = '<html><head><title>Page B</title></head><body><a href="/c">Go to C</a></body></html>'
        html_c = '<html><head><title>Page C</title></head><body><a href="/">Back to A</a></body></html>'

        mock_responses = {
            "https://testsite.com/": httpx.Response(200, text=html_a, request=httpx.Request("GET", "https://testsite.com/")),
            "https://testsite.com/b": httpx.Response(200, text=html_b, request=httpx.Request("GET", "https://testsite.com/b")),
            "https://testsite.com/c": httpx.Response(200, text=html_c, request=httpx.Request("GET", "https://testsite.com/c")),
        }

        def mock_get(url, **kwargs):
            if str(url) in mock_responses:
                return mock_responses[str(url)]
            return httpx.Response(404, text="Not Found", request=httpx.Request("GET", str(url)))

        def mock_head(url, **kwargs):
            if str(url) in mock_responses:
                return httpx.Response(200, request=httpx.Request("HEAD", str(url)))
            return httpx.Response(404, request=httpx.Request("HEAD", str(url)))

        config = CrawlConfig(
            start_url="https://testsite.com/",
            max_depth=5,
            max_pages=10,
            spa_scan=False,
            respect_robots_txt=False,
            check_broken_links=False
        )

        crawler = WebCrawler(config)

        with patch.object(httpx.Client, "get", side_effect=mock_get):
            with patch.object(httpx.Client, "head", side_effect=mock_head):
                result = crawler.crawl()

        # Visited exactly 3 pages, terminated cleanly despite circular loop
        assert len(result.pages) == 3
        assert "https://testsite.com/" in result.pages
        assert "https://testsite.com/b" in result.pages
        assert "https://testsite.com/c" in result.pages

    def test_depth_limit_enforcement(self):
        """
        Tests max_depth constraint.
        Root is depth 0 -> /depth1 is depth 1 -> /depth2 is depth 2 -> /depth3 is depth 3.
        When max_depth=1, only root and depth1 should be crawled.
        """
        html_root = '<html><body><a href="/depth1">Level 1</a></body></html>'
        html_d1 = '<html><body><a href="/depth2">Level 2</a></body></html>'
        html_d2 = '<html><body><a href="/depth3">Level 3</a></body></html>'

        mock_responses = {
            "https://testsite.com/": httpx.Response(200, text=html_root, request=httpx.Request("GET", "https://testsite.com/")),
            "https://testsite.com/depth1": httpx.Response(200, text=html_d1, request=httpx.Request("GET", "https://testsite.com/depth1")),
            "https://testsite.com/depth2": httpx.Response(200, text=html_d2, request=httpx.Request("GET", "https://testsite.com/depth2")),
        }

        config = CrawlConfig(
            start_url="https://testsite.com/",
            max_depth=1,
            max_pages=20,
            spa_scan=False,
            respect_robots_txt=False,
            check_broken_links=False
        )

        crawler = WebCrawler(config)

        with patch.object(httpx.Client, "get", side_effect=lambda u, **kw: mock_responses[str(u)]):
            result = crawler.crawl()

        # Only depth 0 and depth 1 crawled
        assert len(result.pages) == 2
        assert "https://testsite.com/depth2" not in result.pages
        assert result.stats.max_depth_reached == 1
