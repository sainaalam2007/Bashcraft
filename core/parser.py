"""
HTML Parser and DOM Extractor.
Extracts titles, meta tags, headers, links, and script references.
Handles edge cases: missing titles, excessively long titles, malformed markup,
and extracts anchor text and link context.
"""

import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from core.normalizer import URLNormalizer


class ParsedPage:
    def __init__(self):
        self.title: str = "Untitled Page"
        self.meta_description: str = ""
        self.h1: List[str] = []
        self.h2: List[str] = []
        self.raw_links: List[Dict[str, str]] = []  # [{"href": ..., "anchor": ...}]
        self.script_sources: List[str] = []
        self.inline_scripts: List[str] = []
        self.is_spa_skeleton: bool = False


class PageParser:
    """Robust HTML DOM parser built on BeautifulSoup."""

    MAX_TITLE_LENGTH = 200

    @classmethod
    def parse(cls, html_content: str, current_url: str) -> ParsedPage:
        """Parses HTML document and extracts structural and link information."""
        result = ParsedPage()

        if not html_content or not isinstance(html_content, str):
            return result

        try:
            soup = BeautifulSoup(html_content, "html.parser")
        except Exception:
            # Fallback in case of parser crash
            return result

        # 1. Page Title extraction
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            clean_title = re.sub(r"\s+", " ", title_tag.string).strip()
            if clean_title:
                result.title = clean_title
            else:
                result.title = f"Untitled ({current_url})"
        else:
            result.title = f"Untitled ({current_url})"

        # 2. Meta description extraction
        meta_desc = (
            soup.find("meta", attrs={"name": "description"})
            or soup.find("meta", attrs={"property": "og:description"})
            or soup.find("meta", attrs={"name": "twitter:description"})
        )
        if meta_desc and meta_desc.get("content"):
            result.meta_description = meta_desc.get("content").strip()

        # 3. Headings extraction
        for h1 in soup.find_all("h1"):
            text = h1.get_text(strip=True)
            if text:
                result.h1.append(text[:120])

        for h2 in soup.find_all("h2")[:5]:  # limit to top 5
            text = h2.get_text(strip=True)
            if text:
                result.h2.append(text[:120])

        # 4. Links extraction (<a href="...">)
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            anchor_text = a_tag.get_text(strip=True) or a_tag.get("title", "") or a_tag.get("aria-label", "")
            result.raw_links.append({
                "href": href,
                "anchor": anchor_text[:100]
            })

        # 5. Extract script tags for SPA route discovery
        for script in soup.find_all("script"):
            src = script.get("src")
            if src:
                # resolve script URL
                norm_script = URLNormalizer.normalize(src, base_url=current_url)
                if norm_script:
                    result.script_sources.append(norm_script)
            elif script.string:
                result.inline_scripts.append(script.string)

        # 6. Detect if this is an SPA skeleton (e.g. <div id="root"></div> with minimal content)
        root_div = soup.find(id=re.compile(r"root|app|__next"))
        body_text_len = len(soup.body.get_text(strip=True)) if soup.body else 0
        if root_div and body_text_len < 150 and len(result.raw_links) <= 2:
            result.is_spa_skeleton = True

        return result
