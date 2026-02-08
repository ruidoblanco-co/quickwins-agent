"""Async website crawler with enhanced sitemap discovery."""

import asyncio
import gzip
import re
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse, urljoin

import aiohttp
from bs4 import BeautifulSoup

from utils.logger import get_logger
from utils.url_utils import (
    normalize_domain,
    normalize_url,
    is_valid_page_url,
    is_same_domain,
    make_absolute,
    get_base_url,
    get_path_bucket,
)

log = get_logger("crawler")

CRAWL_TIMEOUT = 8
MAX_PAGES = 60
MAX_CONCURRENT = 10
MAX_INTERNAL_LINKS_PER_PAGE = 15
MAX_BROKEN_LINK_CHECKS = 100
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

COMMON_SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/sitemap1.xml",
]


@dataclass
class PageSignals:
    """SEO signals extracted from a single page."""
    url: str
    final_url: str = ""
    status: Optional[int] = None
    error: str = ""
    title: str = ""
    meta_description: str = ""
    canonical: str = ""
    robots_meta: str = ""
    h1s: list = field(default_factory=list)
    headings: list = field(default_factory=list)  # [(level, text), ...]
    word_count: int = 0
    internal_links: list = field(default_factory=list)
    has_schema: bool = False
    has_hreflang: bool = False

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "final_url": self.final_url,
            "status": self.status,
            "error": self.error,
            "title": self.title,
            "meta_description": self.meta_description,
            "canonical": self.canonical,
            "robots_meta": self.robots_meta,
            "h1s": self.h1s,
            "h1_count": len(self.h1s),
            "headings": self.headings,
            "word_count": self.word_count,
            "internal_links": self.internal_links[:5],
            "internal_link_count": len(self.internal_links),
            "has_schema": self.has_schema,
            "has_hreflang": self.has_hreflang,
        }


@dataclass
class CrawlResult:
    """Complete crawl results."""
    domain: str
    base_url: str
    discovery_method: str
    urls_discovered: int
    urls_analyzed: int
    pages: list = field(default_factory=list)
    broken_links: list = field(default_factory=list)
    redirect_chains: list = field(default_factory=list)
    all_discovered_urls: list = field(default_factory=list)
    sitemap_missing: bool = False

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "base_url": self.base_url,
            "discovery_method": self.discovery_method,
            "urls_discovered": self.urls_discovered,
            "urls_analyzed": self.urls_analyzed,
            "pages": [p.to_dict() for p in self.pages],
            "broken_links": self.broken_links,
            "redirect_chains": self.redirect_chains,
            "sitemap_missing": self.sitemap_missing,
        }


def _headers() -> dict:
    return {"User-Agent": USER_AGENT}


# ─── Sitemap Discovery ─────────────────────────────────────────


def _parse_sitemap_xml(xml_text: str) -> tuple[list[str], list[str]]:
    """Parse sitemap XML, return (urls, sub_sitemaps)."""
    urls, sitemaps = [], []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return urls, sitemaps

    tag_end = lambda el, name: el.tag.lower().endswith(name)

    if tag_end(root, "sitemapindex"):
        for el in root.iter():
            if tag_end(el, "loc") and el.text:
                sitemaps.append(el.text.strip())
    else:
        for el in root.iter():
            if tag_end(el, "loc") and el.text:
                urls.append(el.text.strip())

    return urls, sitemaps


async def _fetch_text(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    """Fetch URL and return text content, handling gzip."""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=CRAWL_TIMEOUT)) as resp:
            if resp.status >= 400:
                return None
            content_type = resp.headers.get("Content-Type", "")
            raw = await resp.read()

            # Handle gzipped sitemaps
            if url.endswith(".gz") or "gzip" in content_type:
                try:
                    raw = gzip.decompress(raw)
                except Exception:
                    pass

            return raw.decode("utf-8", errors="replace")
    except Exception as e:
        log.warning(f"Failed to fetch {url}: {e}")
        return None


async def _fetch_sitemap_urls(
    session: aiohttp.ClientSession,
    sitemap_url: str,
    max_urls: int = 5000,
    depth: int = 0,
) -> list[str]:
    """Recursively fetch URLs from a sitemap, handling sub-sitemaps and gzip."""
    if depth > 3:
        return []

    text = await _fetch_text(session, sitemap_url)
    if not text:
        # Try gzipped version
        if not sitemap_url.endswith(".gz"):
            text = await _fetch_text(session, sitemap_url + ".gz")
        if not text:
            return []

    urls, sub_sitemaps = _parse_sitemap_xml(text)
    all_urls = list(urls)

    for sm in sub_sitemaps[:20]:
        if len(all_urls) >= max_urls:
            break
        sub_urls = await _fetch_sitemap_urls(session, sm, max_urls, depth + 1)
        all_urls.extend(sub_urls)

    # Deduplicate preserving order
    seen = set()
    unique = []
    for u in all_urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique[:max_urls]


async def _discover_from_robots(
    session: aiohttp.ClientSession, base_url: str
) -> list[str]:
    """Check robots.txt for Sitemap: declarations."""
    robots_url = base_url.rstrip("/") + "/robots.txt"
    text = await _fetch_text(session, robots_url)
    if not text:
        return []

    sitemaps = []
    for line in text.splitlines():
        if line.lower().startswith("sitemap:"):
            sm = line.split(":", 1)[1].strip()
            if sm:
                sitemaps.append(sm)

    return list(dict.fromkeys(sitemaps))


async def _discover_urls(
    session: aiohttp.ClientSession, base_url: str
) -> tuple[list[str], str, bool]:
    """
    Full sitemap discovery chain:
    1. robots.txt Sitemap: declarations
    2. Common sitemap paths
    3. Fallback: crawl from homepage

    Returns: (urls, method_description, sitemap_missing)
    """
    # Step 1: robots.txt
    log.info("Checking robots.txt for sitemap declarations...")
    robot_sitemaps = await _discover_from_robots(session, base_url)

    if robot_sitemaps:
        log.info(f"Found {len(robot_sitemaps)} sitemap(s) in robots.txt")
        all_urls = []
        for sm in robot_sitemaps:
            urls = await _fetch_sitemap_urls(session, sm)
            all_urls.extend(urls)
            log.info(f"  {sm} → {len(urls)} URLs")
        if all_urls:
            seen = set()
            unique = [u for u in all_urls if u not in seen and not seen.add(u)]
            return unique, f"robots.txt ({len(robot_sitemaps)} sitemaps)", False

    # Step 2: Common sitemap paths
    log.info("No sitemaps in robots.txt, trying common paths...")
    for path in COMMON_SITEMAP_PATHS:
        sm_url = base_url.rstrip("/") + path
        urls = await _fetch_sitemap_urls(session, sm_url)
        if urls:
            log.info(f"Found sitemap at {path} → {len(urls)} URLs")
            return urls, f"sitemap ({path})", False

    # Step 3: Fallback — crawl from homepage
    log.warning("No sitemap found. Falling back to homepage crawl.")
    return [], "homepage_crawl (no sitemap found)", True


async def _crawl_from_homepage(
    session: aiohttp.ClientSession,
    base_url: str,
    base_domain: str,
    max_pages: int = MAX_PAGES,
) -> list[str]:
    """Discover URLs by following internal links from the homepage."""
    discovered = [base_url]
    visited = {normalize_url(base_url)}
    to_visit = [base_url]

    while to_visit and len(discovered) < max_pages * 3:
        batch = to_visit[:MAX_CONCURRENT]
        to_visit = to_visit[MAX_CONCURRENT:]

        tasks = [_fetch_page_html(session, url) for url in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for url, result in zip(batch, results):
            if isinstance(result, Exception) or result is None:
                continue
            html, final_url = result
            soup = BeautifulSoup(html, "lxml")
            for a in soup.find_all("a", href=True):
                href = make_absolute(a["href"], final_url)
                if not href or not is_valid_page_url(href):
                    continue
                if not is_same_domain(href, base_domain):
                    continue
                norm = normalize_url(href)
                if norm not in visited:
                    visited.add(norm)
                    discovered.append(href)
                    to_visit.append(href)

    return discovered


async def _fetch_page_html(
    session: aiohttp.ClientSession, url: str
) -> Optional[tuple[str, str]]:
    """Fetch a page and return (html, final_url) or None."""
    try:
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=CRAWL_TIMEOUT)
        ) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type.lower():
                return None
            html = await resp.text(errors="replace")
            return html, str(resp.url)
    except Exception:
        return None


# ─── Signal Extraction ──────────────────────────────────────────


def extract_signals(html: str, url: str, final_url: str, status: int, base_domain: str) -> PageSignals:
    """Extract all SEO signals from an HTML page."""
    signals = PageSignals(url=url, final_url=final_url, status=status)

    soup = BeautifulSoup(html, "lxml")

    # Title
    if soup.title and soup.title.string:
        signals.title = soup.title.string.strip()

    # Meta description
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag:
        signals.meta_description = (meta_tag.get("content") or "").strip()

    # Canonical
    canon = soup.find("link", attrs={"rel": lambda x: x and "canonical" in str(x).lower()})
    if canon:
        signals.canonical = (canon.get("href") or "").strip()

    # Robots meta
    robots = soup.find("meta", attrs={"name": lambda x: x and str(x).lower() == "robots"})
    if robots:
        signals.robots_meta = (robots.get("content") or "").strip().lower()

    # H1s
    for h1 in soup.find_all("h1"):
        text = h1.get_text(strip=True)
        if text:
            signals.h1s.append(text)

    # All headings for hierarchy check
    for level in range(1, 7):
        for h in soup.find_all(f"h{level}"):
            text = h.get_text(strip=True)
            if text:
                signals.headings.append((level, text[:100]))

    # Word count
    body = soup.find("body")
    if body:
        # Remove script and style elements
        for tag in body.find_all(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        signals.word_count = len(body.get_text(" ", strip=True).split())

    # Internal links
    for a in soup.find_all("a", href=True):
        href = make_absolute(a["href"], final_url)
        if href and is_same_domain(href, base_domain):
            signals.internal_links.append(href)
        if len(signals.internal_links) >= MAX_INTERNAL_LINKS_PER_PAGE:
            break

    # Schema (JSON-LD)
    signals.has_schema = bool(soup.find("script", attrs={"type": "application/ld+json"}))

    # Hreflang
    signals.has_hreflang = bool(
        soup.find("link", attrs={"rel": lambda x: x and "alternate" in str(x).lower(), "hreflang": True})
    )

    return signals


# ─── Page Fetching ──────────────────────────────────────────────


async def _fetch_and_extract(
    session: aiohttp.ClientSession,
    url: str,
    base_domain: str,
    semaphore: asyncio.Semaphore,
) -> PageSignals:
    """Fetch a page and extract signals, respecting concurrency limit."""
    async with semaphore:
        try:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=CRAWL_TIMEOUT)
            ) as resp:
                status = resp.status
                final_url = str(resp.url)
                content_type = resp.headers.get("Content-Type", "")

                if "text/html" not in content_type.lower():
                    return PageSignals(url=url, final_url=final_url, status=status, error="non_html")

                html = await resp.text(errors="replace")
                return extract_signals(html, url, final_url, status, base_domain)

        except asyncio.TimeoutError:
            return PageSignals(url=url, error="timeout")
        except Exception as e:
            log.warning(f"Error fetching {url}: {e}")
            return PageSignals(url=url, error="request_failed")


# ─── Broken Link / Redirect Detection ──────────────────────────


async def _check_link(
    session: aiohttp.ClientSession,
    url: str,
    semaphore: asyncio.Semaphore,
) -> Optional[dict]:
    """Check a single link for broken status or redirect chain."""
    async with semaphore:
        try:
            # Use allow_redirects=False to detect chains
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=CRAWL_TIMEOUT),
                allow_redirects=False,
            ) as resp:
                status = resp.status

                if 300 <= status < 400:
                    # Follow redirects manually to detect chains
                    chain = [url]
                    current = url
                    for _ in range(5):
                        location = resp.headers.get("Location", "")
                        if not location:
                            break
                        next_url = make_absolute(location, current)
                        chain.append(next_url)
                        current = next_url
                        async with session.get(
                            next_url,
                            timeout=aiohttp.ClientTimeout(total=CRAWL_TIMEOUT),
                            allow_redirects=False,
                        ) as resp2:
                            resp = resp2
                            status = resp2.status
                            if status < 300 or status >= 400:
                                break

                    if len(chain) > 2:
                        return {"url": url, "status": status, "type": "redirect_chain", "chain": chain}
                    if status >= 400:
                        return {"url": url, "status": status, "type": "broken"}
                    return None

                if status >= 400:
                    return {"url": url, "status": status, "type": "broken"}
                return None

        except Exception:
            return {"url": url, "status": None, "type": "broken"}


async def _check_broken_links(
    session: aiohttp.ClientSession,
    links: list[str],
) -> tuple[list[dict], list[dict]]:
    """Check links for broken status and redirect chains."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [_check_link(session, url, semaphore) for url in links[:MAX_BROKEN_LINK_CHECKS]]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    broken = []
    chains = []
    for r in results:
        if isinstance(r, Exception) or r is None:
            continue
        if r["type"] == "broken":
            broken.append({"url": r["url"], "status": r["status"]})
        elif r["type"] == "redirect_chain":
            chains.append({"url": r["url"], "chain": r["chain"]})

    return broken, chains


# ─── URL Sampling ───────────────────────────────────────────────


def _sample_urls(urls: list[str], homepage: str, max_pages: int = MAX_PAGES) -> list[str]:
    """Intelligently sample URLs across site structure."""
    urls = [u for u in urls if is_valid_page_url(u)]
    # Deduplicate
    seen = set()
    unique = []
    for u in urls:
        norm = normalize_url(u)
        if norm not in seen:
            seen.add(norm)
            unique.append(u)

    sample = [homepage] if homepage else []
    sample_set = {normalize_url(homepage)} if homepage else set()

    # First pass: one from each bucket
    buckets = defaultdict(list)
    for u in unique:
        buckets[get_path_bucket(u)].append(u)

    for _, bucket_urls in sorted(buckets.items()):
        if len(sample) >= max_pages:
            break
        for u in bucket_urls:
            if normalize_url(u) not in sample_set:
                sample.append(u)
                sample_set.add(normalize_url(u))
                break

    # Fill remaining
    for u in unique:
        if len(sample) >= max_pages:
            break
        if normalize_url(u) not in sample_set:
            sample.append(u)
            sample_set.add(normalize_url(u))

    return sample[:max_pages]


# ─── Main Crawl Entry Point ────────────────────────────────────


async def crawl_site(
    url_input: str,
    progress_cb=None,
    max_pages: int = MAX_PAGES,
) -> CrawlResult:
    """
    Main crawl entry point.

    Args:
        url_input: User-provided URL or domain
        progress_cb: Optional callback(percent, message)
        max_pages: Maximum pages to analyze

    Returns:
        CrawlResult with all crawl data
    """
    base_url = get_base_url(url_input)
    base_domain = normalize_domain(base_url)
    if not base_domain:
        raise ValueError("Invalid URL or domain")

    log.info(f"Starting crawl of {base_domain}")

    async with aiohttp.ClientSession(headers=_headers()) as session:
        # ── Discover URLs ──
        if progress_cb:
            progress_cb(5, "Checking robots.txt and sitemaps...")

        discovered, method, sitemap_missing = await _discover_urls(session, base_url)

        if not discovered and sitemap_missing:
            if progress_cb:
                progress_cb(10, "No sitemap found. Crawling from homepage...")
            discovered = await _crawl_from_homepage(session, base_url, base_domain, max_pages)
            if not discovered:
                discovered = [base_url]

        if progress_cb:
            progress_cb(15, f"Found {len(discovered)} URLs via {method}. Sampling...")

        # ── Sample ──
        sample = _sample_urls(discovered, base_url, max_pages)
        log.info(f"Sampling {len(sample)} pages from {len(discovered)} discovered")

        if progress_cb:
            progress_cb(20, f"Analyzing {len(sample)} pages (10 concurrent)...")

        # ── Fetch & Extract Signals ──
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        tasks = [_fetch_and_extract(session, url, base_domain, semaphore) for url in sample]

        pages = []
        total = len(tasks)
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            page = await coro
            pages.append(page)
            if progress_cb and i % 5 == 0:
                pct = 20 + int(40 * (i / total))
                progress_cb(pct, f"Scanned {i + 1}/{total} pages...")

        if progress_cb:
            progress_cb(65, "Checking internal links for issues...")

        # ── Collect unique internal links ──
        all_links = set()
        linked_urls = set()
        for p in pages:
            for link in p.internal_links:
                norm = normalize_url(link)
                linked_urls.add(norm)
                if norm not in all_links and is_valid_page_url(link):
                    all_links.add(norm)

        link_list = list(all_links)[:MAX_BROKEN_LINK_CHECKS]
        broken, chains = await _check_broken_links(session, link_list)

        if progress_cb:
            progress_cb(80, "Crawl complete. Preparing data...")

        log.info(
            f"Crawl done: {len(pages)} pages, "
            f"{len(broken)} broken links, {len(chains)} redirect chains"
        )

        return CrawlResult(
            domain=base_domain,
            base_url=base_url,
            discovery_method=method,
            urls_discovered=len(discovered),
            urls_analyzed=len(pages),
            pages=pages,
            broken_links=broken,
            redirect_chains=chains,
            all_discovered_urls=[normalize_url(u) for u in sample],
            sitemap_missing=sitemap_missing,
        )
