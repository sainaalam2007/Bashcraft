"""
Core Web Crawler Engine for BashCraft Sitemap Analyzer.
Implements Breadth-First Search (BFS) graph traversal with loop prevention,
canonical URL tracking, concurrency control, polite delays, robots.txt compliance,
dynamic SPA route hydration, and broken-link auditing.
"""

import time
from collections import deque
from datetime import datetime
from typing import Dict, Set, List, Optional, Callable, Any, Tuple
from urllib.parse import urlparse
import httpx

from core.config import CrawlConfig
from core.models import (
    PageNode, DiscoveredLink, LinkType, LinkStatus,
    CrawlStats, CrawlResult, GraphNode, GraphEdge
)
from core.normalizer import URLNormalizer
from core.parser import PageParser
from core.robots import RobotsManager
from core.spa_analyzer import SPAAnalyzer
from core.auditor import LinkAuditor


class WebCrawler:
    """Production-grade Web Crawler and Sitemap Generator."""

    def __init__(self, config: CrawlConfig):
        self.config = config
        self.normalized_start_url = URLNormalizer.normalize(config.start_url)
        if not self.normalized_start_url:
            raise ValueError(f"Invalid start URL: {config.start_url}")

        self.base_domain = URLNormalizer.get_domain(self.normalized_start_url)
        self.auditor = LinkAuditor(timeout=config.timeout, user_agent=config.user_agent)
        self.robots = RobotsManager(
            base_url=self.normalized_start_url,
            user_agent=config.user_agent,
            timeout=config.timeout
        )

        # Crawler State
        self.pages: Dict[str, PageNode] = {}
        self.visited_urls: Set[str] = set()
        self.all_broken_links: List[DiscoveredLink] = []
        self.all_external_links: List[DiscoveredLink] = []
        self.seen_external_urls: Set[str] = set()
        self.seen_script_urls: Set[str] = set()
        self.edges: List[Dict[str, str]] = []  # [{from: ..., to: ...}]

    def crawl(
        self,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> CrawlResult:
        """
        Executes the crawl starting from start_url.
        Emits real-time progress events to progress_callback if provided.
        """
        start_time_iso = datetime.now().isoformat()
        start_time_perf = time.perf_counter()

        def notify(event_type: str, data: Dict[str, Any]):
            if progress_callback:
                progress_callback({"event": event_type, "timestamp": time.time(), **data})

        notify("start", {"target_url": self.normalized_start_url})

        # Step 1: Robots.txt
        if self.config.respect_robots_txt:
            notify("status", {"message": "Checking robots.txt..."})
            self.robots.fetch_rules()
            if self.robots.crawl_delay:
                self.config.crawl_delay = max(self.config.crawl_delay, self.robots.crawl_delay)

        # Step 2: Initialize BFS Queue: (url, depth, referrer)
        queue = deque([(self.normalized_start_url, 0, None)])
        self.visited_urls.add(self.normalized_start_url)

        headers = {
            "User-Agent": self.config.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        with httpx.Client(headers=headers, follow_redirects=True, timeout=self.config.timeout) as client:
            while queue and len(self.pages) < self.config.max_pages:
                current_url, depth, referrer = queue.popleft()

                notify("crawling", {
                    "url": current_url,
                    "depth": depth,
                    "crawled_count": len(self.pages),
                    "queue_size": len(queue)
                })

                # Respect robots.txt
                if self.config.respect_robots_txt and not self.robots.can_fetch(current_url):
                    notify("skipped", {"url": current_url, "reason": "Disallowed by robots.txt"})
                    continue

                # Polite delay
                if self.config.crawl_delay > 0:
                    time.sleep(self.config.crawl_delay)

                req_start = time.perf_counter()
                try:
                    response = client.get(current_url)
                    latency = round((time.perf_counter() - req_start) * 1000, 2)
                    status_code = response.status_code
                    content_type = response.headers.get("content-type", "")
                    html_content = response.text if "text/html" in content_type or len(response.text) > 0 else ""
                except httpx.TimeoutException:
                    latency = round((time.perf_counter() - req_start) * 1000, 2)
                    self._record_broken_page(current_url, depth, referrer, "Request Timeout", latency)
                    continue
                except httpx.ConnectError:
                    latency = round((time.perf_counter() - req_start) * 1000, 2)
                    self._record_broken_page(current_url, depth, referrer, "Connection Refused / DNS Error", latency)
                    continue
                except Exception as e:
                    latency = round((time.perf_counter() - req_start) * 1000, 2)
                    self._record_broken_page(current_url, depth, referrer, str(e), latency)
                    continue

                # Parse the HTML content
                parsed_dom = PageParser.parse(html_content, current_url)

                page_node = PageNode(
                    url=current_url,
                    canonical_url=current_url,
                    title=parsed_dom.title,
                    status_code=status_code,
                    status_text=response.reason_phrase if hasattr(response, "reason_phrase") else "OK",
                    response_time_ms=latency,
                    content_type=content_type.split(";")[0],
                    depth=depth,
                    discovered_via=referrer,
                    meta_description=parsed_dom.meta_description,
                    h1=parsed_dom.h1,
                    h2=parsed_dom.h2
                )

                # Process Links found in DOM
                for link_item in parsed_dom.raw_links:
                    raw_href = link_item["href"]
                    anchor = link_item["anchor"]

                    category, resolved = URLNormalizer.classify_href(raw_href, current_url)

                    if category == "internal_page" and resolved:
                        if resolved not in page_node.internal_links:
                            page_node.internal_links.append(resolved)
                        self.edges.append({"from": current_url, "to": resolved})

                        # Enqueue internal page if unvisited and within depth limit
                        if resolved not in self.visited_urls:
                            self.visited_urls.add(resolved)
                            if depth + 1 <= self.config.max_depth:
                                queue.append((resolved, depth + 1, current_url))

                    elif category == "external" and resolved:
                        if resolved not in page_node.external_links:
                            page_node.external_links.append(resolved)
                        if resolved not in self.seen_external_urls:
                            self.seen_external_urls.add(resolved)
                            ext_link = DiscoveredLink(
                                url=resolved,
                                original_href=raw_href,
                                link_type=LinkType.EXTERNAL,
                                source_url=current_url,
                                anchor_text=anchor
                            )
                            if self.config.check_external_status:
                                self.auditor.audit_link(ext_link, client=client)
                            self.all_external_links.append(ext_link)

                # Check SPA dynamic script bundles
                if self.config.spa_scan:
                    for script_url in parsed_dom.script_sources:
                        if script_url not in self.seen_script_urls and URLNormalizer.is_internal(script_url, self.normalized_start_url):
                            self.seen_script_urls.add(script_url)
                            try:
                                js_resp = client.get(script_url)
                                if js_resp.status_code == 200:
                                    discovery = SPAAnalyzer.analyze_script(js_resp.text, self.normalized_start_url)
                                    
                                    # Add SPA discovered internal routes
                                    for spa_route in discovery.internal_routes:
                                        if spa_route not in page_node.internal_links:
                                            page_node.internal_links.append(spa_route)
                                        self.edges.append({"from": current_url, "to": spa_route})
                                        if spa_route not in self.visited_urls:
                                            self.visited_urls.add(spa_route)
                                            if depth + 1 <= self.config.max_depth:
                                                queue.append((spa_route, depth + 1, current_url))

                                    # Add SPA discovered external links
                                    for ext_url in discovery.external_links:
                                        if ext_url not in self.seen_external_urls:
                                            self.seen_external_urls.add(ext_url)
                                            ext_link = DiscoveredLink(
                                                url=ext_url,
                                                original_href=ext_url,
                                                link_type=LinkType.EXTERNAL,
                                                source_url=current_url,
                                                anchor_text="SPA Navigation"
                                            )
                                            self.all_external_links.append(ext_link)
                            except Exception:
                                pass

                # Broken link detection on page's internal links
                if self.config.check_broken_links:
                    for int_url in page_node.internal_links:
                        link_obj = DiscoveredLink(
                            url=int_url,
                            original_href=int_url,
                            link_type=LinkType.INTERNAL_PAGE,
                            source_url=current_url
                        )
                        self.auditor.audit_link(link_obj, client=client)
                        if link_obj.is_broken:
                            page_node.broken_links.append(link_obj)
                            self.all_broken_links.append(link_obj)

                # Set counts
                page_node.outbound_internal_count = len(page_node.internal_links)
                page_node.outbound_external_count = len(page_node.external_links)
                page_node.broken_links_count = len(page_node.broken_links)

                self.pages[current_url] = page_node

        # Compute inbound link counts
        for src_url, page in self.pages.items():
            for target_url in page.internal_links:
                if target_url in self.pages:
                    self.pages[target_url].inbound_links_count += 1

        duration = round(time.perf_counter() - start_time_perf, 2)
        end_time_iso = datetime.now().isoformat()

        # Build Graph and Tree structures
        graph_nodes, graph_edges = self._build_graph_data()
        sitemap_tree = self._build_sitemap_tree()

        # Calculate SEO Health Score (0 - 100%)
        health_score = self._calculate_health_score()

        # Total counts
        total_internal = sum(len(p.internal_links) for p in self.pages.values())
        avg_latency = (
            round(sum(p.response_time_ms for p in self.pages.values()) / len(self.pages), 2)
            if self.pages else 0.0
        )
        max_depth = max((p.depth for p in self.pages.values()), default=0)

        stats = CrawlStats(
            target_url=self.normalized_start_url,
            start_time=start_time_iso,
            end_time=end_time_iso,
            duration_seconds=duration,
            pages_crawled=len(self.pages),
            pages_discovered=len(self.visited_urls),
            total_internal_links=total_internal,
            total_external_links=len(self.all_external_links),
            total_broken_links=len(self.all_broken_links),
            average_response_time_ms=avg_latency,
            max_depth_reached=max_depth,
            health_score=health_score
        )

        result = CrawlResult(
            base_url=self.normalized_start_url,
            stats=stats,
            pages=self.pages,
            all_broken_links=self.all_broken_links,
            all_external_links=self.all_external_links,
            sitemap_tree=sitemap_tree,
            graph_nodes=graph_nodes,
            graph_edges=graph_edges
        )

        notify("complete", {"stats": stats.model_dump()})
        return result

    def _record_broken_page(self, url: str, depth: int, referrer: Optional[str], reason: str, latency: float):
        """Records an unreachable internal page as broken."""
        link = DiscoveredLink(
            url=url,
            original_href=url,
            link_type=LinkType.INTERNAL_PAGE,
            source_url=referrer or "Root",
            status_code=None,
            status=LinkStatus.ERROR,
            is_broken=True,
            error_reason=reason,
            response_time_ms=latency
        )
        self.all_broken_links.append(link)

        # Add placeholder page node
        self.pages[url] = PageNode(
            url=url,
            canonical_url=url,
            title=f"Error: {reason}",
            status_code=0,
            status_text="Failed",
            response_time_ms=latency,
            depth=depth,
            discovered_via=referrer,
            broken_links_count=1
        )

    def _calculate_health_score(self) -> float:
        """Calculates a comprehensive site quality and SEO health score (0 - 100%)."""
        if not self.pages:
            return 0.0

        score = 100.0
        total_pages = len(self.pages)

        # Deduct for broken links (-5 points per broken link, max -40)
        broken_penalty = min(len(self.all_broken_links) * 5.0, 40.0)
        score -= broken_penalty

        # Deduct for missing titles (-2 points per page without proper title)
        missing_titles = sum(1 for p in self.pages.values() if not p.title or "Untitled" in p.title)
        title_penalty = (missing_titles / total_pages) * 20.0
        score -= title_penalty

        # Deduct for missing meta descriptions (-1 point per page)
        missing_meta = sum(1 for p in self.pages.values() if not p.meta_description)
        meta_penalty = (missing_meta / total_pages) * 15.0
        score -= meta_penalty

        # Deduct for slow pages (> 1000ms latency)
        slow_pages = sum(1 for p in self.pages.values() if p.response_time_ms > 1000)
        speed_penalty = (slow_pages / total_pages) * 10.0
        score -= speed_penalty

        return max(round(score, 1), 0.0)

    def _build_graph_data(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Constructs node and edge arrays formatted for Vis.js Network graph visualization."""
        nodes = []
        edges_set = set()
        edges = []

        for url, page in self.pages.items():
            parsed = urlparse(url)
            path_label = parsed.path if parsed.path else "/"
            if len(path_label) > 25:
                path_label = path_label[:22] + "..."

            # Group by status
            if page.status_code == 0 or page.broken_links_count > 0:
                group = "broken"
            elif page.depth == 0:
                group = "root"
            else:
                group = "ok"

            node_title = (
                f"<b>URL:</b> {page.url}<br/>"
                f"<b>Title:</b> {page.title}<br/>"
                f"<b>Status:</b> {page.status_code} ({page.status_text})<br/>"
                f"<b>Depth:</b> {page.depth}<br/>"
                f"<b>Inbound Links:</b> {page.inbound_links_count}<br/>"
                f"<b>Outbound Internal:</b> {page.outbound_internal_count}<br/>"
                f"<b>Response Time:</b> {page.response_time_ms} ms"
            )

            nodes.append({
                "id": page.url,
                "label": path_label,
                "title": node_title,
                "group": group,
                "value": max(page.inbound_links_count + 1, 1),
                "depth": page.depth,
                "status_code": page.status_code,
                "page_title": page.title
            })

        for edge in self.edges:
            src = edge["from"]
            dst = edge["to"]
            if src in self.pages and dst in self.pages and (src, dst) not in edges_set:
                edges_set.add((src, dst))
                edges.append({
                    "from": src,
                    "to": dst,
                    "arrows": "to"
                })

        return nodes, edges

    def _build_sitemap_tree(self) -> Dict[str, Any]:
        """Constructs a nested hierarchical tree dictionary representing directory paths."""
        tree = {
            "name": self.base_domain,
            "url": self.normalized_start_url,
            "title": self.pages.get(self.normalized_start_url, PageNode(url="", canonical_url="")).title,
            "children": [],
            "depth": 0
        }

        # Organize pages by URL path depth
        sorted_pages = sorted(self.pages.values(), key=lambda p: (p.depth, p.url))

        # Build path-based tree lookup
        path_map: Dict[str, Dict[str, Any]] = {"/": tree}

        for page in sorted_pages:
            parsed = urlparse(page.url)
            path = parsed.path or "/"
            if path == "/":
                continue

            segments = [s for s in path.strip("/").split("/") if s]
            current_path = ""
            parent_node = tree

            for i, seg in enumerate(segments):
                current_path += "/" + seg
                if current_path not in path_map:
                    is_leaf = (i == len(segments) - 1)
                    new_node = {
                        "name": "/" + seg,
                        "url": page.url if is_leaf else "",
                        "title": page.title if is_leaf else seg.capitalize(),
                        "status_code": page.status_code if is_leaf else 200,
                        "depth": i + 1,
                        "children": []
                    }
                    path_map[current_path] = new_node
                    parent_node["children"].append(new_node)
                parent_node = path_map[current_path]

        return tree
