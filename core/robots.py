"""
Robots.txt Parser and Polite Crawler Compliance.
Parses robots.txt files, checks permission for target user-agents,
and extracts crawl-delay directives.
"""

from typing import Optional
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser
import httpx


class RobotsManager:
    """Manages robots.txt retrieval and access rules for the crawler."""

    def __init__(self, base_url: str, user_agent: str = "*", timeout: float = 5.0):
        self.base_url = base_url
        self.user_agent = user_agent
        self.timeout = timeout
        self.parser = RobotFileParser()
        self.is_loaded = False
        self.crawl_delay: Optional[float] = None

    def fetch_rules(self, client: Optional[httpx.Client] = None) -> None:
        """Attempts to fetch and parse robots.txt for the given site."""
        robots_url = urljoin(self.base_url, "/robots.txt")
        try:
            if client:
                res = client.get(robots_url, timeout=self.timeout)
                if res.status_code == 200:
                    self.parser.parse(res.text.splitlines())
                    self.is_loaded = True
                    try:
                        self.crawl_delay = self.parser.crawl_delay(self.user_agent)
                    except Exception:
                        self.crawl_delay = None
                    return
            else:
                with httpx.Client(follow_redirects=True) as local_client:
                    res = local_client.get(robots_url, timeout=self.timeout)
                    if res.status_code == 200:
                        self.parser.parse(res.text.splitlines())
                        self.is_loaded = True
                        try:
                            self.crawl_delay = self.parser.crawl_delay(self.user_agent)
                        except Exception:
                            self.crawl_delay = None
                        return
        except Exception:
            pass

        # If 404 or unreachable, default to unrestricted
        self.is_loaded = False

    def can_fetch(self, url: str) -> bool:
        """Checks if the crawler is permitted to fetch the given URL."""
        if not self.is_loaded:
            return True  # If no robots.txt, all pages are allowed
        try:
            return self.parser.can_fetch(self.user_agent, url)
        except Exception:
            return True
