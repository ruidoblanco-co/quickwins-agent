"""LLM integration for Quick Wins prioritization using Gemini 3 Flash."""

import json
import re
from pathlib import Path

import google.generativeai as genai

from utils.logger import get_logger

log = get_logger("llm")

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
PROMPT_FILE = PROMPTS_DIR / "prioritization.md"


def configure(api_key: str) -> None:
    """Configure the Gemini API with the given key."""
    genai.configure(api_key=api_key)
    log.info("Gemini API configured")


def _load_prompt() -> str:
    """Load the prioritization prompt template."""
    if not PROMPT_FILE.exists():
        raise FileNotFoundError(f"Prompt file not found: {PROMPT_FILE}")
    return PROMPT_FILE.read_text(encoding="utf-8")


def _strip_json_fences(text: str) -> str:
    """Remove markdown code fences from JSON response."""
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _parse_json_response(raw: str) -> dict | None:
    """Extract valid JSON from LLM response, handling edge cases."""
    if not raw:
        return None

    cleaned = _strip_json_fences(raw)

    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try extracting JSON object
    depth, start = 0, None
    for i, ch in enumerate(cleaned):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    return json.loads(cleaned[start : i + 1])
                except json.JSONDecodeError:
                    pass

    log.error("Failed to parse JSON from LLM response")
    return None


def _call_gemini(prompt: str) -> str:
    """Call Gemini 3 Flash and return raw text response."""
    model = genai.GenerativeModel("gemini-3-flash-preview")
    response = model.generate_content(prompt)
    text = (getattr(response, "text", "") or "").strip()
    log.info(f"Gemini response: {len(text)} chars")
    return text


def prioritize_quickwins(analysis_dict: dict, crawl_dict: dict) -> dict | None:
    """
    Send analysis results to Gemini for Top 5 prioritization.

    Args:
        analysis_dict: AnalysisResult.to_dict()
        crawl_dict: CrawlResult.to_dict() (summary for context)

    Returns:
        Parsed JSON with top_5_quick_wins and all_findings, or None on failure
    """
    template = _load_prompt()

    context = {
        "domain": crawl_dict.get("domain", ""),
        "urls_discovered": crawl_dict.get("urls_discovered", 0),
        "urls_analyzed": crawl_dict.get("urls_analyzed", 0),
        "discovery_method": crawl_dict.get("discovery_method", ""),
        "sitemap_missing": crawl_dict.get("sitemap_missing", False),
        "score": analysis_dict.get("score", 0),
        "issues": analysis_dict,
    }

    prompt = template.replace(
        "{{CONTEXT_JSON}}",
        json.dumps(context, ensure_ascii=False, indent=2),
    )

    log.info("Calling Gemini for quick wins prioritization...")
    try:
        raw = _call_gemini(prompt)
    except Exception as e:
        log.error(f"Gemini API error: {e}")
        return None

    if not raw:
        log.error("Gemini returned empty response")
        return None

    result = _parse_json_response(raw)
    if not result:
        log.error("Could not parse Gemini response as JSON")
        log.debug(f"Raw response (first 500 chars): {raw[:500]}")
        return None

    # Validate expected structure
    if "top_5_quick_wins" not in result:
        log.warning("Response missing 'top_5_quick_wins' key")

    return result
