"""URL normalization, validation, and filtering utilities."""

from urllib.parse import urlparse, urljoin

IMAGE_EXTENSIONS = frozenset({
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".ico",
    ".bmp", ".tiff", ".tif", ".avif",
})

SKIP_EXTENSIONS = IMAGE_EXTENSIONS | frozenset({
    ".pdf", ".zip", ".gz", ".tar", ".rar",
    ".mp4", ".mp3", ".avi", ".mov", ".wmv",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".exe", ".dmg", ".apk",
})


def normalize_domain(url_or_domain: str) -> str:
    """Extract and normalize domain: lowercase, no www, no port."""
    s = (url_or_domain or "").strip()
    if not s:
        return ""
    s_lower = s.lower()
    if s_lower.startswith(("http://", "https://")):
        s = urlparse(s).netloc
    s = s.lower()
    if s.startswith("www."):
        s = s[4:]
    return s.split(":")[0]


def normalize_url(url: str) -> str:
    """Normalize a URL: strip fragment, trailing slash on path."""
    if not url:
        return ""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    return normalized


def is_valid_page_url(url: str) -> bool:
    """Check if URL is a valid crawlable page (not image, pdf, etc.)."""
    if not url or not url.startswith(("http://", "https://")):
        return False
    path = urlparse(url).path.lower()
    for ext in SKIP_EXTENSIONS:
        if path.endswith(ext):
            return False
    return True


def is_same_domain(url: str, base_domain: str) -> bool:
    """Check if URL belongs to the same domain."""
    return normalize_domain(url) == base_domain


def make_absolute(href: str, base_url: str) -> str:
    """Convert a relative href to an absolute URL."""
    if not href:
        return ""
    href = href.strip()
    if href.startswith(("http://", "https://")):
        return href
    if href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return ""
    return urljoin(base_url, href)


def get_base_url(url_input: str) -> str:
    """Build a clean base URL (scheme + host) from user input."""
    if not url_input.startswith(("http://", "https://")):
        url_input = "https://" + url_input
    parsed = urlparse(url_input)
    return f"{parsed.scheme}://{parsed.netloc}"


def get_path_bucket(url: str) -> str:
    """Get the first path segment for bucketing/sampling."""
    path = (urlparse(url).path or "/").strip("/")
    return path.split("/")[0] if path else "_root"
