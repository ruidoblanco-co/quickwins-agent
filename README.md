# ⚡ Quick Wins — SEO Agent

A fast, focused SEO agent that crawls your site and tells you exactly what to fix today.

No lengthy reports. No fluff. Just a prioritized list of quick wins with concrete instructions — and AI-generated fixes you can copy-paste.

## What it does

1. **Crawls** your site via robots.txt + sitemap (samples up to 80 pages)
2. **Detects** SEO issues: duplicate titles, missing metas, broken links, thin content, missing alt text, canonical problems, and more
3. **Prioritizes** findings as quick wins ranked by severity and effort
4. **Generates fixes** on demand — click any fixable issue and get rewritten titles, meta descriptions, H1 suggestions, or alt text
5. **Exports** everything to a clean Excel file

## Quick start

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/quickwins-agent.git
cd quickwins-agent
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Add your Gemini API key

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml` and add your Google API key.

### 4. Run

```bash
streamlit run app.py
```

## Deploy to Streamlit Cloud

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repo
4. Add `GOOGLE_API_KEY` in the Secrets section
5. Deploy

## Tech stack

- **Streamlit** — UI
- **Gemini 2.5 Flash** — AI analysis & fix generation
- **BeautifulSoup** — HTML parsing
- **openpyxl** — Excel export

## Project structure

```
quickwins-agent/
├── app.py                 # Main application
├── prompts/
│   ├── quickwins.md       # Quick wins analysis prompt
│   └── generate_fix.md    # Fix generation prompt
├── requirements.txt
├── .streamlit/
│   ├── config.toml        # Theme config
│   └── secrets.toml.example
├── .gitignore
└── README.md
```

## License

MIT
