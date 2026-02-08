"""Tests for URL utility functions."""

import sys
sys.path.insert(0, ".")

from utils.url_utils import (
    normalize_domain,
    normalize_url,
    is_valid_page_url,
    is_same_domain,
    make_absolute,
    get_base_url,
    get_path_bucket,
)


class TestNormalizeDomain:
    def test_full_url(self):
        assert normalize_domain("https://www.example.com/page") == "example.com"

    def test_with_www(self):
        assert normalize_domain("https://www.example.com") == "example.com"

    def test_without_www(self):
        assert normalize_domain("https://example.com") == "example.com"

    def test_bare_domain(self):
        assert normalize_domain("example.com") == "example.com"

    def test_with_port(self):
        assert normalize_domain("https://example.com:8080/path") == "example.com"

    def test_uppercase(self):
        assert normalize_domain("HTTPS://WWW.EXAMPLE.COM") == "example.com"

    def test_empty(self):
        assert normalize_domain("") == ""

    def test_none(self):
        assert normalize_domain(None) == ""


class TestNormalizeUrl:
    def test_removes_trailing_slash(self):
        assert normalize_url("https://example.com/page/") == "https://example.com/page"

    def test_preserves_root(self):
        assert normalize_url("https://example.com/") == "https://example.com/"

    def test_removes_fragment(self):
        assert normalize_url("https://example.com/page#section") == "https://example.com/page"

    def test_preserves_query(self):
        assert normalize_url("https://example.com/page?q=1") == "https://example.com/page?q=1"

    def test_empty(self):
        assert normalize_url("") == ""


class TestIsValidPageUrl:
    def test_html_page(self):
        assert is_valid_page_url("https://example.com/about") is True

    def test_jpg_image(self):
        assert is_valid_page_url("https://example.com/photo.jpg") is False

    def test_png_image(self):
        assert is_valid_page_url("https://example.com/logo.png") is False

    def test_webp_image(self):
        assert is_valid_page_url("https://example.com/img.webp") is False

    def test_svg_image(self):
        assert is_valid_page_url("https://example.com/icon.svg") is False

    def test_pdf(self):
        assert is_valid_page_url("https://example.com/doc.pdf") is False

    def test_no_scheme(self):
        assert is_valid_page_url("/relative/path") is False

    def test_empty(self):
        assert is_valid_page_url("") is False

    def test_gif_image(self):
        assert is_valid_page_url("https://example.com/anim.gif") is False

    def test_ico_image(self):
        assert is_valid_page_url("https://example.com/favicon.ico") is False


class TestIsSameDomain:
    def test_same(self):
        assert is_same_domain("https://example.com/page", "example.com") is True

    def test_different(self):
        assert is_same_domain("https://other.com/page", "example.com") is False

    def test_www_variant(self):
        assert is_same_domain("https://www.example.com/page", "example.com") is True


class TestMakeAbsolute:
    def test_already_absolute(self):
        assert make_absolute("https://example.com/page", "https://example.com") == "https://example.com/page"

    def test_relative_path(self):
        assert make_absolute("/about", "https://example.com/page") == "https://example.com/about"

    def test_hash_link(self):
        assert make_absolute("#section", "https://example.com") == ""

    def test_mailto(self):
        assert make_absolute("mailto:test@example.com", "https://example.com") == ""

    def test_javascript(self):
        assert make_absolute("javascript:void(0)", "https://example.com") == ""

    def test_empty(self):
        assert make_absolute("", "https://example.com") == ""


class TestGetBaseUrl:
    def test_full_url(self):
        assert get_base_url("https://example.com/some/page") == "https://example.com"

    def test_bare_domain(self):
        assert get_base_url("example.com") == "https://example.com"

    def test_http(self):
        assert get_base_url("http://example.com/page") == "http://example.com"


class TestGetPathBucket:
    def test_root(self):
        assert get_path_bucket("https://example.com/") == "_root"

    def test_blog(self):
        assert get_path_bucket("https://example.com/blog/post-1") == "blog"

    def test_products(self):
        assert get_path_bucket("https://example.com/products/item") == "products"
