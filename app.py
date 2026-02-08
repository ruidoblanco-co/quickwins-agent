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

/* Expander */
.streamlit-expanderHeader { font-family: var(--sans) !important; font-size: 13px !important; font-weight: 500 !important; }
.stAlert { border-radius: 10px !important; font-family: var(--sans) !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 0; }
.stTabs [data-baseweb="tab"] { font-family: var(--sans) !important; font-weight: 500 !important; font-size: 14px !important; }

/* Download button */
.stDownloadButton > button { background: var(--surface) !important; color: var(--text-primary) !important; border: 1.5px solid var(--border) !important; border-radius: 10px !important; font-family: var(--sans) !important; font-weight: 500 !important; font-size: 13px !important; }
.stDownloadButton > button:hover { border-color: var(--accent) !important; color: var(--accent) !important; background: var(--accent-light) !important; box-shadow: none !important; transform: none !important; }

.divider { height: 1px; background: var(--border); margin: 2rem 0; }
.footer { text-align: center; padding: 3rem 0 1.5rem; font-size: 12px; color: var(--text-muted); }
</style>
""", unsafe_allow_html=True)


# ─── Rendering Helpers ──────────────────────────────────────────

IMPACT_ICONS = {"high": ":red_circle:", "medium": ":large_yellow_circle:", "low": ":large_green_circle:"}
SEVERITY_ICONS = {"critical": ":red_circle:", "high": ":large_orange_circle:", "medium": ":large_yellow_circle:", "low": ":large_green_circle:"}


def render_score_circle(score: int) -> str:
    """Render an SVG score circle (this small piece stays as HTML — SVG has no Streamlit equivalent)."""
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
                <circle cx="70" cy="70" r="{radius}" fill="none" stroke="#E2E8F0" stroke-width="8"/>
                <circle cx="70" cy="70" r="{radius}" fill="none" stroke="{color}" stroke-width="8"
                    stroke-linecap="round" stroke-dasharray="{circumference}" stroke-dashoffset="{offset}"/>
            </svg>
            <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:42px;font-weight:800;font-family:var(--mono);color:var(--text-primary)">{score}</div>
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
    impact_icon = IMPACT_ICONS.get(impact, ":large_yellow_circle:")

    with st.container(border=True):
        col_rank, col_content = st.columns([1, 20])
        with col_rank:
            st.markdown(f"**`{rank}`**")
        with col_content:
            st.markdown(f"**{win.get('issue', '')}**")
            if why:
                st.caption(why)
            if action:
                st.info(f"**What to do:** {action}", icon=":material/lightbulb:")

            c1, c2, c3, c4 = st.columns(4)
            c1.caption(f":label: {category}")
            c2.caption(f":link: {urls_count} URLs")
            c3.caption(f"{impact_icon} Impact: {impact}")
            c4.caption(f":hammer_and_wrench: Effort: {effort}")

        if example_urls:
            with st.expander(f":mag: View affected URLs ({len(example_urls)} examples)"):
                for eu in example_urls[:10]:
                    st.code(eu, language=None)


def render_finding_item(finding: dict) -> None:
    """Render a single finding using native Streamlit components."""
    severity = (finding.get("severity") or "medium").lower()
    count = finding.get("count", 0)
    sev_icon = SEVERITY_ICONS.get(severity, ":large_yellow_circle:")
    urls = finding.get("urls", [])

    with st.container(border=True):
        col_sev, col_text, col_count = st.columns([1, 12, 3])
        with col_sev:
            st.markdown(sev_icon)
        with col_text:
            st.markdown(f"**{finding.get('issue', '')}**")
        with col_count:
            st.caption(f"`{count}` URLs")

        if urls:
            with st.expander(f":mag: View {len(urls)} affected URLs"):
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

    with st.status("Analyzing your site...", expanded=True) as status_bar:
        try:
            st.write(":globe_with_meridians: Discovering pages from sitemaps...")
            loop = asyncio.new_event_loop()
            crawl_result = loop.run_until_complete(crawl_site(url_input))
            loop.close()
            st.session_state.crawl_data = crawl_result
            st.write(f":white_check_mark: Found {crawl_result.urls_analyzed} pages to analyze")

            st.write(":mag: Detecting SEO issues...")
            analysis = analyze(crawl_result)
            st.session_state.analysis_data = analysis
            st.write(f":white_check_mark: Found {analysis.total_count} issues (score: {analysis.score}/100)")

            st.write(":brain: AI is picking your Top 5 Quick Wins...")
            llm_result = prioritize_quickwins(
                analysis.to_dict(),
                crawl_result.to_dict(),
            )
            if llm_result:
                st.session_state.result = llm_result
                st.write(":white_check_mark: Quick wins prioritized!")

            status_bar.update(label=":white_check_mark: Analysis complete!", state="complete", expanded=False)

        except Exception as e:
            status_bar.update(label=":x: Analysis failed", state="error")
            st.error(f"Analysis failed: {str(e)}")


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

    # ── Reset Button ──
    _, col_reset = st.columns([5, 1])
    with col_reset:
        if st.button(":arrows_counterclockwise: New Audit", use_container_width=True):
            st.session_state.result = None
            st.session_state.crawl_data = None
            st.session_state.analysis_data = None
            st.rerun()

    # ── Score ──
    st.markdown(render_score_circle(score), unsafe_allow_html=True)
    st.markdown(
        f'<p style="text-align:center;color:var(--text-secondary);font-size:14px;margin:0">'
        f'SEO Health Score for <strong>{domain}</strong></p>'
        f'<p style="text-align:center;color:var(--text-muted);font-size:12px;font-family:var(--mono);margin:.25rem 0 0">'
        f'{urls_analyzed} pages analyzed · {datetime.now().strftime("%b %d, %Y")}</p>',
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
            icon=":warning:",
        )

    # ── Top 5 Quick Wins ──
    if top_5:
        st.subheader(f":dart: Your Top {len(top_5)} Quick Wins")
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
        st.subheader(f":clipboard: All Findings ({total_findings})")

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
    st.subheader(":inbox_tray: Download Action Plan")
    st.caption("Get the full report as an Excel file ready for Google Sheets.")

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
