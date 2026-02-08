"""Issue detection engine — analyzes crawl data and categorizes SEO problems."""

from dataclasses import dataclass, field
from collections import defaultdict

from utils.logger import get_logger
from utils.url_utils import normalize_url, normalize_domain

log = get_logger("analyzer")


@dataclass
class Issue:
    """A single detected SEO issue."""
    category: str          # content, headings, links, technical
    issue_type: str        # e.g. "duplicate_titles", "missing_h1"
    title: str             # Human-readable title
    description: str       # Why it matters
    severity: str          # critical, high, medium, low
    affected_urls: list = field(default_factory=list)
    details: dict = field(default_factory=dict)

    @property
    def count(self) -> int:
        return len(self.affected_urls)

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "issue_type": self.issue_type,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "affected_urls": self.affected_urls[:20],
            "affected_count": self.count,
            "details": self.details,
        }


@dataclass
class AnalysisResult:
    """Complete analysis output."""
    content_issues: list = field(default_factory=list)
    heading_issues: list = field(default_factory=list)
    link_issues: list = field(default_factory=list)
    technical_issues: list = field(default_factory=list)
    score: int = 100
    sitemap_missing: bool = False

    @property
    def all_issues(self) -> list:
        return self.content_issues + self.heading_issues + self.link_issues + self.technical_issues

    @property
    def total_count(self) -> int:
        return len(self.all_issues)

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "sitemap_missing": self.sitemap_missing,
            "total_issues": self.total_count,
            "content_issues": [i.to_dict() for i in self.content_issues],
            "heading_issues": [i.to_dict() for i in self.heading_issues],
            "link_issues": [i.to_dict() for i in self.link_issues],
            "technical_issues": [i.to_dict() for i in self.technical_issues],
        }


# ─── Score Calculation ──────────────────────────────────────────

SEVERITY_WEIGHTS = {"critical": 15, "high": 8, "medium": 4, "low": 1}


def _calculate_score(issues: list[Issue]) -> int:
    """Calculate SEO score (0-100) based on issue severity and count."""
    penalty = 0
    for issue in issues:
        weight = SEVERITY_WEIGHTS.get(issue.severity, 1)
        # Scale penalty by number of affected URLs, with diminishing returns
        count_factor = min(issue.count, 10)
        penalty += weight * (1 + count_factor * 0.3)

    score = max(0, min(100, int(100 - penalty)))
    return score


# ─── Content Issue Detectors ────────────────────────────────────


def _detect_duplicate_titles(pages: list) -> list[Issue]:
    """Detect pages sharing the same title tag."""
    titles = defaultdict(list)
    for p in pages:
        title = (p.title if hasattr(p, "title") else p.get("title", "")).strip()
        if title:
            url = p.final_url or p.url if hasattr(p, "final_url") else p.get("final_url") or p.get("url", "")
            titles[title].append(url)

    duplicates = {t: urls for t, urls in titles.items() if len(urls) > 1}
    if not duplicates:
        return []

    all_affected = []
    details = []
    for title, urls in sorted(duplicates.items(), key=lambda x: len(x[1]), reverse=True):
        all_affected.extend(urls)
        details.append({"title": title[:120], "count": len(urls), "urls": urls[:5]})

    return [Issue(
        category="content",
        issue_type="duplicate_titles",
        title=f"Fix {len(all_affected)} pages with duplicate titles",
        description=(
            "Multiple pages share the same title tag. Google uses titles as a primary "
            "ranking signal — duplicate titles make it harder for search engines to "
            "understand which page to rank for a given query."
        ),
        severity="high" if len(all_affected) > 5 else "medium",
        affected_urls=all_affected,
        details={"groups": details},
    )]


def _detect_missing_titles(pages: list) -> list[Issue]:
    """Detect pages without a title tag."""
    affected = []
    for p in pages:
        title = (p.title if hasattr(p, "title") else p.get("title", "")).strip()
        status = p.status if hasattr(p, "status") else p.get("status")
        error = p.error if hasattr(p, "error") else p.get("error", "")
        if not title and not error and status and status < 400:
            url = p.final_url or p.url if hasattr(p, "final_url") else p.get("final_url") or p.get("url", "")
            affected.append(url)

    if not affected:
        return []

    return [Issue(
        category="content",
        issue_type="missing_titles",
        title=f"Add title tags to {len(affected)} pages",
        description=(
            "These pages have no title tag at all. The title is the most important "
            "on-page SEO element — without it, Google has to guess what the page is about."
        ),
        severity="critical" if len(affected) > 3 else "high",
        affected_urls=affected,
    )]


def _detect_duplicate_metas(pages: list) -> list[Issue]:
    """Detect pages sharing the same meta description."""
    metas = defaultdict(list)
    for p in pages:
        meta = (p.meta_description if hasattr(p, "meta_description") else p.get("meta_description", "")).strip()
        if meta:
            url = p.final_url or p.url if hasattr(p, "final_url") else p.get("final_url") or p.get("url", "")
            metas[meta].append(url)

    duplicates = {m: urls for m, urls in metas.items() if len(urls) > 1}
    if not duplicates:
        return []

    all_affected = []
    details = []
    for meta, urls in sorted(duplicates.items(), key=lambda x: len(x[1]), reverse=True):
        all_affected.extend(urls)
        details.append({"meta": meta[:160], "count": len(urls), "urls": urls[:5]})

    return [Issue(
        category="content",
        issue_type="duplicate_metas",
        title=f"Fix {len(all_affected)} pages with duplicate meta descriptions",
        description=(
            "Several pages share identical meta descriptions. Unique descriptions "
            "improve click-through rates from search results and help Google understand "
            "each page's unique value."
        ),
        severity="medium",
        affected_urls=all_affected,
        details={"groups": details},
    )]


def _detect_missing_metas(pages: list) -> list[Issue]:
    """Detect pages without a meta description."""
    affected = []
    for p in pages:
        meta = (p.meta_description if hasattr(p, "meta_description") else p.get("meta_description", "")).strip()
        status = p.status if hasattr(p, "status") else p.get("status")
        error = p.error if hasattr(p, "error") else p.get("error", "")
        if not meta and not error and status and status < 400:
            url = p.final_url or p.url if hasattr(p, "final_url") else p.get("final_url") or p.get("url", "")
            affected.append(url)

    if not affected:
        return []

    return [Issue(
        category="content",
        issue_type="missing_metas",
        title=f"Add meta descriptions to {len(affected)} pages",
        description=(
            "These pages lack a meta description. While not a direct ranking factor, "
            "meta descriptions heavily influence click-through rates from search results."
        ),
        severity="medium" if len(affected) > 5 else "low",
        affected_urls=affected,
    )]


def _detect_thin_content(pages: list) -> list[Issue]:
    """Detect pages with fewer than 300 words."""
    affected = []
    details = []
    for p in pages:
        wc = p.word_count if hasattr(p, "word_count") else p.get("word_count", 0)
        status = p.status if hasattr(p, "status") else p.get("status")
        error = p.error if hasattr(p, "error") else p.get("error", "")
        if 0 < wc < 300 and not error and status and status < 400:
            url = p.final_url or p.url if hasattr(p, "final_url") else p.get("final_url") or p.get("url", "")
            affected.append(url)
            details.append({"url": url, "word_count": wc})

    if not affected:
        return []

    return [Issue(
        category="content",
        issue_type="thin_content",
        title=f"Expand thin content on {len(affected)} pages",
        description=(
            "These pages have fewer than 300 words. Thin content pages often struggle "
            "to rank because they don't provide enough depth for Google to consider them "
            "authoritative on the topic."
        ),
        severity="medium",
        affected_urls=affected,
        details={"pages": details[:20]},
    )]


# ─── Heading Issue Detectors ───────────────────────────────────


def _detect_missing_h1(pages: list) -> list[Issue]:
    """Detect pages without an H1 tag."""
    affected = []
    for p in pages:
        h1_count = len(p.h1s) if hasattr(p, "h1s") else p.get("h1_count", 0)
        status = p.status if hasattr(p, "status") else p.get("status")
        error = p.error if hasattr(p, "error") else p.get("error", "")
        if h1_count == 0 and not error and status and status < 400:
            url = p.final_url or p.url if hasattr(p, "final_url") else p.get("final_url") or p.get("url", "")
            affected.append(url)

    if not affected:
        return []

    return [Issue(
        category="headings",
        issue_type="missing_h1",
        title=f"Add H1 tags to {len(affected)} pages",
        description=(
            "These pages have no H1 heading. The H1 is a strong signal to search engines "
            "about the page's main topic and helps both users and crawlers understand content structure."
        ),
        severity="high" if len(affected) > 3 else "medium",
        affected_urls=affected,
    )]


def _detect_multiple_h1(pages: list) -> list[Issue]:
    """Detect pages with more than one H1 tag."""
    affected = []
    details = []
    for p in pages:
        h1s = p.h1s if hasattr(p, "h1s") else []
        h1_count = len(h1s) if h1s else (p.get("h1_count", 0) if isinstance(p, dict) else 0)
        status = p.status if hasattr(p, "status") else p.get("status")
        error = p.error if hasattr(p, "error") else p.get("error", "")
        if h1_count > 1 and not error and status and status < 400:
            url = p.final_url or p.url if hasattr(p, "final_url") else p.get("final_url") or p.get("url", "")
            affected.append(url)
            details.append({"url": url, "h1s": h1s[:5] if h1s else [], "count": h1_count})

    if not affected:
        return []

    return [Issue(
        category="headings",
        issue_type="multiple_h1",
        title=f"Fix {len(affected)} pages with multiple H1 tags",
        description=(
            "These pages have more than one H1 tag. While not a critical error, "
            "best practice is one H1 per page to clearly signal the primary topic."
        ),
        severity="low",
        affected_urls=affected,
        details={"pages": details[:20]},
    )]


def _detect_broken_hierarchy(pages: list) -> list[Issue]:
    """Detect pages with broken heading hierarchy (e.g., H3 before H2)."""
    affected = []
    details = []
    for p in pages:
        headings = p.headings if hasattr(p, "headings") else p.get("headings", [])
        status = p.status if hasattr(p, "status") else p.get("status")
        error = p.error if hasattr(p, "error") else p.get("error", "")
        if not headings or error or not status or status >= 400:
            continue

        # Check for level skips (e.g., H1 → H3 without H2)
        prev_level = 0
        broken = False
        for level, text in headings:
            if prev_level > 0 and level > prev_level + 1:
                broken = True
                break
            prev_level = level

        if broken:
            url = p.final_url or p.url if hasattr(p, "final_url") else p.get("final_url") or p.get("url", "")
            affected.append(url)
            details.append({
                "url": url,
                "headings": [(lvl, txt) for lvl, txt in headings[:10]],
            })

    if not affected:
        return []

    return [Issue(
        category="headings",
        issue_type="broken_hierarchy",
        title=f"Fix heading hierarchy on {len(affected)} pages",
        description=(
            "These pages skip heading levels (e.g., jumping from H1 to H3 without an H2). "
            "A proper heading hierarchy helps search engines understand content structure "
            "and improves accessibility."
        ),
        severity="low",
        affected_urls=affected,
        details={"pages": details[:20]},
    )]


# ─── Link Issue Detectors ──────────────────────────────────────


def _detect_broken_links(broken_links: list) -> list[Issue]:
    """Report broken internal links found during crawl."""
    if not broken_links:
        return []

    affected = [bl["url"] for bl in broken_links]
    return [Issue(
        category="links",
        issue_type="broken_internal_links",
        title=f"Fix {len(broken_links)} broken internal links",
        description=(
            "These internal links return 4xx/5xx errors. Broken links waste crawl budget, "
            "hurt user experience, and leak link equity into dead ends."
        ),
        severity="high" if len(broken_links) > 5 else "medium",
        affected_urls=affected,
        details={"links": broken_links[:20]},
    )]


def _detect_redirect_chains(redirect_chains: list) -> list[Issue]:
    """Report redirect chains found during link checking."""
    if not redirect_chains:
        return []

    affected = [rc["url"] for rc in redirect_chains]
    return [Issue(
        category="links",
        issue_type="redirect_chains",
        title=f"Fix {len(redirect_chains)} redirect chains",
        description=(
            "These URLs go through multiple redirects before reaching the final page. "
            "Redirect chains slow page loading, waste crawl budget, and dilute link equity "
            "with each hop."
        ),
        severity="medium",
        affected_urls=affected,
        details={"chains": redirect_chains[:20]},
    )]


def _detect_orphan_pages(pages: list, all_discovered_urls: list) -> list[Issue]:
    """Detect pages that aren't linked to from any other crawled page."""
    # Collect all internal links from all pages
    linked_to = set()
    for p in pages:
        links = p.internal_links if hasattr(p, "internal_links") else p.get("internal_links", [])
        for link in links:
            linked_to.add(normalize_url(link))

    # Find pages that no one links to (except homepage)
    affected = []
    for p in pages:
        url = p.final_url or p.url if hasattr(p, "final_url") else p.get("final_url") or p.get("url", "")
        norm = normalize_url(url)
        # Skip homepage — it's typically linked to from external sources
        if norm == normalize_url(all_discovered_urls[0]) if all_discovered_urls else False:
            continue
        if norm not in linked_to:
            affected.append(url)

    if not affected:
        return []

    return [Issue(
        category="links",
        issue_type="orphan_pages",
        title=f"Fix {len(affected)} orphan pages with no internal links",
        description=(
            "These pages aren't linked to from any other page on the site. "
            "Orphan pages are hard for search engines to discover and receive no "
            "internal link equity, making them unlikely to rank."
        ),
        severity="medium" if len(affected) > 3 else "low",
        affected_urls=affected,
    )]


# ─── Technical Issue Detectors ──────────────────────────────────


def _detect_missing_canonical(pages: list) -> list[Issue]:
    """Detect pages without a canonical tag."""
    affected = []
    for p in pages:
        canonical = (p.canonical if hasattr(p, "canonical") else p.get("canonical", "")).strip()
        status = p.status if hasattr(p, "status") else p.get("status")
        error = p.error if hasattr(p, "error") else p.get("error", "")
        if not canonical and not error and status and status < 400:
            url = p.final_url or p.url if hasattr(p, "final_url") else p.get("final_url") or p.get("url", "")
            affected.append(url)

    if not affected:
        return []

    return [Issue(
        category="technical",
        issue_type="missing_canonical",
        title=f"Add canonical tags to {len(affected)} pages",
        description=(
            "These pages lack a canonical tag. Canonical tags prevent duplicate content "
            "issues by telling search engines which version of a page is the primary one."
        ),
        severity="medium" if len(affected) > 5 else "low",
        affected_urls=affected,
    )]


def _detect_incorrect_canonical(pages: list, base_domain: str) -> list[Issue]:
    """Detect pages where canonical points to a different domain."""
    affected = []
    details = []
    for p in pages:
        canonical = (p.canonical if hasattr(p, "canonical") else p.get("canonical", "")).strip()
        status = p.status if hasattr(p, "status") else p.get("status")
        error = p.error if hasattr(p, "error") else p.get("error", "")
        if not canonical or error or not status or status >= 400:
            continue

        canon_domain = normalize_domain(canonical)
        if canon_domain and canon_domain != base_domain:
            url = p.final_url or p.url if hasattr(p, "final_url") else p.get("final_url") or p.get("url", "")
            affected.append(url)
            details.append({"url": url, "canonical": canonical, "canonical_domain": canon_domain})

    if not affected:
        return []

    return [Issue(
        category="technical",
        issue_type="incorrect_canonical",
        title=f"Fix {len(affected)} pages with incorrect canonical tags",
        description=(
            "These pages have canonical tags pointing to a different domain. "
            "This tells Google to index the other domain's version instead, "
            "effectively de-indexing your pages."
        ),
        severity="critical",
        affected_urls=affected,
        details={"pages": details[:20]},
    )]


def _detect_noindex_issues(pages: list) -> list[Issue]:
    """Detect potentially important pages with noindex."""
    affected = []
    for p in pages:
        robots = (p.robots_meta if hasattr(p, "robots_meta") else p.get("robots_meta", "")).lower()
        status = p.status if hasattr(p, "status") else p.get("status")
        error = p.error if hasattr(p, "error") else p.get("error", "")
        if "noindex" in robots and not error and status and status < 400:
            url = p.final_url or p.url if hasattr(p, "final_url") else p.get("final_url") or p.get("url", "")
            affected.append(url)

    if not affected:
        return []

    return [Issue(
        category="technical",
        issue_type="noindex_important",
        title=f"Review noindex on {len(affected)} pages",
        description=(
            "These pages have a noindex directive, which prevents them from appearing in "
            "search results. If any of these should be indexed, this is actively blocking "
            "their visibility."
        ),
        severity="critical" if len(affected) > 2 else "high",
        affected_urls=affected,
    )]


# ─── Main Analysis Entry Point ──────────────────────────────────


def analyze(crawl_result) -> AnalysisResult:
    """
    Run all detectors on crawl data and return categorized issues with a score.

    Args:
        crawl_result: CrawlResult from crawler

    Returns:
        AnalysisResult with all detected issues and score
    """
    pages = crawl_result.pages
    base_domain = crawl_result.domain

    log.info(f"Analyzing {len(pages)} pages for SEO issues...")

    # Content issues
    content_issues = []
    content_issues.extend(_detect_duplicate_titles(pages))
    content_issues.extend(_detect_missing_titles(pages))
    content_issues.extend(_detect_duplicate_metas(pages))
    content_issues.extend(_detect_missing_metas(pages))
    content_issues.extend(_detect_thin_content(pages))

    # Heading issues
    heading_issues = []
    heading_issues.extend(_detect_missing_h1(pages))
    heading_issues.extend(_detect_multiple_h1(pages))
    heading_issues.extend(_detect_broken_hierarchy(pages))

    # Link issues
    link_issues = []
    link_issues.extend(_detect_broken_links(crawl_result.broken_links))
    link_issues.extend(_detect_redirect_chains(crawl_result.redirect_chains))
    link_issues.extend(_detect_orphan_pages(pages, crawl_result.all_discovered_urls))

    # Technical issues
    technical_issues = []
    technical_issues.extend(_detect_missing_canonical(pages))
    technical_issues.extend(_detect_incorrect_canonical(pages, base_domain))
    technical_issues.extend(_detect_noindex_issues(pages))

    all_issues = content_issues + heading_issues + link_issues + technical_issues
    score = _calculate_score(all_issues)

    log.info(
        f"Analysis complete: {len(all_issues)} issues found, "
        f"score: {score}/100"
    )

    return AnalysisResult(
        content_issues=content_issues,
        heading_issues=heading_issues,
        link_issues=link_issues,
        technical_issues=technical_issues,
        score=score,
        sitemap_missing=crawl_result.sitemap_missing,
    )
