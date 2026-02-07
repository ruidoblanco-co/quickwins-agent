import streamlit as st
import time
import json
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urljoin
from collections import defaultdict
from bs4 import BeautifulSoup
from io import BytesIO
import google.generativeai as genai
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

st.set_page_config(page_title="Quick Wins · SEO Agent", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")

BASE_DIR = Path(__file__).parent
PROMPTS_DIR = BASE_DIR / "prompts"
PROMPT_QUICKWINS = PROMPTS_DIR / "quickwins.md"
PROMPT_FIX = PROMPTS_DIR / "generate_fix.md"
CRAWL_TIMEOUT = 12
MAX_PAGES = 80
MAX_INTERNAL_LINKS_PER_PAGE = 10
MAX_BROKEN_LINK_CHECKS = 120

try:
    GEMINI_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
    GEMINI_AVAILABLE = True
except Exception:
    GEMINI_AVAILABLE = False

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=JetBrains+Mono:wght@400;500&display=swap');
:root{--bg:#FAFAFA;--surface:#FFF;--border:#E8E8E8;--border-hover:#D0D0D0;--text-primary:#1A1A1A;--text-secondary:#6B6B6B;--text-muted:#9B9B9B;--accent:#FF6B35;--accent-light:#FFF3ED;--accent-hover:#E55A2B;--critical:#DC2626;--critical-bg:#FEF2F2;--high:#EA580C;--high-bg:#FFF7ED;--medium:#CA8A04;--medium-bg:#FEFCE8;--low:#16A34A;--low-bg:#F0FDF4;--mono:'JetBrains Mono',monospace;--sans:'DM Sans',-apple-system,BlinkMacSystemFont,sans-serif}
.stApp{background-color:var(--bg)!important;font-family:var(--sans)!important}
#MainMenu,footer,header{visibility:hidden}.stDeployButton{display:none}
h1,h2,h3,h4,h5,h6{font-family:var(--sans)!important;color:var(--text-primary)!important;font-weight:600!important}
p,li,span,div{font-family:var(--sans)}
.qw-hero{text-align:center;padding:3.5rem 1.5rem 1rem;max-width:700px;margin:0 auto}
.qw-logo{display:inline-flex;align-items:center;justify-content:center;width:60px;height:60px;border-radius:16px;background:linear-gradient(135deg,#FF6B35,#FF8F5E);color:white;font-size:28px;margin-bottom:1.25rem;box-shadow:0 6px 20px rgba(255,107,53,0.3)}
.qw-title{font-size:36px;font-weight:700;color:var(--text-primary);margin:0 0 .5rem;letter-spacing:-.8px}
.qw-tagline{font-size:16px;color:var(--text-secondary);margin:0 0 2rem;line-height:1.6;max-width:520px;margin-left:auto;margin-right:auto}
.qw-how{display:flex;justify-content:center;gap:2.5rem;margin-bottom:2.5rem;flex-wrap:wrap}
.qw-step{text-align:center;max-width:150px}
.qw-step-num{display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:50%;background:var(--accent-light);color:var(--accent);font-weight:700;font-size:14px;font-family:var(--mono);margin-bottom:.5rem}
.qw-step-label{font-size:13px;color:var(--text-secondary);line-height:1.4}
.stTextInput>div>div>input{background:var(--surface)!important;border:1.5px solid var(--border)!important;border-radius:10px!important;padding:12px 16px!important;font-size:15px!important;font-family:var(--sans)!important;color:var(--text-primary)!important}
.stTextInput>div>div>input:focus{border-color:var(--accent)!important;box-shadow:0 0 0 3px rgba(255,107,53,0.1)!important}
.stTextInput>div>div>input::placeholder{color:var(--text-muted)!important}
.stButton>button{background:var(--accent)!important;color:white!important;border:none!important;border-radius:10px!important;padding:.6rem 1.5rem!important;font-size:14px!important;font-weight:600!important;font-family:var(--sans)!important;transition:all .2s ease!important}
.stButton>button:hover{background:var(--accent-hover)!important;transform:translateY(-1px);box-shadow:0 4px 12px rgba(255,107,53,0.3)!important}
.stButton>button:disabled{background:var(--border)!important;color:var(--text-muted)!important;transform:none!important;box-shadow:none!important}
.qw-results-hero{text-align:center;padding:2.5rem 1rem 1rem;margin:1rem auto 0;max-width:600px}
.qw-results-count{font-size:80px;font-weight:800;color:var(--accent);font-family:var(--mono);line-height:1;margin-bottom:.25rem}
.qw-results-label{font-size:18px;color:var(--text-secondary);font-weight:500;margin-bottom:.25rem}
.qw-results-meta{font-size:13px;color:var(--text-muted);font-family:var(--mono)}
.qw-section-title{font-size:13px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:.08em;margin:2rem 0 1rem;padding-bottom:.5rem;border-bottom:1px solid var(--border)}
.qw-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:1.25rem 1.5rem;margin-bottom:.75rem;transition:border-color .2s,box-shadow .2s}
.qw-card:hover{border-color:var(--border-hover);box-shadow:0 2px 8px rgba(0,0,0,0.04)}
.qw-card-header{display:flex;align-items:flex-start;gap:.75rem;margin-bottom:.5rem}
.qw-card-title{font-size:15px;font-weight:600;color:var(--text-primary);margin:0;flex:1;line-height:1.35}
.qw-card-desc{font-size:13.5px;color:var(--text-secondary);line-height:1.55;margin:0 0 .75rem}
.qw-card-fix{font-size:13px;color:var(--text-primary);background:#F8F9FA;border-radius:8px;padding:.75rem 1rem;margin:.5rem 0 .75rem;line-height:1.5;border-left:3px solid var(--accent)}
.qw-card-fix-label{font-size:11px;font-weight:600;color:var(--accent);text-transform:uppercase;letter-spacing:.05em;margin-bottom:.25rem}
.qw-card-meta{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}
.badge{display:inline-flex;align-items:center;padding:3px 9px;border-radius:6px;font-size:11px;font-weight:600;letter-spacing:.03em;text-transform:uppercase;font-family:var(--mono)}
.badge-critical{background:var(--critical-bg);color:var(--critical)}.badge-high{background:var(--high-bg);color:var(--high)}.badge-medium{background:var(--medium-bg);color:var(--medium)}.badge-low{background:var(--low-bg);color:var(--low)}
.badge-cat{background:#F3F4F6;color:var(--text-secondary);font-weight:500}.badge-effort{background:#EDE9FE;color:#7C3AED;font-weight:500}.badge-urls{background:#ECFDF5;color:#059669;font-weight:500}.badge-fixable{background:var(--accent-light);color:var(--accent);font-weight:600}
.fix-item{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:1rem 1.25rem;margin-bottom:.5rem}
.fix-url{font-family:var(--mono);font-size:12px;color:var(--text-muted);margin-bottom:6px;word-break:break-all}
.fix-current{font-size:13px;color:var(--critical);text-decoration:line-through;margin-bottom:4px}
.fix-suggested{font-size:14px;color:var(--low);font-weight:500;margin-bottom:4px}
.fix-reason{font-size:12px;color:var(--text-muted);font-style:italic}
.stProgress>div>div>div>div{background:linear-gradient(90deg,var(--accent),#FF8F5E)!important;border-radius:10px}
.qw-download-box{background:var(--surface);border:1.5px dashed var(--border);border-radius:12px;padding:2rem;text-align:center;margin:1.5rem 0}
.qw-download-title{font-size:15px;font-weight:600;color:var(--text-primary);margin-bottom:.25rem}
.qw-download-desc{font-size:13px;color:var(--text-muted);margin-bottom:1rem}
.stDownloadButton>button{background:var(--surface)!important;color:var(--text-primary)!important;border:1.5px solid var(--border)!important;border-radius:10px!important;font-family:var(--sans)!important;font-weight:500!important;font-size:13px!important}
.stDownloadButton>button:hover{border-color:var(--accent)!important;color:var(--accent)!important;background:var(--accent-light)!important;box-shadow:none!important;transform:none!important}
.qw-divider{height:1px;background:var(--border);margin:2rem 0}
.qw-footer{text-align:center;padding:3rem 0 1.5rem;font-size:12px;color:var(--text-muted)}
.streamlit-expanderHeader{font-family:var(--sans)!important;font-size:13px!important;font-weight:500!important;color:var(--text-secondary)!important}
.stAlert{border-radius:10px!important;font-family:var(--sans)!important}
</style>
""", unsafe_allow_html=True)

# ─── UTILITIES ───
def normalize_domain(url_or_domain):
    s = (url_or_domain or "").strip()
    if not s: return ""
    if s.startswith(("http://","https://")): s = urlparse(s).netloc
    s = s.lower()
    if s.startswith("www."): s = s[4:]
    return s.split(":")[0]

def load_prompt(path):
    return path.read_text(encoding="utf-8") if path.exists() else ""

def strip_json_fences(text):
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*```$", "", t)
    return t.strip()

def safe_int(x, default=0):
    try: return int(x)
    except: return default

# ─── CRAWLER ───
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def fetch_url(url, timeout=CRAWL_TIMEOUT):
    try: return requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    except: return None

def get_robots_sitemaps(base_url):
    r = fetch_url(urljoin(base_url.rstrip("/") + "/", "robots.txt"))
    if not r or r.status_code >= 400: return []
    sitemaps = []
    for line in r.text.splitlines():
        if line.lower().startswith("sitemap:"):
            sm = line.split(":", 1)[1].strip()
            if sm: sitemaps.append(sm)
    return list(dict.fromkeys(sitemaps))

def try_default_sitemaps(base_url):
    base = base_url.rstrip("/") + "/"
    return [urljoin(base, "sitemap.xml"), urljoin(base, "sitemap_index.xml")]

def parse_sitemap_xml(xml_text):
    urls, sitemaps = [], []
    try: root = ET.fromstring(xml_text)
    except: return urls, sitemaps
    tag_end = lambda el, name: el.tag.lower().endswith(name)
    if tag_end(root, "sitemapindex"):
        for el in root.findall(".//"):
            if tag_end(el, "loc") and el.text: sitemaps.append(el.text.strip())
    else:
        for el in root.findall(".//"):
            if tag_end(el, "loc") and el.text: urls.append(el.text.strip())
    return urls, sitemaps

def fetch_sitemap_urls(sitemap_url, max_urls=6000):
    r = fetch_url(sitemap_url)
    if not r or r.status_code >= 400: return []
    urls, sitemaps = parse_sitemap_xml(r.text)
    all_urls = list(urls)
    for sm in (sitemaps or [])[:20]:
        time.sleep(0.1)
        all_urls.extend(fetch_sitemap_urls(sm, max_urls=max_urls))
        if len(all_urls) >= max_urls: break
    return list(dict.fromkeys(all_urls))[:max_urls]

def pick_sample(urls, homepage, max_pages=MAX_PAGES):
    urls = [u for u in urls if isinstance(u, str) and u.startswith(("http://","https://"))]
    urls = list(dict.fromkeys(urls))
    sample = [homepage] if homepage else []
    buckets = defaultdict(list)
    for u in urls:
        try:
            path = (urlparse(u).path or "/").strip("/")
            bucket = path.split("/")[0] if path else "_root"
            buckets[bucket].append(u)
        except: continue
    for _, lst in buckets.items():
        if len(sample) >= max_pages: break
        if lst[0] not in sample: sample.append(lst[0])
    for u in urls:
        if len(sample) >= max_pages: break
        if u not in sample: sample.append(u)
    return sample[:max_pages]

def extract_signals(url, base_domain):
    r = fetch_url(url)
    if not r: return {"url": url, "status": None, "error": "request_failed"}
    if "text/html" not in (r.headers.get("Content-Type") or "").lower():
        return {"url": url, "status": r.status_code, "error": "non_html"}
    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    meta = ""
    md = soup.find("meta", attrs={"name": "description"})
    if md: meta = (md.get("content") or "").strip()
    canonical = ""
    c = soup.find("link", attrs={"rel": lambda x: x and "canonical" in x.lower()})
    if c: canonical = (c.get("href") or "").strip()
    robots_meta = ""
    rm = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "robots"})
    if rm: robots_meta = (rm.get("content") or "").strip().lower()
    internal_links = []
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("#","mailto:","tel:","javascript:")): continue
        abs_url = href if href.startswith(("http://","https://")) else urljoin(r.url, href)
        if normalize_domain(abs_url) == base_domain: internal_links.append(abs_url)
        if len(internal_links) >= MAX_INTERNAL_LINKS_PER_PAGE: break
    return {
        "url": url, "final_url": r.url, "status": r.status_code,
        "title": title, "title_len": len(title), "meta": meta, "meta_len": len(meta),
        "canonical": canonical, "robots_meta": robots_meta,
        "h1_count": len(soup.find_all("h1")),
        "word_count": len(soup.get_text(" ", strip=True).split()),
        "hreflang_count": len(soup.find_all("link", attrs={"rel": lambda x: x and "alternate" in x.lower(), "hreflang": True})),
        "jsonld_count": len(soup.find_all("script", attrs={"type": "application/ld+json"})),
        "sample_internal_links": internal_links,
    }

def check_broken_links(links):
    broken = []
    for link in links:
        try:
            r = requests.head(link, headers=HEADERS, timeout=CRAWL_TIMEOUT, allow_redirects=True)
            code = r.status_code
            if code >= 400:
                r2 = requests.get(link, headers=HEADERS, timeout=CRAWL_TIMEOUT, allow_redirects=True)
                code = r2.status_code
            if code >= 400: broken.append({"url": link, "status": code})
        except: broken.append({"url": link, "status": None})
        time.sleep(0.04)
        if len(broken) >= 20: break
    return broken

def build_findings(pages, base_domain):
    summary = {"analyzed_pages": len(pages), "status_4xx_5xx": 0, "redirects": 0,
        "missing_title": 0, "missing_meta": 0, "missing_h1": 0, "multiple_h1": 0,
        "noindex_pages": 0, "missing_canonical": 0, "canonical_mismatch": 0,
        "thin_pages_lt_250w": 0, "pages_with_schema": 0, "pages_with_hreflang": 0}
    examples = {"duplicate_titles": [], "duplicate_meta": [], "noindex_examples": [],
        "canonical_examples": [], "thin_examples": [], "status_examples": []}
    titles, metas = defaultdict(list), defaultdict(list)
    for p in pages:
        status = p.get("status"); url = p.get("final_url") or p.get("url")
        if status is None or (isinstance(status, int) and status >= 400):
            summary["status_4xx_5xx"] += 1
            if len(examples["status_examples"]) < 10: examples["status_examples"].append({"url": url, "status": status})
        elif (p.get("final_url") or p.get("url")) != p.get("url"): summary["redirects"] += 1
        title = (p.get("title") or "").strip(); meta = (p.get("meta") or "").strip()
        if not title: summary["missing_title"] += 1
        else: titles[title].append(url)
        if not meta: summary["missing_meta"] += 1
        else: metas[meta].append(url)
        h1c = safe_int(p.get("h1_count"), 0)
        if h1c == 0: summary["missing_h1"] += 1
        elif h1c > 1: summary["multiple_h1"] += 1
        robots = (p.get("robots_meta") or "").lower()
        if "noindex" in robots:
            summary["noindex_pages"] += 1
            if len(examples["noindex_examples"]) < 10: examples["noindex_examples"].append({"url": url, "robots": robots})
        canonical = (p.get("canonical") or "").strip()
        if not canonical: summary["missing_canonical"] += 1
        else:
            try:
                c_abs = canonical if canonical.startswith("http") else urljoin(url, canonical)
                if normalize_domain(c_abs) != base_domain:
                    summary["canonical_mismatch"] += 1
                    if len(examples["canonical_examples"]) < 10: examples["canonical_examples"].append({"url": url, "canonical": canonical})
            except: pass
        wc = safe_int(p.get("word_count"), 0)
        if 0 < wc < 250:
            summary["thin_pages_lt_250w"] += 1
            if len(examples["thin_examples"]) < 10: examples["thin_examples"].append({"url": url, "word_count": wc})
        if safe_int(p.get("jsonld_count"), 0) > 0: summary["pages_with_schema"] += 1
        if safe_int(p.get("hreflang_count"), 0) > 0: summary["pages_with_hreflang"] += 1
    for t, urls in sorted(titles.items(), key=lambda x: len(x[1]), reverse=True):
        if len(urls) > 1 and len(examples["duplicate_titles"]) < 5:
            examples["duplicate_titles"].append({"value": t[:140], "count": len(urls), "urls": urls[:5]})
    for m, urls in sorted(metas.items(), key=lambda x: len(x[1]), reverse=True):
        if len(urls) > 1 and len(examples["duplicate_meta"]) < 5:
            examples["duplicate_meta"].append({"value": m[:160], "count": len(urls), "urls": urls[:5]})
    return summary, examples

def run_crawl(url_input, progress_cb=None):
    base_domain = normalize_domain(url_input)
    if not base_domain: raise ValueError("Invalid URL/domain")
    base_url = url_input if url_input.startswith(("http://","https://")) else "https://" + url_input
    p = urlparse(base_url); base_url = f"{p.scheme}://{p.netloc}"
    if progress_cb: progress_cb(10, "Checking robots.txt & sitemaps...")
    sitemaps = get_robots_sitemaps(base_url) or try_default_sitemaps(base_url)
    discovered, used_sm = [], None
    for sm in sitemaps:
        urls = fetch_sitemap_urls(sm, max_urls=6000)
        if urls: discovered, used_sm = urls, sm; break
    homepage = base_url
    if not discovered: sample_urls, method, disc_count = [homepage], "homepage_only", 1
    else: sample_urls, method, disc_count = pick_sample(discovered, homepage), f"sitemap ({used_sm})", len(discovered)
    if progress_cb: progress_cb(20, f"Found {disc_count} URLs. Scanning {len(sample_urls)} pages...")
    pages = []
    for i, u in enumerate(sample_urls):
        pages.append(extract_signals(u, base_domain)); time.sleep(0.1)
        if progress_cb and i % 5 == 0: progress_cb(20 + int(40*(i/len(sample_urls))), f"Scanning page {i+1}/{len(sample_urls)}...")
    if progress_cb: progress_cb(65, "Analyzing findings...")
    summary, examples = build_findings(pages, base_domain)
    if progress_cb: progress_cb(70, "Checking internal links...")
    all_links = []
    for pg in pages:
        for ln in (pg.get("sample_internal_links") or []):
            if ln not in all_links: all_links.append(ln)
            if len(all_links) >= MAX_BROKEN_LINK_CHECKS: break
        if len(all_links) >= MAX_BROKEN_LINK_CHECKS: break
    broken = check_broken_links(all_links)
    summary["broken_internal_links_checked"] = len(all_links)
    summary["broken_internal_links_found"] = len(broken)
    examples["broken_links"] = broken
    return {"domain": base_domain, "audit_date": datetime.now().strftime("%Y-%m-%d"),
        "discovery_method": method, "urls_discovered": disc_count, "urls_analyzed": len(pages),
        "crawl_summary": summary, "pages": pages, "examples": examples}

# ─── LLM ───
def call_gemini(prompt_text):
    model = genai.GenerativeModel("gemini-2.5-flash")
    resp = model.generate_content(prompt_text)
    return (getattr(resp, "text", "") or "").strip()

def parse_json_response(raw):
    if not raw: return None
    cleaned = strip_json_fences(raw)
    try: return json.loads(cleaned)
    except: pass
    depth, start = 0, None
    for i, ch in enumerate(cleaned):
        if ch == '{':
            if depth == 0: start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                try: return json.loads(cleaned[start:i+1])
                except: pass
    return None

def analyze_quickwins(context):
    tmpl = load_prompt(PROMPT_QUICKWINS)
    if not tmpl:
        st.error("Could not load prompt file.")
        return None
    prompt = tmpl.replace("{{CONTEXT_JSON}}", json.dumps(context, ensure_ascii=False, indent=2))
    try: raw = call_gemini(prompt)
    except Exception as e:
        st.error(f"Gemini API error: {e}")
        return None
    if not raw:
        st.error("Gemini returned an empty response.")
        return None
    result = parse_json_response(raw)
    if result: return result
    st.error("Could not parse AI response.")
    with st.expander("Debug: raw response"):
        st.code(raw[:3000], language=None)
    return None

def generate_fixes(category, affected_pages):
    tmpl = load_prompt(PROMPT_FIX)
    if not tmpl: return None
    fix_context = json.dumps({"category": category, "affected_pages": affected_pages}, ensure_ascii=False, indent=2)
    prompt = tmpl.replace("{{FIX_CONTEXT}}", fix_context)
    try: raw = call_gemini(prompt)
    except: return None
    return parse_json_response(raw)

# ─── EXCEL ───
def create_excel(qw_data, fixes_data=None):
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Quick Wins"
    af = PatternFill("solid", fgColor="FF6B35"); hf = Font(name="Arial",bold=True,color="FFFFFF",size=11); cf = Font(name="Arial",size=10)
    border = Border(bottom=Side(style="thin",color="E8E8E8"))
    for c,w in [("A",6),("B",14),("C",12),("D",50),("E",60),("F",8),("G",10),("H",60)]: ws.column_dimensions[c].width = w
    for col,h in enumerate(["#","Category","Severity","Issue","Description","URLs","Effort","How to Fix"],1):
        c = ws.cell(row=1,column=col,value=h); c.fill = af; c.font = hf; c.alignment = Alignment(horizontal="center",vertical="center")
    sf = {"critical":PatternFill("solid",fgColor="FEF2F2"),"high":PatternFill("solid",fgColor="FFF7ED"),"medium":PatternFill("solid",fgColor="FEFCE8"),"low":PatternFill("solid",fgColor="F0FDF4")}
    sfo = {"critical":Font(name="Arial",size=10,color="DC2626",bold=True),"high":Font(name="Arial",size=10,color="EA580C",bold=True),"medium":Font(name="Arial",size=10,color="CA8A04",bold=True),"low":Font(name="Arial",size=10,color="16A34A",bold=True)}
    for i, qw in enumerate((qw_data.get("quick_wins") or []), start=1):
        row = i+1; sev = (qw.get("severity") or "medium").lower()
        ws.cell(row=row,column=1,value=i).font = cf; ws.cell(row=row,column=2,value=qw.get("category","")).font = cf
        sc = ws.cell(row=row,column=3,value=sev.upper()); sc.font = sfo.get(sev,cf); sc.fill = sf.get(sev,PatternFill()); sc.alignment = Alignment(horizontal="center")
        ws.cell(row=row,column=4,value=qw.get("title","")).font = Font(name="Arial",size=10,bold=True)
        ws.cell(row=row,column=5,value=qw.get("description","")).font = cf
        ws.cell(row=row,column=6,value=qw.get("affected_urls_count",0)).font = cf; ws.cell(row=row,column=6).alignment = Alignment(horizontal="center")
        ws.cell(row=row,column=7,value=qw.get("effort","M")).font = cf; ws.cell(row=row,column=7).alignment = Alignment(horizontal="center")
        ws.cell(row=row,column=8,value=qw.get("fix_instruction","")).font = cf
        for col in range(1,9): ws.cell(row=row,column=col).border = border
    ws.auto_filter.ref = f"A1:H{len(qw_data.get('quick_wins',[]))+1}"; ws.freeze_panes = "A2"
    if fixes_data:
        for cat, fixes in fixes_data.items():
            if not fixes: continue
            ws2 = wb.create_sheet(f"Fixes - {cat.title()}"[:31])
            for c,w in [("A",50),("B",40),("C",50),("D",50)]: ws2.column_dimensions[c].width = w
            for col,h in enumerate(["URL","Current","Suggested Fix","Reasoning"],1):
                c = ws2.cell(row=1,column=col,value=h); c.fill = af; c.font = hf
            for j,fix in enumerate(fixes,start=1):
                ws2.cell(row=j+1,column=1,value=fix.get("url","")).font = cf
                ws2.cell(row=j+1,column=2,value=fix.get("current_value","")).font = Font(name="Arial",size=10,color="999999")
                ws2.cell(row=j+1,column=3,value=fix.get("suggested_fix","")).font = Font(name="Arial",size=10,color="16A34A",bold=True)
                ws2.cell(row=j+1,column=4,value=fix.get("reasoning","")).font = cf
            ws2.freeze_panes = "A2"
    out = BytesIO(); wb.save(out); out.seek(0); return out

# ─── RENDER ───
def render_card(qw):
    sev = (qw.get("severity") or "medium").lower()
    cat = qw.get("category", "general"); effort = qw.get("effort", "M"); count = qw.get("affected_urls_count", 0)
    fix_instruction = qw.get("fix_instruction", ""); can_fix = qw.get("can_generate_fix", False)
    fix_html = f'<div class="qw-card-fix"><div class="qw-card-fix-label">How to fix</div>{fix_instruction}</div>' if fix_instruction else ""
    fixable_badge = '<span class="badge badge-fixable">✨ auto-fix</span>' if can_fix else ""
    return f"""<div class="qw-card"><div class="qw-card-header"><span class="badge badge-{sev}">{sev}</span><p class="qw-card-title">{qw.get('title','')}</p></div><p class="qw-card-desc">{qw.get('description','')}</p>{fix_html}<div class="qw-card-meta"><span class="badge badge-cat">{cat}</span><span class="badge badge-urls">{count} URLs</span><span class="badge badge-effort">Effort: {effort}</span>{fixable_badge}</div></div>"""

# ─── SESSION STATE ───
if "qw_result" not in st.session_state: st.session_state.qw_result = None
if "crawl_context" not in st.session_state: st.session_state.crawl_context = None
if "fixes" not in st.session_state: st.session_state.fixes = {}

# ═════════════════════════════════════
# UI
# ═════════════════════════════════════
st.markdown("""
<div class="qw-hero">
    <div class="qw-logo">⚡</div>
    <h1 class="qw-title">Quick Wins</h1>
    <p class="qw-tagline">
        Find out what you can fix <strong>today</strong> to improve your SEO.<br>
        Paste your URL, get a prioritized list of quick wins with
        concrete instructions — and let AI generate the fixes for you.
    </p>
    <div class="qw-how">
        <div class="qw-step"><div class="qw-step-num">1</div><div class="qw-step-label">Paste your URL</div></div>
        <div class="qw-step"><div class="qw-step-num">2</div><div class="qw-step-label">We crawl & analyze</div></div>
        <div class="qw-step"><div class="qw-step-num">3</div><div class="qw-step-label">Get your quick wins</div></div>
    </div>
</div>
""", unsafe_allow_html=True)

col_input, col_btn = st.columns([4, 1])
with col_input:
    url_input = st.text_input("URL", placeholder="https://example.com", label_visibility="collapsed")
with col_btn:
    run_btn = st.button("Scan →", disabled=not url_input or not GEMINI_AVAILABLE, use_container_width=True)

if not GEMINI_AVAILABLE:
    st.error("Gemini API key not configured. Add `GOOGLE_API_KEY` to Streamlit secrets.")

if run_btn and url_input:
    st.session_state.qw_result = None
    st.session_state.crawl_context = None
    st.session_state.fixes = {}
    progress = st.progress(0)
    status = st.empty()
    def update_progress(pct, msg):
        progress.progress(min(pct, 100))
        status.caption(msg)
    try:
        context = run_crawl(url_input, progress_cb=update_progress)
        st.session_state.crawl_context = context
        update_progress(80, "AI is analyzing quick wins...")
        result = analyze_quickwins(context)
        if result:
            st.session_state.qw_result = result
            update_progress(100, "Done!")
    except Exception as e:
        st.error(f"Scan failed: {str(e)}")
    time.sleep(0.3)
    progress.empty()
    status.empty()

if st.session_state.qw_result:
    data = st.session_state.qw_result
    wins = data.get("quick_wins", [])
    scan = data.get("scan_summary", {})
    analyzed = scan.get("urls_analyzed", 0)
    domain = data.get("domain", "")

    st.markdown('<div class="qw-divider"></div>', unsafe_allow_html=True)

    st.markdown(f"""
    <div class="qw-results-hero">
        <div class="qw-results-count">{len(wins)}</div>
        <div class="qw-results-label">quick wins found for {domain}</div>
        <div class="qw-results-meta">{analyzed} pages scanned · {datetime.now().strftime("%b %d, %Y")}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="qw-section-title">Your Quick Wins</div>', unsafe_allow_html=True)

    for i, qw in enumerate(wins):
        st.markdown(render_card(qw), unsafe_allow_html=True)
        example_urls = qw.get("example_urls", [])
        if example_urls:
            with st.expander(f"Affected URLs ({len(example_urls)} examples)"):
                for eu in example_urls[:5]:
                    st.code(eu, language=None)
        if qw.get("can_generate_fix"):
            cat = qw.get("category", "")
            if st.button(f"✨ Generate AI fixes for: {qw.get('title','')}", key=f"fix_{i}_{cat}", use_container_width=True):
                crawl = st.session_state.crawl_context
                pages = crawl.get("pages", []) if crawl else []
                affected = []
                for pg in pages:
                    purl = pg.get("final_url") or pg.get("url", "")
                    if cat == "titles":
                        val = pg.get("title", "")
                        if not val or val in [e.get("value") for e in (crawl or {}).get("examples", {}).get("duplicate_titles", [])]:
                            affected.append({"url": purl, "current_value": val or "(missing)", "word_count": pg.get("word_count", 0)})
                    elif cat == "metas":
                        val = pg.get("meta", "")
                        if not val or val in [e.get("value") for e in (crawl or {}).get("examples", {}).get("duplicate_meta", [])]:
                            affected.append({"url": purl, "current_value": val or "(missing)", "word_count": pg.get("word_count", 0)})
                    elif cat == "h1":
                        if pg.get("h1_count", 0) == 0:
                            affected.append({"url": purl, "current_value": "(missing)", "title": pg.get("title", "")})
                if not affected:
                    affected = [{"url": eu, "current_value": "(see page)"} for eu in qw.get("example_urls", [])[:10]]
                affected = affected[:15]
                with st.spinner("Generating fixes..."):
                    fix_result = generate_fixes(cat, affected)
                if fix_result and "fixes" in fix_result:
                    st.session_state.fixes[cat] = fix_result["fixes"]
                    for fix in fix_result["fixes"]:
                        st.markdown(f'<div class="fix-item"><div class="fix-url">{fix.get("url","")}</div><div class="fix-current">✗ {fix.get("current_value","")}</div><div class="fix-suggested">✓ {fix.get("suggested_fix","")}</div><div class="fix-reason">{fix.get("reasoning","")}</div></div>', unsafe_allow_html=True)
                else:
                    st.warning("Could not generate fixes. Try again.")

    st.markdown('<div class="qw-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="qw-download-box"><div class="qw-download-title">📥 Download your report</div><div class="qw-download-desc">Get the full quick wins list and any AI-generated fixes as an Excel file.</div></div>', unsafe_allow_html=True)
    excel = create_excel(data, st.session_state.fixes if st.session_state.fixes else None)
    fname = f"QuickWins_{domain}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    st.download_button(label="Download Excel (.xlsx)", data=excel, file_name=fname, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

st.markdown('<div class="qw-footer">Quick Wins · SEO Agent</div>', unsafe_allow_html=True)
