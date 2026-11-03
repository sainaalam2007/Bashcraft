"""
Unit tests for SitemapExporter.
Validates XML standard formatting, JSON serialization, CSV columns, and Markdown output.
"""

import json
import xml.etree.ElementTree as ET
from datetime import datetime
import pytest

from core.models import CrawlResult, CrawlStats, PageNode, DiscoveredLink, LinkType, LinkStatus
from core.exporter import SitemapExporter


@pytest.fixture
def sample_crawl_result():
    pages = {
        "https://example.com/": PageNode(
            url="https://example.com/",
            canonical_url="https://example.com/",
            title="Example Home",
            status_code=200,
            depth=0,
            response_time_ms=45.2,
            internal_links=["https://example.com/about"],
            external_links=["https://github.com/example"]
        ),
        "https://example.com/about": PageNode(
            url="https://example.com/about",
            canonical_url="https://example.com/about",
            title="About Us",
            status_code=200,
            depth=1,
            response_time_ms=52.1
        )
    }

    broken = [
        DiscoveredLink(
            url="https://example.com/broken",
            original_href="/broken",
            link_type=LinkType.INTERNAL_PAGE,
            source_url="https://example.com/",
            status_code=404,
            status=LinkStatus.BROKEN,
            is_broken=True,
            error_reason="404 Not Found"
        )
    ]

    stats = CrawlStats(
        target_url="https://example.com/",
        start_time=datetime.now().isoformat(),
        end_time=datetime.now().isoformat(),
        duration_seconds=1.2,
        pages_crawled=2,
        pages_discovered=2,
        total_internal_links=1,
        total_external_links=1,
        total_broken_links=1,
        average_response_time_ms=48.65,
        max_depth_reached=1,
        health_score=95.0
    )

    return CrawlResult(
        base_url="https://example.com/",
        stats=stats,
        pages=pages,
        all_broken_links=broken,
        all_external_links=[]
    )


class TestSitemapExporter:

    def test_xml_sitemap_compliance(self, sample_crawl_result):
        xml_str = SitemapExporter.to_xml(sample_crawl_result)
        assert "<urlset" in xml_str
        assert "http://www.sitemaps.org/schemas/sitemap/0.9" in xml_str

        # Parse XML to verify well-formedness
        root = ET.fromstring(xml_str)
        assert root.tag.endswith("urlset")
        locs = [elem.text for elem in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
        assert "https://example.com/" in locs
        assert "https://example.com/about" in locs

    def test_json_export(self, sample_crawl_result):
        json_str = SitemapExporter.to_json(sample_crawl_result)
        data = json.loads(json_str)
        assert data["base_url"] == "https://example.com/"
        assert len(data["pages"]) == 2
        assert len(data["all_broken_links"]) == 1

    def test_csv_exports(self, sample_crawl_result):
        pages_csv = SitemapExporter.to_pages_csv(sample_crawl_result)
        assert "URL,Title,Status Code" in pages_csv
        assert "https://example.com/" in pages_csv

        broken_csv = SitemapExporter.to_broken_links_csv(sample_crawl_result)
        assert "Broken URL,Original Href" in broken_csv
        assert "https://example.com/broken" in broken_csv

    def test_markdown_report(self, sample_crawl_result):
        md = SitemapExporter.to_markdown_report(sample_crawl_result)
        assert "# 🗺️ BashCraft Website Sitemap" in md
        assert "95.0/100" in md
        assert "Broken Link Diagnostics" in md
