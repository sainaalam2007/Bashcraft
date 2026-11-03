"""
Data models for the BashCraft Sitemap & Link Analyzer.
Provides strict Pydantic schemas for crawled pages, links, statistics, and graph representations.
"""

from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, ConfigDict


class LinkType(str, Enum):
    INTERNAL_PAGE = "internal_page"
    EXTERNAL = "external"
    ASSET = "asset"
    ANCHOR = "anchor"
    SPECIAL = "special"  # mailto, tel, javascript


class LinkStatus(str, Enum):
    OK = "ok"
    REDIRECT = "redirect"
    BROKEN = "broken"
    TIMEOUT = "timeout"
    ERROR = "error"
    UNCHECKED = "unchecked"


class DiscoveredLink(BaseModel):
    """Represents an individual link discovered on a page."""
    url: str
    original_href: str
    link_type: LinkType
    source_url: str
    anchor_text: str = ""
    status_code: Optional[int] = None
    status: LinkStatus = LinkStatus.UNCHECKED
    is_broken: bool = False
    error_reason: Optional[str] = None
    response_time_ms: Optional[float] = None


class PageNode(BaseModel):
    """Represents a discovered and analyzed webpage."""
    url: str
    canonical_url: str
    title: str = "Untitled Page"
    status_code: int = 200
    status_text: str = "OK"
    response_time_ms: float = 0.0
    content_type: str = "text/html"
    depth: int = 0
    discovered_via: Optional[str] = None
    meta_description: str = ""
    h1: List[str] = Field(default_factory=list)
    h2: List[str] = Field(default_factory=list)
    
    # Links discovered on this page
    internal_links: List[str] = Field(default_factory=list)
    external_links: List[str] = Field(default_factory=list)
    broken_links: List[DiscoveredLink] = Field(default_factory=list)
    
    # Counts
    inbound_links_count: int = 0
    outbound_internal_count: int = 0
    outbound_external_count: int = 0
    broken_links_count: int = 0


class CrawlStats(BaseModel):
    """Summary statistics for a completed crawl."""
    target_url: str
    start_time: str
    end_time: str
    duration_seconds: float
    pages_crawled: int = 0
    pages_discovered: int = 0
    total_internal_links: int = 0
    total_external_links: int = 0
    total_broken_links: int = 0
    average_response_time_ms: float = 0.0
    max_depth_reached: int = 0
    health_score: float = 100.0  # 0 to 100%


class GraphNode(BaseModel):
    id: str
    label: str
    title: str
    group: str
    status_code: int
    depth: int
    value: int = 1  # Node sizing based on inbound links


class GraphEdge(BaseModel):
    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    label: str = ""
    arrows: str = "to"

    model_config = ConfigDict(populate_by_name=True)


class CrawlResult(BaseModel):
    """Root container for all crawl results, exportable to JSON/XML/CSV."""
    base_url: str
    stats: CrawlStats
    pages: Dict[str, PageNode] = Field(default_factory=dict)
    all_broken_links: List[DiscoveredLink] = Field(default_factory=list)
    all_external_links: List[DiscoveredLink] = Field(default_factory=list)
    sitemap_tree: Dict[str, Any] = Field(default_factory=dict)
    graph_nodes: List[Dict[str, Any]] = Field(default_factory=list)
    graph_edges: List[Dict[str, Any]] = Field(default_factory=list)
