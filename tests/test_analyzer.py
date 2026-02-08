"""Tests for the SEO issue analyzer."""

import sys
sys.path.insert(0, ".")

from core.analyzer import (
    analyze,
    _detect_duplicate_titles,
    _detect_missing_titles,
    _detect_duplicate_metas,
    _detect_missing_metas,
    _detect_thin_content,
    _detect_missing_h1,
    _detect_multiple_h1,
    _detect_broken_hierarchy,
    _detect_broken_links,
    _detect_redirect_chains,
    _detect_orphan_pages,
    _detect_missing_canonical,
    _detect_incorrect_canonical,
    _detect_noindex_issues,
    _calculate_score,
)


def _make_page(**kwargs):
    """Helper to create a mock page object as a dict."""
    defaults = {
        "url": "https://example.com/page",
        "final_url": "https://example.com/page",
        "status": 200,
        "error": "",
        "title": "Default Title",
        "meta_description": "Default meta description for testing.",
        "canonical": "https://example.com/page",
        "robots_meta": "",
        "h1s": ["Main Heading"],
        "h1_count": 1,
        "headings": [(1, "Main Heading"), (2, "Subheading")],
        "word_count": 500,
        "internal_links": [],
        "has_schema": False,
        "has_hreflang": False,
    }
    defaults.update(kwargs)
    return defaults


# ─── Content Issues ─────────────────────────────────────────────


class TestDuplicateTitles:
    def test_no_duplicates(self):
        pages = [
            _make_page(url="https://example.com/a", final_url="https://example.com/a", title="Title A"),
            _make_page(url="https://example.com/b", final_url="https://example.com/b", title="Title B"),
        ]
        assert _detect_duplicate_titles(pages) == []

    def test_finds_duplicates(self):
        pages = [
            _make_page(url="https://example.com/a", final_url="https://example.com/a", title="Same Title"),
            _make_page(url="https://example.com/b", final_url="https://example.com/b", title="Same Title"),
            _make_page(url="https://example.com/c", final_url="https://example.com/c", title="Unique"),
        ]
        issues = _detect_duplicate_titles(pages)
        assert len(issues) == 1
        assert issues[0].issue_type == "duplicate_titles"
        assert len(issues[0].affected_urls) == 2


class TestMissingTitles:
    def test_all_have_titles(self):
        pages = [_make_page(title="Has Title")]
        assert _detect_missing_titles(pages) == []

    def test_finds_missing(self):
        pages = [_make_page(title="", url="https://example.com/no-title", final_url="https://example.com/no-title")]
        issues = _detect_missing_titles(pages)
        assert len(issues) == 1
        assert issues[0].issue_type == "missing_titles"

    def test_ignores_error_pages(self):
        pages = [_make_page(title="", error="request_failed")]
        assert _detect_missing_titles(pages) == []


class TestDuplicateMetas:
    def test_finds_duplicates(self):
        pages = [
            _make_page(url="https://a.com/1", final_url="https://a.com/1", meta_description="Same meta"),
            _make_page(url="https://a.com/2", final_url="https://a.com/2", meta_description="Same meta"),
        ]
        issues = _detect_duplicate_metas(pages)
        assert len(issues) == 1
        assert issues[0].issue_type == "duplicate_metas"


class TestMissingMetas:
    def test_finds_missing(self):
        pages = [_make_page(meta_description="")]
        issues = _detect_missing_metas(pages)
        assert len(issues) == 1


class TestThinContent:
    def test_detects_thin(self):
        pages = [_make_page(word_count=150)]
        issues = _detect_thin_content(pages)
        assert len(issues) == 1
        assert issues[0].issue_type == "thin_content"

    def test_normal_content_ok(self):
        pages = [_make_page(word_count=500)]
        assert _detect_thin_content(pages) == []

    def test_zero_words_ignored(self):
        pages = [_make_page(word_count=0)]
        assert _detect_thin_content(pages) == []


# ─── Heading Issues ─────────────────────────────────────────────


class TestMissingH1:
    def test_detects_missing(self):
        pages = [_make_page(h1s=[], h1_count=0)]
        issues = _detect_missing_h1(pages)
        assert len(issues) == 1

    def test_has_h1_ok(self):
        pages = [_make_page(h1s=["Heading"])]
        assert _detect_missing_h1(pages) == []


class TestMultipleH1:
    def test_detects_multiple(self):
        pages = [_make_page(h1s=["H1 One", "H1 Two"], h1_count=2)]
        issues = _detect_multiple_h1(pages)
        assert len(issues) == 1

    def test_single_h1_ok(self):
        pages = [_make_page(h1s=["One H1"])]
        assert _detect_multiple_h1(pages) == []


class TestBrokenHierarchy:
    def test_detects_skip(self):
        pages = [_make_page(headings=[(1, "H1"), (3, "H3 without H2")])]
        issues = _detect_broken_hierarchy(pages)
        assert len(issues) == 1
        assert issues[0].issue_type == "broken_hierarchy"

    def test_proper_hierarchy_ok(self):
        pages = [_make_page(headings=[(1, "H1"), (2, "H2"), (3, "H3")])]
        assert _detect_broken_hierarchy(pages) == []

    def test_empty_headings_ok(self):
        pages = [_make_page(headings=[])]
        assert _detect_broken_hierarchy(pages) == []


# ─── Link Issues ────────────────────────────────────────────────


class TestBrokenLinks:
    def test_reports_broken(self):
        broken = [{"url": "https://example.com/404", "status": 404}]
        issues = _detect_broken_links(broken)
        assert len(issues) == 1
        assert issues[0].issue_type == "broken_internal_links"

    def test_no_broken(self):
        assert _detect_broken_links([]) == []


class TestRedirectChains:
    def test_reports_chains(self):
        chains = [{"url": "https://a.com/old", "chain": ["https://a.com/old", "https://a.com/mid", "https://a.com/new"]}]
        issues = _detect_redirect_chains(chains)
        assert len(issues) == 1
        assert issues[0].issue_type == "redirect_chains"


class TestOrphanPages:
    def test_finds_orphans(self):
        pages = [
            _make_page(url="https://a.com/", final_url="https://a.com/", internal_links=["https://a.com/linked"]),
            _make_page(url="https://a.com/linked", final_url="https://a.com/linked", internal_links=[]),
            _make_page(url="https://a.com/orphan", final_url="https://a.com/orphan", internal_links=[]),
        ]
        discovered = ["https://a.com/", "https://a.com/linked", "https://a.com/orphan"]
        issues = _detect_orphan_pages(pages, discovered)
        assert len(issues) == 1
        assert "https://a.com/orphan" in issues[0].affected_urls


# ─── Technical Issues ───────────────────────────────────────────


class TestMissingCanonical:
    def test_finds_missing(self):
        pages = [_make_page(canonical="")]
        issues = _detect_missing_canonical(pages)
        assert len(issues) == 1

    def test_has_canonical_ok(self):
        pages = [_make_page(canonical="https://example.com/page")]
        assert _detect_missing_canonical(pages) == []


class TestIncorrectCanonical:
    def test_finds_wrong_domain(self):
        pages = [_make_page(canonical="https://other-domain.com/page")]
        issues = _detect_incorrect_canonical(pages, "example.com")
        assert len(issues) == 1
        assert issues[0].severity == "critical"

    def test_same_domain_ok(self):
        pages = [_make_page(canonical="https://example.com/page")]
        assert _detect_incorrect_canonical(pages, "example.com") == []


class TestNoindexIssues:
    def test_finds_noindex(self):
        pages = [_make_page(robots_meta="noindex, follow")]
        issues = _detect_noindex_issues(pages)
        assert len(issues) == 1

    def test_no_robots_ok(self):
        pages = [_make_page(robots_meta="")]
        assert _detect_noindex_issues(pages) == []


# ─── Score Calculation ──────────────────────────────────────────


class TestScore:
    def test_no_issues_is_100(self):
        assert _calculate_score([]) == 100

    def test_issues_reduce_score(self):
        from core.analyzer import Issue
        issues = [
            Issue(
                category="content",
                issue_type="duplicate_titles",
                title="Fix duplicates",
                description="...",
                severity="high",
                affected_urls=["a", "b", "c"],
            )
        ]
        score = _calculate_score(issues)
        assert 0 < score < 100
