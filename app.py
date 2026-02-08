"""Quick Wins — SEO Audit Tool. Streamlit UI."""

import asyncio
import sys
import time
from datetime import datetime

import nest_asyncio
import streamlit as st

# Allow async inside Streamlit's event loop
nest_asyncio.apply()

# Ensure project root is in path for imports
sys.path.insert(0, ".")

from core.crawler import crawl_site  # noqa: E402
from core.analyzer import analyze  # noqa: E402
from core.llm_client import configure as configure_llm, prioritize_quickwins  # noqa: E402
from core.excel_generator import create_action_plan  # noqa: E402

# ─── Page Config ────────────────────────────────────────────────

st.set_page_config(
    page_title="Quick Wins · SEO Audit",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── API Key ────────────────────────────────────────────────────

GEMINI_AVAILABLE = False
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    configure_llm(api_key)
    GEMINI_AVAILABLE = True
except Exception:
    pass

# ─── CSS ────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --bg: #F8FAFC;
    --surface: #FFFFFF;
    --border: #E2E8F0;
    --border-hover: #CBD5E1;
    --text-primary: #0F172A;
    --text-secondary: #475569;
    --text-muted: #94A3B8;
    --accent: #2563EB;
    --accent-light: #EFF6FF;
    --accent-hover: #1D4ED8;
    --red: #EF4444;
    --red-bg: #FEF2F2;
    --yellow: #F59E0B;
    --yellow-bg: #FFFBEB;
    --green: #10B981;
    --green-bg: #ECFDF5;
    --mono: 'JetBrains Mono', monospace;
    --sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

.stApp { background-color: var(--bg) !important; font-family: var(--sans) !important; }
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
h1,h2,h3,h4,h5,h6 { font-family: var(--sans) !important; color: var(--text-primary) !important; font-weight: 700 !important; }
p,li,span,div { font-family: var(--sans); }

/* Hero */
.hero { text-align: center; padding: 2.5rem 1.5rem .5rem; max-width: 640px; margin: 0 auto; }
.hero-badge { display: inline-flex; align-items: center; gap: .5rem; padding: .35rem .9rem; border-radius: 20px; background: var(--accent-light); color: var(--accent); font-size: 12px; font-weight: 600; font-family: var(--mono); letter-spacing: .03em; margin-bottom: 1rem; }
.hero-badge-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); }
.hero-title { font-size: 38px; font-weight: 800; color: var(--text-primary); margin: 0 0 .4rem; letter-spacing: -.8px; line-height: 1.1; }
.hero-sub { font-size: 15px; color: var(--text-secondary); margin: 0 0 1.75rem; line-height: 1.5; }
.steps { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0; margin-bottom: 1.75rem; max-width: 540px; margin-left: auto; margin-right: auto; position: relative; }
.steps::before { content: ''; position: absolute; top: 15px; left: calc(12.5% + 15px); right: calc(12.5% + 15px); height: 2px; background: var(--border); z-index: 0; }
.step { text-align: center; position: relative; z-index: 1; }
.step-num { display: inline-flex; align-items: center; justify-content: center; width: 30px; height: 30px; border-radius: 50%; background: var(--accent); color: white; font-weight: 700; font-size: 13px; font-family: var(--mono); margin-bottom: .4rem; box-shadow: 0 2px 8px rgba(37,99,235,0.2); }
.step-label { font-size: 12px; color: var(--text-muted); line-height: 1.3; }

/* Input */
.stTextInput > div > div > input { background: var(--surface) !important; border: 1.5px solid var(--border) !important; border-radius: 10px !important; padding: 12px 16px !important; font-size: 15px !important; font-family: var(--sans) !important; color: var(--text-primary) !important; }
.stTextInput > div > div > input:focus { border-color: var(--accent) !important; box-shadow: 0 0 0 3px rgba(37,99,235,0.1) !important; }
.stTextInput > div > div > input::placeholder { color: var(--text-muted) !important; }
.stButton > button { background: var(--accent) !important; color: white !important; border: none !important; border-radius: 10px !important; padding: .6rem 1.5rem !important; font-size: 14px !important; font-weight: 600 !important; font-family: var(--sans) !important; transition: all .2s ease !important; }
.stButton > button:hover { background: var(--accent-hover) !important; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(37,99,235,0.25) !important; }
.stButton > button:disabled { background: var(--border) !important; color: var(--text-muted) !important; transform: none !important; box-shadow: none !important; }

/* Score Circle */
.score-section { text-align: center; padding: 2rem 0 1rem; }
.score-circle { position: relative; display: inline-block; width: 140px; height: 140px; }
.score-circle svg { transform: rotate(-90deg); }
.score-number { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 42px; font-weight: 800; font-family: var(--mono); color: var(--text-primary); }
.score-label { font-size: 14px; color: var(--text-secondary); margin-top: .5rem; }
.score-meta { font-size: 12px; color: var(--text-muted); font-family: var(--mono); margin-top: .25rem; }

/* Section Headers */
.section-title { font-size: 18px; font-weight: 700; color: var(--text-primary); margin: 2rem 0 1rem; display: flex; align-items: center; gap: .5rem; }
.section-count { display: inline-flex; align-items: center; justify-content: center; min-width: 24px; height: 24px; border-radius: 12px; background: var(--accent-light); color: var(--accent); font-size: 12px; font-weight: 700; font-family: var(--mono); padding: 0 8px; }

/* Quick Win Cards */
.qw-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1.25rem 1.5rem; margin-bottom: .75rem; transition: border-color .2s, box-shadow .2s; }
.qw-card:hover { border-color: var(--border-hover); box-shadow: 0 2px 12px rgba(0,0,0,0.04); }
.qw-card-rank { display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 8px; background: var(--accent); color: white; font-weight: 700; font-size: 14px; font-family: var(--mono); flex-shrink: 0; }
.qw-card-header { display: flex; align-items: flex-start; gap: .75rem; margin-bottom: .5rem; }
.qw-card-title { font-size: 15px; font-weight: 600; color: var(--text-primary); margin: 0; flex: 1; line-height: 1.4; }
.qw-card-why { font-size: 13px; color: var(--text-secondary); line-height: 1.55; margin: 0 0 .5rem; padding-left: 2.5rem; }
.qw-card-action { font-size: 13px; color: var(--text-primary); background: #F8FAFC; border-radius: 8px; padding: .75rem 1rem; margin: .5rem 0 .75rem 2.5rem; line-height: 1.5; border-left: 3px solid var(--accent); }
.qw-card-action-label { font-size: 11px; font-weight: 600; color: var(--accent); text-transform: uppercase; letter-spacing: .04em; margin-bottom: .25rem; }
.qw-card-meta { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; padding-left: 2.5rem; }

/* Priority Dot */
.priority-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 4px; }
.priority-high { background: var(--red); }
.priority-medium { background: var(--yellow); }
.priority-low { background: var(--green); }

/* Badges */
.badge { display: inline-flex; align-items: center; padding: 3px 9px; border-radius: 6px; font-size: 11px; font-weight: 600; letter-spacing: .03em; font-family: var(--mono); }
.badge-impact-high { background: var(--red-bg); color: var(--red); }
.badge-impact-medium { background: var(--yellow-bg); color: var(--yellow); }
.badge-impact-low { background: var(--green-bg); color: var(--green); }
.badge-effort { background: #F3F4F6; color: var(--text-secondary); }
.badge-urls { background: var(--accent-light); color: var(--accent); }
.badge-cat { background: #F3F4F6; color: var(--text-secondary); font-weight: 500; }

/* Finding items */
.finding-item { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 1rem 1.25rem; margin-bottom: .5rem; display: flex; align-items: center; gap: 1rem; }
.finding-sev { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.finding-sev-critical { background: var(--red); }
.finding-sev-high { background: #EA580C; }
.finding-sev-medium { background: var(--yellow); }
.finding-sev-low { background: var(--green); }
.finding-text { flex: 1; font-size: 14px; color: var(--text-primary); }
.finding-count { font-family: var(--mono); font-size: 13px; color: var(--text-muted); white-space: nowrap; }

/* Sitemap Warning */
.sitemap-warning { background: #FEF2F2; border: 2px solid #FECACA; border-radius: 12px; padding: 1.5rem; margin: 1.5rem 0; }
.sitemap-warning-title { font-size: 16px; font-weight: 700; color: var(--red); margin-bottom: .5rem; }
.sitemap-warning-text { font-size: 14px; color: #991B1B; line-height: 1.6; }

/* Download */
.download-box { background: var(--surface); border: 1.5px dashed var(--border); border-radius: 12px; padding: 2rem; text-align: center; margin: 1.5rem 0; }
.download-title { font-size: 15px; font-weight: 600; color: var(--text-primary); margin-bottom: .25rem; }
.download-desc { font-size: 13px; color: var(--text-muted); margin-bottom: 1rem; }
.stDownloadButton > button { background: var(--surface) !important; color: var(--text-primary) !important; border: 1.5px solid var(--border) !important; border-radius: 10px !important; font-family: var(--sans) !important; font-weight: 500 !important; font-size: 13px !important; }
.stDownloadButton > button:hover { border-color: var(--accent) !important; color: var(--accent) !important; background: var(--accent-light) !important; box-shadow: none !important; transform: none !important; }

/* Progress */
.stProgress > div > div > div > div { background: linear-gradient(90deg, #2563EB, #3B82F6) !important; border-radius: 10px; }

/* Expander */
.streamlit-expanderHeader { font-family: var(--sans) !important; font-size: 13px !important; font-weight: 500 !important; color: var(--text-secondary) !important; }
.stAlert { border-radius: 10px !important; font-family: var(--sans) !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 0; }
.stTabs [data-baseweb="tab"] { font-family: var(--sans) !important; font-weight: 500 !important; font-size: 14px !important; }

.divider { height: 1px; background: var(--border); margin: 2rem 0; }
.footer { text-align: center; padding: 3rem 0 1.5rem; font-size: 12px; color: var(--text-muted); }
</style>
""", unsafe_allow_html=True)


# ─── Rendering Helpers ──────────────────────────────────────────


def render_score_circle(score: int) -> str:
    """Render an SVG score circle."""
    if score >= 70:
        color = "#10B981"
    elif score >= 40:
        color = "#F59E0B"
    else:
        color = "#EF4444"

    # SVG circle math
    radius = 58
    circumference = 2 * 3.14159 * radius
    offset = circumference * (1 - score / 100)

    return f"""
    <div class="score-section">
        <div class="score-circle">
            <svg width="140" height="140" viewBox="0 0 140 140">
                <circle cx="70" cy="70" r="{radius}" fill="none" stroke="#E2E8F0" stroke-width="8"/>
                <circle cx="70" cy="70" r="{radius}" fill="none" stroke="{color}" stroke-width="8"
                    stroke-linecap="round" stroke-dasharray="{circumference}" stroke-dashoffset="{offset}"/>
            </svg>
            <div class="score-number">{score}</div>
        </div>
    </div>
    """


def render_quickwin_card(win: dict, rank: int) -> str:
    """Render a single quick win card."""
    impact = (win.get("impact") or "medium").lower()
    effort = (win.get("effort") or "medium").lower()
    urls = win.get("urls_affected", 0)
    category = (win.get("category") or "general").title()

    impact_badge = f'<span class="badge badge-impact-{impact}">Impact: {impact}</span>'
    effort_badge = f'<span class="badge badge-effort">Effort: {effort}</span>'
    urls_badge = f'<span class="badge badge-urls">{urls} URLs</span>'
    cat_badge = f'<span class="badge badge-cat">{category}</span>'

    why = win.get("why_matters", "")
    action = win.get("what_to_do", "")

    action_html = ""
    if action:
        action_html = f"""
        <div class="qw-card-action">
            <div class="qw-card-action-label">What to do</div>
            {action}
        </div>"""

    return f"""
    <div class="qw-card">
        <div class="qw-card-header">
            <div class="qw-card-rank">{rank}</div>
            <p class="qw-card-title">{win.get('issue', '')}</p>
        </div>
        <p class="qw-card-why">{why}</p>
        {action_html}
        <div class="qw-card-meta">
            {cat_badge} {urls_badge} {impact_badge} {effort_badge}
        </div>
    </div>"""


def render_finding_item(finding: dict) -> str:
    """Render a single finding in the All Findings section."""
    severity = (finding.get("severity") or "medium").lower()
    count = finding.get("count", 0)
    return f"""
    <div class="finding-item">
        <div class="finding-sev finding-sev-{severity}"></div>
        <div class="finding-text">{finding.get('issue', '')}</div>
        <div class="finding-count">{count} URLs</div>
    </div>"""


# ─── Session State ──────────────────────────────────────────────

if "result" not in st.session_state:
    st.session_state.result = None
if "crawl_data" not in st.session_state:
    st.session_state.crawl_data = None
if "analysis_data" not in st.session_state:
    st.session_state.analysis_data = None


# ─── Hero Section ───────────────────────────────────────────────

st.markdown("""
<div class="hero">
    <div class="hero-badge"><span class="hero-badge-dot"></span> SEO AUDIT TOOL</div>
    <h1 class="hero-title">Quick Wins</h1>
    <p class="hero-sub">Find actionable SEO improvements you can fix today.</p>
    <div class="steps">
        <div class="step"><div class="step-num">1</div><div class="step-label">Enter URL</div></div>
        <div class="step"><div class="step-num">2</div><div class="step-label">Analyze</div></div>
        <div class="step"><div class="step-num">3</div><div class="step-label">Review wins</div></div>
        <div class="step"><div class="step-num">4</div><div class="step-label">Download</div></div>
    </div>
</div>
""", unsafe_allow_html=True)


# ─── Input ──────────────────────────────────────────────────────

col_input, col_btn = st.columns([4, 1])
with col_input:
    url_input = st.text_input(
        "URL",
        placeholder="https://example.com",
        label_visibility="collapsed",
    )
with col_btn:
    run_btn = st.button(
        "Analyze Site",
        disabled=not url_input or not GEMINI_AVAILABLE,
        use_container_width=True,
    )

if not GEMINI_AVAILABLE:
    st.error("Gemini API key not configured. Add `GOOGLE_API_KEY` to Streamlit secrets.")


# ─── Run Analysis ───────────────────────────────────────────────

if run_btn and url_input:
    st.session_state.result = None
    st.session_state.crawl_data = None
    st.session_state.analysis_data = None

    progress = st.progress(0)
    status = st.empty()

    def update_progress(pct: int, msg: str) -> None:
        progress.progress(min(pct, 100))
        status.caption(msg)

    try:
        # Crawl
        loop = asyncio.new_event_loop()
        crawl_result = loop.run_until_complete(
            crawl_site(url_input, progress_cb=update_progress)
        )
        loop.close()

        st.session_state.crawl_data = crawl_result

        # Analyze
        update_progress(80, "Detecting SEO issues...")
        analysis = analyze(crawl_result)
        st.session_state.analysis_data = analysis

        # LLM Prioritization
        update_progress(85, "AI is picking your Top 5 Quick Wins...")
        llm_result = prioritize_quickwins(
            analysis.to_dict(),
            crawl_result.to_dict(),
        )
        if llm_result:
            st.session_state.result = llm_result

        update_progress(100, "Done!")

    except Exception as e:
        st.error(f"Analysis failed: {str(e)}")

    time.sleep(0.3)
    progress.empty()
    status.empty()


# ─── Results ────────────────────────────────────────────────────

if st.session_state.result:
    data = st.session_state.result
    crawl = st.session_state.crawl_data
    analysis = st.session_state.analysis_data

    top_5 = data.get("top_5_quick_wins", [])
    all_findings = data.get("all_findings", {})
    score = data.get("score", analysis.score if analysis else 0)
    domain = data.get("domain", crawl.domain if crawl else "")
    urls_analyzed = crawl.urls_analyzed if crawl else 0

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ── Score ──
    st.markdown(render_score_circle(score), unsafe_allow_html=True)
    st.markdown(
        f'<div style="text-align:center"><div class="score-label">SEO Health Score for <strong>{domain}</strong></div>'
        f'<div class="score-meta">{urls_analyzed} pages analyzed &middot; {datetime.now().strftime("%b %d, %Y")}</div></div>',
        unsafe_allow_html=True,
    )

    # ── Sitemap Warning ──
    if crawl and crawl.sitemap_missing:
        st.markdown("""
        <div class="sitemap-warning">
            <div class="sitemap-warning-title">&#9888; Critical: No XML Sitemap Found</div>
            <div class="sitemap-warning-text">
                Your site has no XML sitemap. This is one of the most important technical SEO elements you need to fix <strong>as soon as possible</strong>.<br><br>
                <strong>Why this matters:</strong> An XML sitemap is your direct communication channel with search engines. Without it, Google has to discover your pages by crawling links alone — which means deeper pages may never get indexed. Sites with sitemaps get indexed faster and more completely.<br><br>
                <strong>What to do right now:</strong><br>
                1. Generate a sitemap using your CMS (WordPress: Yoast/RankMath, Shopify: automatic) or a tool like xml-sitemaps.com<br>
                2. Place it at <code>yoursite.com/sitemap.xml</code><br>
                3. Add <code>Sitemap: https://yoursite.com/sitemap.xml</code> to your robots.txt<br>
                4. Submit it in Google Search Console under Sitemaps
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Top 5 Quick Wins ──
    if top_5:
        st.markdown(
            f'<div class="section-title">&#127919; Your Top 5 Quick Wins <span class="section-count">{len(top_5)}</span></div>',
            unsafe_allow_html=True,
        )
        for i, win in enumerate(top_5, 1):
            st.markdown(render_quickwin_card(win, i), unsafe_allow_html=True)
            example_urls = win.get("example_urls", [])
            if example_urls:
                with st.expander(f"View affected URLs ({len(example_urls)} examples)"):
                    for eu in example_urls[:10]:
                        st.code(eu, language=None)

    # ── All Findings (Tabs) ──
    content_findings = all_findings.get("content", [])
    heading_findings = all_findings.get("headings", [])
    link_findings = all_findings.get("links", [])
    tech_findings = all_findings.get("technical", [])

    total_findings = len(content_findings) + len(heading_findings) + len(link_findings) + len(tech_findings)

    if total_findings > 0:
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="section-title">&#128203; All Findings <span class="section-count">{total_findings}</span></div>',
            unsafe_allow_html=True,
        )

        tab_labels = []
        tab_data = []
        if content_findings:
            tab_labels.append(f"Content Issues ({len(content_findings)})")
            tab_data.append(content_findings)
        if heading_findings:
            tab_labels.append(f"Heading Issues ({len(heading_findings)})")
            tab_data.append(heading_findings)
        if link_findings:
            tab_labels.append(f"Link Issues ({len(link_findings)})")
            tab_data.append(link_findings)
        if tech_findings:
            tab_labels.append(f"Technical Issues ({len(tech_findings)})")
            tab_data.append(tech_findings)

        if tab_labels:
            tabs = st.tabs(tab_labels)
            for tab, findings in zip(tabs, tab_data):
                with tab:
                    for f in findings:
                        st.markdown(render_finding_item(f), unsafe_allow_html=True)
                        urls = f.get("urls", [])
                        if urls:
                            with st.expander(f"View {len(urls)} affected URLs"):
                                for u in urls[:20]:
                                    st.code(u, language=None)

    # ── Download ──
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="download-box">'
        '<div class="download-title">Download your Action Plan</div>'
        '<div class="download-desc">Get the full report as an Excel file ready for Google Sheets.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    excel = create_action_plan(top_5, all_findings, domain)
    fname = f"QuickWins_{domain}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    st.download_button(
        label="Download Action Plan (.xlsx)",
        data=excel,
        file_name=fname,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


# ─── Footer ─────────────────────────────────────────────────────

st.markdown('<div class="footer">Quick Wins &middot; SEO Audit Tool</div>', unsafe_allow_html=True)
