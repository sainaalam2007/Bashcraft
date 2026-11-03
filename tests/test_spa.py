"""
Unit tests for SPAAnalyzer.
Validates client-side route extraction from modern JS bundle patterns.
"""

import pytest
from core.spa_analyzer import SPAAnalyzer


class TestSPAAnalyzer:

    def test_extract_routes_and_links(self):
        js_code = """
        const routes = [
            { path: "/", element: <Home /> },
            { path: "/about", element: <About /> },
            { path: "/events", element: <Events /> },
            { path: "/events/bashnex26", element: <Bashnex /> },
            { path: "/team/:teamId", element: <TeamMember /> },
            { path: "/contact", element: <Contact /> }
        ];
        const socials = {
            github: "https://github.com/BashCraftClub",
            insta: "https://www.instagram.com/bashcraft.vit/",
            mail: "mailto:bashcraft@vitbhopal.ac.in"
        };
        """
        base = "https://bashcraftclub.vercel.app"
        discovery = SPAAnalyzer.analyze_script(js_code, base)

        # Internal routes verified
        assert "https://bashcraftclub.vercel.app/about" in discovery.internal_routes
        assert "https://bashcraftclub.vercel.app/events" in discovery.internal_routes
        assert "https://bashcraftclub.vercel.app/events/bashnex26" in discovery.internal_routes
        assert "https://bashcraftclub.vercel.app/contact" in discovery.internal_routes
        assert "https://bashcraftclub.vercel.app/team" in discovery.internal_routes

        # External links verified
        assert "https://github.com/BashCraftClub" in discovery.external_links
        assert "https://www.instagram.com/bashcraft.vit" in discovery.external_links

        # Special links verified
        assert "mailto:bashcraft@vitbhopal.ac.in" in discovery.special_links
