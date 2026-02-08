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

/* ── Force readable text on ALL Streamlit elements ── */
.stApp { background-color: #FFFFFF !important; font-family: 'Inter', -apple-system, sans-serif !important; }
.stApp, .stApp p, .stApp div, .stApp span, .stApp li { color: #374151 !important; }
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {
    font-family: 'Inter', -apple-system, sans-serif !important;
    color: #1F2937 !important;
    font-weight: 700 !important;
}
.stApp .stMarkdown p { color: #374151 !important; }
.stApp .stMarkdown strong { color: #1F2937 !important; }

/* Captions should be medium-gray, not invisible */
.stApp .stCaption, .stApp [data-testid="stCaptionContainer"] p {
    color: #6B7280 !important;
}

#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* Hero */
.hero { text-align: center; padding: 2.5rem 1.5rem .5rem; max-width: 640px; margin: 0 auto; }
.hero-badge { display: inline-flex; align-items: center; gap: .5rem; padding: .35rem .9rem; border-radius: 20px; background: #EFF6FF; color: #2563EB !important; font-size: 12px; font-weight: 600; font-family: 'JetBrains Mono', monospace; letter-spacing: .03em; margin-bottom: 1rem; }
.hero-badge-dot { width: 6px; height: 6px; border-radius: 50%; background: #2563EB; }
.hero-title { font-size: 38px; font-weight: 800; color: #1F2937 !important; margin: 0 0 .4rem; letter-spacing: -.8px; line-height: 1.1; }
.hero-sub { font-size: 15px; color: #6B7280 !important; margin: 0 0 1.75rem; line-height: 1.5; }
.steps { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0; margin-bottom: 1.75rem; max-width: 540px; margin-left: auto; margin-right: auto; position: relative; }
.steps::before { content: ''; position: absolute; top: 15px; left: calc(12.5% + 15px); right: calc(12.5% + 15px); height: 2px; background: #E5E7EB; z-index: 0; }
.step { text-align: center; position: relative; z-index: 1; }
.step-num { display: inline-flex; align-items: center; justify-content: center; width: 30px; height: 30px; border-radius: 50%; background: #2563EB; color: white !important; font-weight: 700; font-size: 13px; font-family: 'JetBrains Mono', monospace; margin-bottom: .4rem; box-shadow: 0 2px 8px rgba(37,99,235,0.2); }
.step-label { font-size: 12px; color: #6B7280 !important; line-height: 1.3; }

/* Input */
.stTextInput > div > div > input { background: #FFFFFF !important; border: 1.5px solid #D1D5DB !important; border-radius: 10px !important; padding: 12px 16px !important; font-size: 15px !important; color: #1F2937 !important; }
.stTextInput > div > div > input:focus { border-color: #2563EB !important; box-shadow: 0 0 0 3px rgba(37,99,235,0.1) !important; }
.stTextInput > div > div > input::placeholder { color: #9CA3AF !important; }

/* Primary buttons */
.stButton > button { background: #2563EB !important; color: #FFFFFF !important; border: none !important; border-radius: 10px !important; padding: .6rem 1.5rem !important; font-size: 14px !important; font-weight: 600 !important; }
.stButton > button:hover { background: #1D4ED8 !important; }
.stButton > button:disabled { background: #D1D5DB !important; color: #9CA3AF !important; }

/* Progress bar */
.stProgress > div > div > div > div { background: linear-gradient(90deg, #2563EB, #3B82F6) !important; border-radius: 10px; }

/* Download button */
.stDownloadButton > button { background: #FFFFFF !important; color: #1F2937 !important; border: 1.5px solid #D1D5DB !important; border-radius: 10px !important; }
.stDownloadButton > button:hover { border-color: #2563EB !important; color: #2563EB !important; background: #EFF6FF !important; }

/* Tabs */
.stTabs [data-baseweb="tab"] { font-weight: 500 !important; font-size: 14px !important; color: #374151 !important; }

.footer { text-align: center; padding: 3rem 0 1.5rem; font-size: 12px; color: #9CA3AF !important; }
</style>
""", unsafe_allow_html=True)


# ─── Rendering Helpers ──────────────────────────────────────────

IMPACT_LABELS = {"high": "High", "medium": "Medium", "low": "Low"}
SEVERITY_LABELS = {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low"}


def render_score_circle(score: int) -> str:
    """Render an SVG score circle."""
    if score >= 70:
        color = "#10B981"
    elif score >= 40:
        color = "#F59E0B"
    else:
        color = "#EF4444"
    radius = 58
    circumference = 2 * 3.14159 * radius
    offset = circumference * (1 - score / 100)
    return f"""<div style="text-align:center;padding:2rem 0 .5rem">
        <div style="position:relative;display:inline-block;width:140px;height:140px">
            <svg width="140" height="140" viewBox="0 0 140 140" style="transform:rotate(-90deg)">
                <circle cx="70" cy="70" r="{radius}" fill="none" stroke="#E5E7EB" stroke-width="8"/>
                <circle cx="70" cy="70" r="{radius}" fill="none" stroke="{color}" stroke-width="8"
                    stroke-linecap="round" stroke-dasharray="{circumference}" stroke-dashoffset="{offset}"/>
            </svg>
            <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:42px;font-weight:800;font-family:'JetBrains Mono',monospace;color:#1F2937">{score}</div>
        </div></div>"""


def render_quickwin_card(win: dict, rank: int) -> None:
    """Render a quick win card using native Streamlit components."""
    impact = (win.get("impact") or "medium").lower()
    effort = (win.get("effort") or "medium").lower()
    urls_count = win.get("urls_affected", 0)
    category = (win.get("category") or "general").title()
    why = win.get("why_matters", "")
    action = win.get("what_to_do", "")
    example_urls = win.get("example_urls", [])

    with st.container(border=True):
        col_rank, col_content = st.columns([1, 20])
        with col_rank:
            st.markdown(f"### {rank}")
        with col_content:
            st.markdown(f"**{win.get('issue', '')}**")
            if why:
                st.write(why)
            if action:
                st.info(f"**What to do:** {action}")

            c1, c2, c3, c4 = st.columns(4)
            c1.write(f"**{category}**")
            c2.write(f"**{urls_count}** URLs")
            c3.write(f"Impact: **{IMPACT_LABELS.get(impact, impact)}**")
            c4.write(f"Effort: **{IMPACT_LABELS.get(effort, effort)}**")

        if example_urls:
            with st.expander(f"View {len(example_urls)} affected URLs"):
                for eu in example_urls[:10]:
                    st.code(eu, language=None)


def render_finding_item(finding: dict) -> None:
    """Render a single finding using native Streamlit components."""
    severity = (finding.get("severity") or "medium").lower()
    count = finding.get("count", 0)
    sev_label = SEVERITY_LABELS.get(severity, severity)
    urls = finding.get("urls", [])

    with st.container(border=True):
        col_text, col_sev, col_count = st.columns([8, 2, 2])
        with col_text:
            st.write(f"**{finding.get('issue', '')}**")
        with col_sev:
            st.write(f"*{sev_label}*")
        with col_count:
            st.write(f"**{count}** URLs")

        if urls:
            with st.expander(f"View {len(urls)} affected URLs"):
                for u in urls[:20]:
                    st.code(u, language=None)


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
    status_text = st.empty()

    def update_progress(pct: int, msg: str) -> None:
        progress.progress(min(pct, 100))
        status_text.caption(msg)

    try:
        # Crawl
        update_progress(5, "Discovering pages from sitemaps...")
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
    status_text.empty()


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

    st.divider()

    # ── Reset Button ──
    _, col_reset = st.columns([5, 1])
    with col_reset:
        if st.button("New Analysis", type="secondary", use_container_width=True):
            st.session_state.result = None
            st.session_state.crawl_data = None
            st.session_state.analysis_data = None
            st.rerun()

    # ── Score ──
    st.markdown(render_score_circle(score), unsafe_allow_html=True)
    st.markdown(
        f'<p style="text-align:center;color:#374151;font-size:14px;margin:0">'
        f'SEO Health Score for <strong style="color:#1F2937">{domain}</strong></p>'
        f'<p style="text-align:center;color:#6B7280;font-size:12px;font-family:monospace;margin:.25rem 0 0">'
        f'{urls_analyzed} pages analyzed &middot; {datetime.now().strftime("%b %d, %Y")}</p>',
        unsafe_allow_html=True,
    )

    # ── Sitemap Warning ──
    if crawl and crawl.sitemap_missing:
        st.error(
            "**Critical: No XML Sitemap Found**\n\n"
            "Your site has no XML sitemap. This is one of the most important technical SEO "
            "elements you need to fix **as soon as possible**.\n\n"
            "**Why this matters:** An XML sitemap is your direct communication channel with "
            "search engines. Without it, Google has to discover your pages by crawling links "
            "alone — which means deeper pages may never get indexed.\n\n"
            "**What to do right now:**\n"
            "1. Generate a sitemap using your CMS (WordPress: Yoast/RankMath, Shopify: automatic)\n"
            "2. Place it at `yoursite.com/sitemap.xml`\n"
            "3. Add `Sitemap: https://yoursite.com/sitemap.xml` to your `robots.txt`\n"
            "4. Submit it in Google Search Console under Sitemaps",
        )

    # ── Top 5 Quick Wins ──
    if top_5:
        st.subheader(f"Your Top {len(top_5)} Quick Wins")
        for i, win in enumerate(top_5, 1):
            render_quickwin_card(win, i)

    # ── All Findings (Tabs) ──
    content_findings = all_findings.get("content", [])
    heading_findings = all_findings.get("headings", [])
    link_findings = all_findings.get("links", [])
    tech_findings = all_findings.get("technical", [])

    total_findings = len(content_findings) + len(heading_findings) + len(link_findings) + len(tech_findings)

    if total_findings > 0:
        st.divider()
        st.subheader(f"All Findings ({total_findings})")

        tab_labels = []
        tab_data = []
        if content_findings:
            tab_labels.append(f"Content ({len(content_findings)})")
            tab_data.append(content_findings)
        if heading_findings:
            tab_labels.append(f"Headings ({len(heading_findings)})")
            tab_data.append(heading_findings)
        if link_findings:
            tab_labels.append(f"Links ({len(link_findings)})")
            tab_data.append(link_findings)
        if tech_findings:
            tab_labels.append(f"Technical ({len(tech_findings)})")
            tab_data.append(tech_findings)

        if tab_labels:
            tabs = st.tabs(tab_labels)
            for tab, findings in zip(tabs, tab_data):
                with tab:
                    for f in findings:
                        render_finding_item(f)

    # ── Download ──
    st.divider()
    st.subheader("Download Action Plan")
    st.write("Get the full report as an Excel file ready for Google Sheets.")

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
