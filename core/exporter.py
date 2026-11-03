"""
Multi-Format Sitemap and Audit Report Exporter.
Supports:
1. Standard XML Sitemap (W3C/Google protocol 0.9)
2. Comprehensive JSON
3. Tabular CSV (Pages and Broken Links)
4. Formatted Markdown Audit Report
"""

import csv
import io
import json
from datetime import datetime
from typing import Dict, Any
import xml.etree.ElementTree as ET
from xml.dom import minidom

from core.models import CrawlResult


class SitemapExporter:
    """Exports CrawlResult to XML, JSON, CSV, and Markdown formats."""

    @staticmethod
    def to_json(result: CrawlResult, indent: int = 2) -> str:
        """Serializes the full crawl result to formatted JSON string."""
        return result.model_dump_json(indent=indent)

    @staticmethod
    def to_xml(result: CrawlResult) -> str:
        """
        Generates standard XML sitemap compliant with sitemaps.org protocol 0.9.
        Dynamically assigns priority and changefreq based on page depth.
        """
        urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
        today_iso = datetime.now().strftime("%Y-%m-%d")

        for url, page in result.pages.items():
            # Skip failed pages from the public XML sitemap
            if page.status_code != 200:
                continue

            url_elem = ET.SubElement(urlset, "url")

            loc = ET.SubElement(url_elem, "loc")
            loc.text = url

            lastmod = ET.SubElement(url_elem, "lastmod")
            lastmod.text = today_iso

            changefreq = ET.SubElement(url_elem, "changefreq")
            changefreq.text = "daily" if page.depth == 0 else "weekly"

            priority = ET.SubElement(url_elem, "priority")
            # Calculate priority based on depth: 1.0 for root, decreasing with depth
            calc_priority = max(1.0 - (page.depth * 0.2), 0.2)
            priority.text = f"{calc_priority:.1f}"

        rough_string = ET.tostring(urlset, "utf-8")
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ", encoding="UTF-8").decode("utf-8")

    @staticmethod
    def to_pages_csv(result: CrawlResult) -> str:
        """Exports crawled pages list to CSV."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "URL", "Title", "Status Code", "Status", "Depth",
            "Latency (ms)", "Inbound Links", "Outbound Internal",
            "Outbound External", "Broken Links Count", "Meta Description"
        ])

        for page in result.pages.values():
            writer.writerow([
                page.url,
                page.title,
                page.status_code,
                page.status_text,
                page.depth,
                page.response_time_ms,
                page.inbound_links_count,
                page.outbound_internal_count,
                page.outbound_external_count,
                page.broken_links_count,
                page.meta_description
            ])

        return output.getvalue()

    @staticmethod
    def to_broken_links_csv(result: CrawlResult) -> str:
        """Exports detected broken links to a dedicated CSV audit file."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Broken URL", "Original Href", "Link Type",
            "Discovered On (Referrer)", "Status Code", "Failure Reason", "Anchor Text"
        ])

        for link in result.all_broken_links:
            writer.writerow([
                link.url,
                link.original_href,
                link.link_type.value,
                link.source_url,
                link.status_code if link.status_code else "N/A",
                link.error_reason or "Unknown",
                link.anchor_text
            ])

        return output.getvalue()

    @staticmethod
    def to_markdown_report(result: CrawlResult) -> str:
        """Generates a professional Markdown audit and sitemap summary report."""
        stats = result.stats
        md = []

        md.append(f"# 🗺️ BashCraft Website Sitemap & Health Audit Report\n")
        md.append(f"**Target URL:** `{result.base_url}`  ")
        md.append(f"**Crawl Date:** `{stats.start_time}`  ")
        md.append(f"**Duration:** `{stats.duration_seconds}s`  ")
        md.append(f"**SEO / Health Score:** **{stats.health_score}/100**\n")

        md.append("## 📊 Summary Statistics\n")
        md.append("| Metric | Value |")
        md.append("| :--- | :--- |")
        md.append(f"| Pages Crawled | **{stats.pages_crawled}** |")
        md.append(f"| Pages Discovered | **{stats.pages_discovered}** |")
        md.append(f"| Internal Links | **{stats.total_internal_links}** |")
        md.append(f"| External Links | **{stats.total_external_links}** |")
        md.append(f"| Broken Links | **{stats.total_broken_links}** |")
        md.append(f"| Average Latency | **{stats.average_response_time_ms} ms** |")
        md.append(f"| Max Depth | **{stats.max_depth_reached}** |\n")

        md.append("## 📑 Discovered Pages Hierarchy\n")
        md.append("| Status | Depth | Title | URL | Latency | Links (In/Out) |")
        md.append("| :---: | :---: | :--- | :--- | :---: | :---: |")

        for page in sorted(result.pages.values(), key=lambda p: (p.depth, p.url)):
            status_badge = "🟢 200" if page.status_code == 200 else f"🔴 {page.status_code}"
            links_summary = f"{page.inbound_links_count} in / {page.outbound_internal_count} int / {page.outbound_external_count} ext"
            md.append(f"| {status_badge} | {page.depth} | {page.title[:35]} | [`{page.url}`]({page.url}) | {page.response_time_ms}ms | {links_summary} |")

        md.append("\n")

        if result.all_broken_links:
            md.append("## ⚠️ Broken Link Diagnostics\n")
            md.append("| Target Broken URL | HTTP Status / Reason | Source Page | Anchor / Context |")
            md.append("| :--- | :--- | :--- | :--- |")
            for bl in result.all_broken_links:
                md.append(f"| `{bl.url}` | **{bl.error_reason or bl.status_code}** | [`{bl.source_url}`]({bl.source_url}) | *{bl.anchor_text or 'N/A'}* |")
            md.append("\n")
        else:
            md.append("## ✅ Broken Link Diagnostics\n")
            md.append("🎉 **No broken links detected! All internal routes resolved successfully.**\n")

        if result.all_external_links:
            md.append("## 🌐 Discovered External Links\n")
            md.append(f"Found **{len(result.all_external_links)}** outbound external links:\n")
            for ext in result.all_external_links[:20]:
                md.append(f"- [`{ext.url}`]({ext.url}) (Referenced on: `{ext.source_url}`)")
            if len(result.all_external_links) > 20:
                md.append(f"- *...and {len(result.all_external_links) - 20} more external links.*")
            md.append("\n")

        md.append("---\n*Generated automatically by BashCraft Sitemap Analyzer.*")
        return "\n".join(md)
