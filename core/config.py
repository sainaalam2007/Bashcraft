"""
Configuration options for the crawler engine.
"""

from pydantic import BaseModel, Field


class CrawlConfig(BaseModel):
    """Configuration settings for web crawler execution."""
    start_url: str
    max_depth: int = Field(default=3, ge=1, le=10, description="Max tree crawl depth")
    max_pages: int = Field(default=50, ge=1, le=500, description="Max internal pages to fetch")
    timeout: float = Field(default=10.0, ge=1.0, le=60.0, description="HTTP request timeout in seconds")
    crawl_delay: float = Field(default=0.05, ge=0.0, le=5.0, description="Polite crawl delay between requests")
    respect_robots_txt: bool = Field(default=True, description="Whether to honor robots.txt directives")
    user_agent: str = Field(
        default="BashCraftSitemapBot/1.0 (+https://bashcraftclub.vercel.app/)",
        description="User-Agent string sent with requests"
    )
    check_broken_links: bool = Field(default=True, description="Verify status of all discovered links")
    spa_scan: bool = Field(
        default=True,
        description="Scan JavaScript bundles to extract dynamic Single-Page Application (SPA) routes"
    )
    check_external_status: bool = Field(
        default=False,
        description="Verify status codes for external links as well as internal ones"
    )
    concurrency: int = Field(default=4, ge=1, le=16, description="Parallel worker threads")
