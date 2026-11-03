"""
JavaScript SPA Bundle Analyzer and Client-Side Route Extractor.
Extracts client-side routes, navigation paths, and embedded links from
React Router, Vue Router, Next.js, and Vite/Webpack bundles.
Enables comprehensive crawling of Single Page Applications (SPAs) like BashCraft.
"""

import re
from typing import Set, List, Dict, Tuple
from core.normalizer import URLNormalizer


class SPARouteDiscovery:
    def __init__(self):
        self.internal_routes: Set[str] = set()
        self.external_links: Set[str] = set()
        self.special_links: Set[str] = set()  # mailto, tel


class SPAAnalyzer:
    """Dissects JavaScript bundles to discover dynamic routes and links."""

    # Patterns matching router definitions
    ROUTE_PATTERNS = [
        # React Router path: "/about" or path: '/team/:teamId'
        re.compile(r'path\s*:\s*["\']([^"\'*\s]+)["\']', re.IGNORECASE),
        # React Router <Route path="/about">
        re.compile(r'<Route[^>]*path=["\']([^"\'*\s]+)["\']', re.IGNORECASE),
        # Navigation targets <Link to="/team"> or navigate("/events")
        re.compile(r'to\s*:\s*["\'](/[a-zA-Z0-9_\-\./:]+)["\']', re.IGNORECASE),
        re.compile(r'navigate\(\s*["\'](/[a-zA-Z0-9_\-\./:]+)["\']', re.IGNORECASE),
        # href attributes in JSX/templates: href: "/events"
        re.compile(r'href\s*:\s*["\'](/[a-zA-Z0-9_\-\./:]+)["\']', re.IGNORECASE),
    ]

    # Patterns matching external URLs in JS
    EXTERNAL_URL_PATTERN = re.compile(
        r'https?://[a-zA-Z0-9_\-\.]+(?:\.[a-zA-Z]{2,})+(?:/[a-zA-Z0-9_\-\./#\?&=%]*)?'
    )

    # Patterns matching email/tel
    SPECIAL_PATTERN = re.compile(r'(?:mailto|tel):[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')

    # Ignored technical / library paths
    IGNORED_PATHS = {
        "/", "/assets", "/node_modules", "/src", "/dist", "/public", "/api",
        "/favicon.ico", "/robots.txt", "/sitemap.xml", "/manifest.json"
    }

    @classmethod
    def analyze_script(cls, script_content: str, base_url: str) -> SPARouteDiscovery:
        """Analyzes JavaScript source code and extracts discovered routes and links."""
        discovery = SPARouteDiscovery()

        if not script_content or not isinstance(script_content, str):
            return discovery

        # 1. Discover client-side internal routes
        for pattern in cls.ROUTE_PATTERNS:
            for match in pattern.findall(script_content):
                route = match.strip()
                if not route or route in cls.IGNORED_PATHS:
                    continue

                # Ensure starts with /
                if not route.startswith("/"):
                    route = "/" + route

                # Skip asset paths, params with colons like /team/:teamId
                if ":" in route or route.startswith("/assets") or "." in route.split("/")[-1]:
                    # If it's a param route like /team/:teamId, we can still note /team
                    base_param = route.split("/:")[0]
                    if base_param and base_param != "/":
                        norm = URLNormalizer.normalize(base_param, base_url=base_url)
                        if norm:
                            discovery.internal_routes.add(norm)
                    continue

                normalized_route = URLNormalizer.normalize(route, base_url=base_url)
                if normalized_route and URLNormalizer.is_internal(normalized_route, base_url):
                    discovery.internal_routes.add(normalized_route)

        # 2. Discover external links embedded in JS
        for match in cls.EXTERNAL_URL_PATTERN.findall(script_content):
            url = match.strip()
            # Exclude framework schemas & spec URLs (e.g. w3.org, reactjs.org error decoder)
            if any(tech in url for tech in ["w3.org", "reactjs.org", "schema.org", "xmlns"]):
                continue

            normalized_ext = URLNormalizer.normalize(url, base_url=base_url)
            if normalized_ext:
                if URLNormalizer.is_internal(normalized_ext, base_url):
                    discovery.internal_routes.add(normalized_ext)
                else:
                    discovery.external_links.add(normalized_ext)

        # 3. Discover special links (e.g. mailto)
        for match in cls.SPECIAL_PATTERN.findall(script_content):
            discovery.special_links.add(match.strip())

        return discovery
