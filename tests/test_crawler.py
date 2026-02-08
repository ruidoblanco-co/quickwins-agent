"""Tests for crawler utilities (no network calls)."""

import sys
sys.path.insert(0, ".")

from core.crawler import (
    _parse_sitemap_xml,
    _sample_urls,
    extract_signals,
    PageSignals,
)


# ─── Sitemap Parsing ────────────────────────────────────────────


class TestParseSitemapXml:
    def test_url_sitemap(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/page1</loc></url>
            <url><loc>https://example.com/page2</loc></url>
        </urlset>"""
        urls, sitemaps = _parse_sitemap_xml(xml)
        assert len(urls) == 2
        assert sitemaps == []
        assert "https://example.com/page1" in urls

    def test_sitemap_index(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <sitemap><loc>https://example.com/sitemap-posts.xml</loc></sitemap>
            <sitemap><loc>https://example.com/sitemap-pages.xml</loc></sitemap>
        </sitemapindex>"""
        urls, sitemaps = _parse_sitemap_xml(xml)
        assert urls == []
        assert len(sitemaps) == 2

    def test_invalid_xml(self):
        urls, sitemaps = _parse_sitemap_xml("not xml at all")
        assert urls == []
        assert sitemaps == []

    def test_empty_xml(self):
        urls, sitemaps = _parse_sitemap_xml("")
        assert urls == []
        assert sitemaps == []


# ─── URL Sampling ───────────────────────────────────────────────


class TestSampleUrls:
    def test_includes_homepage(self):
        urls = ["https://example.com/a", "https://example.com/b"]
        sample = _sample_urls(urls, "https://example.com", max_pages=10)
        assert sample[0] == "https://example.com"

    def test_respects_max(self):
        urls = [f"https://example.com/{i}" for i in range(200)]
        sample = _sample_urls(urls, "https://example.com", max_pages=60)
        assert len(sample) <= 60

    def test_deduplicates(self):
        urls = ["https://example.com/a", "https://example.com/a", "https://example.com/b"]
        sample = _sample_urls(urls, "https://example.com", max_pages=10)
        normalized = [u for u in sample if "example.com/a" in u]
        assert len(normalized) <= 1  # homepage + at most 1 "a"

    def test_filters_images(self):
        urls = [
            "https://example.com/page",
            "https://example.com/photo.jpg",
            "https://example.com/logo.png",
        ]
        sample = _sample_urls(urls, "https://example.com", max_pages=10)
        for u in sample:
            assert not u.endswith(".jpg")
            assert not u.endswith(".png")

    def test_buckets_diversity(self):
        urls = [
            "https://example.com/blog/post-1",
            "https://example.com/blog/post-2",
            "https://example.com/products/item-1",
            "https://example.com/about",
        ]
        sample = _sample_urls(urls, "https://example.com", max_pages=5)
        buckets = set()
        for u in sample:
            path = u.replace("https://example.com", "").strip("/")
            if path:
                buckets.add(path.split("/")[0])
        # Should have at least blog, products, about
        assert len(buckets) >= 3


# ─── Signal Extraction ──────────────────────────────────────────


class TestExtractSignals:
    def test_basic_html(self):
        html = """
        <html>
        <head>
            <title>Test Page Title</title>
            <meta name="description" content="A test meta description.">
            <link rel="canonical" href="https://example.com/test">
        </head>
        <body>
            <h1>Main Heading</h1>
            <h2>Subheading</h2>
            <p>Some content here with enough words to count.</p>
            <a href="/other-page">Link</a>
        </body>
        </html>
        """
        signals = extract_signals(html, "https://example.com/test", "https://example.com/test", 200, "example.com")
        assert signals.title == "Test Page Title"
        assert signals.meta_description == "A test meta description."
        assert signals.canonical == "https://example.com/test"
        assert len(signals.h1s) == 1
        assert signals.h1s[0] == "Main Heading"
        assert len(signals.headings) >= 2
        assert signals.word_count > 0

    def test_missing_elements(self):
        html = "<html><head></head><body><p>Hello</p></body></html>"
        signals = extract_signals(html, "https://example.com/", "https://example.com/", 200, "example.com")
        assert signals.title == ""
        assert signals.meta_description == ""
        assert signals.canonical == ""
        assert len(signals.h1s) == 0

    def test_multiple_h1s(self):
        html = """
        <html><body>
            <h1>First H1</h1>
            <h1>Second H1</h1>
        </body></html>
        """
        signals = extract_signals(html, "https://example.com/", "https://example.com/", 200, "example.com")
        assert len(signals.h1s) == 2

    def test_noindex_detection(self):
        html = """
        <html><head>
            <meta name="robots" content="noindex, follow">
        </head><body></body></html>
        """
        signals = extract_signals(html, "https://example.com/", "https://example.com/", 200, "example.com")
        assert "noindex" in signals.robots_meta

    def test_schema_detection(self):
        html = """
        <html><head>
            <script type="application/ld+json">{"@type": "WebPage"}</script>
        </head><body></body></html>
        """
        signals = extract_signals(html, "https://example.com/", "https://example.com/", 200, "example.com")
        assert signals.has_schema is True

    def test_internal_links(self):
        html = """
        <html><body>
            <a href="https://example.com/page2">Internal</a>
            <a href="https://other.com/page">External</a>
            <a href="/relative">Relative</a>
        </body></html>
        """
        signals = extract_signals(html, "https://example.com/", "https://example.com/", 200, "example.com")
        # Should include internal and relative, not external
        internal_domains = set()
        for link in signals.internal_links:
            from utils.url_utils import normalize_domain
            internal_domains.add(normalize_domain(link))
        assert all(d == "example.com" for d in internal_domains)


class TestPageSignalsToDict:
    def test_serialization(self):
        signals = PageSignals(
            url="https://example.com/test",
            final_url="https://example.com/test",
            status=200,
            title="Test",
            h1s=["Heading"],
            headings=[(1, "Heading")],
            word_count=300,
        )
        d = signals.to_dict()
        assert d["url"] == "https://example.com/test"
        assert d["h1_count"] == 1
        assert d["word_count"] == 300
        assert "internal_link_count" in d
