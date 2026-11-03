"""
Broken-Link Detection and Diagnostic Engine.
Checks internal and external link statuses, detects 404s, timeouts, and server errors,
and correlates failures with source pages and anchor text.
"""

import time
from typing import Dict, Optional, Tuple
import httpx
from core.models import DiscoveredLink, LinkStatus, LinkType


class LinkAuditor:
    """Verifies discovered links and diagnoses failure causes."""

    def __init__(self, timeout: float = 8.0, user_agent: str = "BashCraftSitemapBot/1.0"):
        self.timeout = timeout
        self.user_agent = user_agent
        # Cache results by URL to prevent redundant network requests
        self._cache: Dict[str, Tuple[int, LinkStatus, bool, Optional[str], float]] = {}

    def audit_link(
        self,
        link: DiscoveredLink,
        client: Optional[httpx.Client] = None
    ) -> DiscoveredLink:
        """Checks the HTTP status of a single link, populating status and diagnostic fields."""
        target_url = link.url

        # Check cache
        if target_url in self._cache:
            status_code, status, is_broken, reason, latency = self._cache[target_url]
            link.status_code = status_code
            link.status = status
            link.is_broken = is_broken
            link.error_reason = reason
            link.response_time_ms = latency
            return link

        headers = {"User-Agent": self.user_agent}
        start_time = time.perf_counter()

        def do_request(http_client: httpx.Client):
            try:
                # Try HEAD first for efficiency
                response = http_client.head(target_url, headers=headers, follow_redirects=True, timeout=self.timeout)
                # Some servers reject HEAD with 405 Method Not Allowed or 403; fall back to GET
                if response.status_code in (405, 403, 501):
                    response = http_client.get(target_url, headers=headers, follow_redirects=True, timeout=self.timeout)
                return response, None
            except httpx.TimeoutException:
                return None, "Connection timed out"
            except httpx.ConnectError:
                return None, "DNS resolution failed or connection refused"
            except httpx.HTTPStatusError as e:
                return e.response, f"HTTP Error {e.response.status_code}"
            except Exception as e:
                return None, str(e)

        resp = None
        error_msg = None

        if client:
            resp, error_msg = do_request(client)
        else:
            with httpx.Client() as local_client:
                resp, error_msg = do_request(local_client)

        latency = round((time.perf_counter() - start_time) * 1000, 2)

        if resp is not None:
            link.status_code = resp.status_code
            link.response_time_ms = latency

            if 200 <= resp.status_code < 300:
                link.status = LinkStatus.OK
                link.is_broken = False
                link.error_reason = None
            elif 300 <= resp.status_code < 400:
                link.status = LinkStatus.REDIRECT
                link.is_broken = False
                link.error_reason = f"Redirected ({resp.status_code})"
            elif resp.status_code == 404:
                link.status = LinkStatus.BROKEN
                link.is_broken = True
                link.error_reason = "404 Not Found"
            else:
                link.status = LinkStatus.BROKEN
                link.is_broken = True
                link.error_reason = f"HTTP Error {resp.status_code}"
        else:
            link.status_code = None
            link.response_time_ms = latency
            link.status = LinkStatus.TIMEOUT if "timed out" in (error_msg or "") else LinkStatus.ERROR
            link.is_broken = True
            link.error_reason = error_msg or "Failed to connect"

        # Cache result
        self._cache[target_url] = (
            link.status_code or 0,
            link.status,
            link.is_broken,
            link.error_reason,
            link.response_time_ms
        )

        return link
