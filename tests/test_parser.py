"""
Unit tests for PageParser.
Validates HTML parsing, title edge cases, meta descriptions, and link extraction.
"""

import pytest
from core.parser import PageParser


class TestPageParser:

    def test_standard_html_parsing(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>BashCraft Club - Home</title>
            <meta name="description" content="Official club website for web engineers.">
        </head>
        <body>
            <h1>Welcome to BashCraft</h1>
            <h2>Upcoming Events</h2>
            <a href="/about">About Us</a>
            <a href="https://github.com/BashCraftClub" target="_blank">GitHub</a>
            <script src="/assets/main.js"></script>
        </body>
        </html>
        """
        parsed = PageParser.parse(html, "https://bashcraftclub.vercel.app/")
        assert parsed.title == "BashCraft Club - Home"
        assert parsed.meta_description == "Official club website for web engineers."
        assert "Welcome to BashCraft" in parsed.h1
        assert "Upcoming Events" in parsed.h2
        assert len(parsed.raw_links) == 2
        assert parsed.raw_links[0]["href"] == "/about"
        assert parsed.raw_links[0]["anchor"] == "About Us"
        assert len(parsed.script_sources) == 1

    def test_missing_title_edge_case(self):
        html = "<html><body><h1>No Title Tag</h1></body></html>"
        parsed = PageParser.parse(html, "https://bashcraftclub.vercel.app/test")
        assert "Untitled" in parsed.title

    def test_whitespace_title_edge_case(self):
        html = "<html><head><title>   \n\t  </title></head><body></body></html>"
        parsed = PageParser.parse(html, "https://bashcraftclub.vercel.app/test")
        assert "Untitled" in parsed.title

    def test_spa_skeleton_detection(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Vite App</title><script type="module" src="/assets/index.js"></script></head>
        <body><div id="root"></div></body>
        </html>
        """
        parsed = PageParser.parse(html, "https://bashcraftclub.vercel.app/")
        assert parsed.is_spa_skeleton is True

