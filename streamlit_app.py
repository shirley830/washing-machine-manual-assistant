"""Streamlit interface for the model-specific manual assistant."""

from __future__ import annotations

import base64
import csv
import html
import logging
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
ASSET_DIR = PROJECT_ROOT / "assets"
MANIFEST_PATH = PROJECT_ROOT / "data" / "manuals_manifest.csv"
LOGGER = logging.getLogger(__name__)
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from generate import (  # noqa: E402
    GatewayAuthenticationError,
    GatewayConnectionError,
    GatewayPermissionError,
    GatewayRateLimitError,
    GatewayRequestError,
    GenerationConfigurationError,
    grounded_answer,
)
from retrieve import RetrievalInputError  # noqa: E402


st.set_page_config(
    page_title="Washing Machine Manual Assistant",
    page_icon=str(ASSET_DIR / "logo.svg"),
    layout="wide",
    initial_sidebar_state="collapsed",
)


def data_uri(path: Path, mime_type: str) -> str:
    """Return a local asset as a data URI."""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def inject_styles() -> None:
    """Apply the approved, card-free visual system to Streamlit."""
    st.markdown(
        f"""
        <style>
        :root {{
          --navy: #092547;
          --blue: #165ee8;
          --cyan: #55d7e8;
          --paper: #ffffff;
          --muted: #526e83;
          --mist: #eaf5f8;
          --font-text: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
          --font-display: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
        }}
        html, body, [class*="css"],
        h1, h2, h3, h4, h5, h6, p, a, label, small, strong {{
          font-family: var(--font-text) !important;
        }}
        button, input, textarea, select, option {{
          font-family: var(--font-text) !important;
        }}
        [data-testid="stAppViewContainer"] {{
          color: var(--navy) !important;
          background: #ffffff;
        }}
        [data-testid="stHeader"], [data-testid="stToolbar"], footer {{ display: none; }}
        [data-testid="stMainBlockContainer"] {{
          position: relative;
          z-index: 1;
          max-width: 1280px;
          padding-top: .6rem;
          padding-bottom: 2rem;
        }}
        ::selection {{ background: #9be4ed; color: var(--navy); }}

        .wm-topbar {{
          display: flex;
          align-items: center;
          justify-content: center;
          gap: .65rem;
          min-height: 62px;
          max-width: 1160px;
          margin: 0 auto;
          border-bottom: 1px solid rgba(9,37,71,.09);
        }}
        .wm-logo {{ width: 42px; height: 42px; }}
        .wm-wordmark {{ color: #1d1d1f; font-size: .88rem; font-weight: 400; line-height: 1; letter-spacing: -.012em; }}
        .wm-wordmark span {{ display: inline; margin-left: .28rem; color: #59606a; font-weight: 400; }}
        .wm-hero {{
          position: relative;
          min-height: 780px;
          margin: 0 0 4.8rem;
          overflow: hidden;
        }}
        .wm-hero-copy {{
          position: relative;
          z-index: 4;
          display: flex;
          flex-direction: column;
          align-items: center;
          width: 100%;
          padding: 5.4rem 1rem 0;
          box-sizing: border-box;
          text-align: center;
        }}
        .wm-eyebrow {{ width: 100%; margin: 0 0 .9rem; color: #52606d; font-size: .78rem; font-weight: 400; letter-spacing: .14em; text-align: center; text-transform: uppercase; }}
        div[data-testid="stMarkdownContainer"] h1.wm-title {{
          margin: 0 auto 1.25rem;
          width: 100%;
          max-width: 920px;
          text-align: center !important;
          color: #0b2341 !important;
          font-family: var(--font-display) !important;
          font-size: clamp(4rem, 7vw, 6.8rem) !important;
          font-weight: 400 !important;
          line-height: .88 !important;
          letter-spacing: -.04em !important;
          text-wrap: balance;
          text-shadow:
            0 1px 0 #fff,
            0 12px 30px rgba(22,94,232,.10),
            0 32px 80px rgba(9,37,71,.10);
        }}
        div[data-testid="stMarkdownContainer"] h1.wm-title > span[data-heading-text] {{
          display: inline;
          color: var(--navy) !important;
        }}
        .wm-title-accent {{ color: var(--blue) !important; font-weight: 400; }}
        .wm-title-line {{ display: block; width: 100%; text-align: center; }}
        .wm-promise {{
          width: 100%;
          max-width: 39rem;
          margin: 0 auto;
          text-align: center !important;
          color: #53606d;
          font-size: 1.15rem;
          line-height: 1.55;
        }}
        .wm-machine-stage {{
          position: relative;
          min-height: 345px;
          max-width: 1050px;
          margin: 1.6rem auto 0;
          isolation: isolate;
        }}
        .wm-machine-stage::before {{
          content: '';
          position: absolute;
          left: 12%;
          right: 12%;
          bottom: 0;
          height: 75%;
          z-index: -1;
          background: transparent;
        }}
        .wm-machine-stage::after {{
          content: '';
          position: absolute;
          left: 18%;
          right: 18%;
          bottom: 0;
          height: 8%;
          z-index: -1;
          border-radius: 50%;
          background: rgba(20,37,53,.16);
          filter: blur(22px);
          transform: scaleY(.5);
        }}
        .wm-machine {{
          position: absolute;
          display: block;
          object-fit: contain;
          mix-blend-mode: multiply;
          filter: drop-shadow(0 26px 24px rgba(9,37,71,.12));
        }}
        .wm-machine-main {{ width: 30%; height: 100%; left: 35%; bottom: 0; z-index: 3; }}
        .wm-machine-left {{ width: 28%; height: 73%; left: 8%; bottom: 0; z-index: 2; transform: translateY(4px); }}
        .wm-machine-right {{ width: 24%; height: 70%; right: 9%; bottom: 0; z-index: 1; transform: translateY(5px); }}
        @media (prefers-reduced-motion: no-preference) {{
          .wm-hero-copy {{ animation: wm-copy-in .72s cubic-bezier(.16,1,.3,1) both; }}
          .wm-machine-main {{ animation: wm-machine-in .82s .08s cubic-bezier(.16,1,.3,1) both; }}
          .wm-machine-left {{ animation: wm-machine-left-in .82s .16s cubic-bezier(.16,1,.3,1) both; }}
          .wm-machine-right {{ animation: wm-machine-right-in .82s .23s cubic-bezier(.16,1,.3,1) both; }}
        }}
        @keyframes wm-copy-in {{ from {{ opacity: .2; transform: translateY(22px); filter: blur(7px); }} to {{ opacity: 1; transform: none; filter: none; }} }}
        @keyframes wm-machine-in {{ from {{ opacity: .1; transform: translateY(32px) scale(.94); }} to {{ opacity: 1; transform: none; }} }}
        @keyframes wm-machine-left-in {{ from {{ opacity: .1; transform: translate(-24px,30px); }} to {{ opacity: 1; transform: translateY(4px); }} }}
        @keyframes wm-machine-right-in {{ from {{ opacity: .1; transform: translate(24px,28px); }} to {{ opacity: 1; transform: translateY(5px); }} }}

        [data-testid="stForm"] {{ border: 0; padding: 0; background: transparent; }}
        [data-testid="stForm"] [data-testid="stHorizontalBlock"] {{ align-items: end; }}
        [data-testid="stSelectbox"] label,
        [data-testid="stTextInput"] label,
        [data-testid="stTextArea"] label {{
          color: #526e83 !important;
          font-size: .75rem !important;
          font-weight: 620 !important;
          letter-spacing: .09em;
          text-transform: uppercase;
        }}
        [data-testid="stSelectbox"] .react-aria-ComboBox > [role="group"] {{
          min-height: 3rem;
          padding-left: 0;
          border: 0 !important;
          border-bottom: 2px solid rgba(9,37,71,.45) !important;
          border-radius: 0 !important;
          background: transparent !important;
          box-shadow: none !important;
          font-size: 1.05rem;
          font-weight: 560;
        }}
        [data-testid="stSelectbox"] .react-aria-ComboBox input {{
          padding-left: 0 !important;
          color: var(--navy) !important;
          background: transparent !important;
          font-family: var(--font-text) !important;
          font-size: 1.05rem !important;
          font-weight: 560 !important;
        }}
        [data-testid="stSelectbox"] .react-aria-ComboBox > [role="group"]:focus-within {{
          border-bottom-color: var(--blue) !important;
          box-shadow: 0 2px 0 var(--blue) !important;
        }}
        .wm-question-anchor {{ margin-top: .4rem; }}
        div[data-testid="stElementContainer"]:has(.wm-question-anchor) + div[data-testid="stLayoutWrapper"] [data-testid="stHorizontalBlock"] {{
          min-height: 7rem;
          padding: 1.05rem 1.1rem 1rem 1.35rem;
          border: 1px solid rgba(9,37,71,.12);
          border-radius: 24px;
          background: #ffffff;
          box-shadow: 0 18px 46px rgba(9,37,71,.07);
          align-items: center;
        }}
        div[data-testid="stElementContainer"]:has(.wm-question-anchor) + div[data-testid="stLayoutWrapper"] [data-testid="stTextArea"] label {{ color: #607080 !important; }}
        div[data-testid="stElementContainer"]:has(.wm-question-anchor) + div[data-testid="stLayoutWrapper"] [data-testid="stTextAreaRootElement"] {{
          border: 0 !important;
          border-radius: 0 !important;
          background: transparent !important;
          box-shadow: none !important;
        }}
        div[data-testid="stElementContainer"]:has(.wm-question-anchor) + div[data-testid="stLayoutWrapper"] [data-testid="stTextArea"] textarea {{
          padding: .15rem 0 .45rem;
          border: 0 !important;
          border-radius: 0 !important;
          color: #172b43 !important;
          background: transparent !important;
          box-shadow: none !important;
          font-family: var(--font-text) !important;
          font-size: 1.25rem !important;
          line-height: 1.4 !important;
          resize: none !important;
        }}
        div[data-testid="stElementContainer"]:has(.wm-question-anchor) + div[data-testid="stLayoutWrapper"] [data-testid="stTextArea"] textarea:focus {{ box-shadow: 0 2px 0 var(--cyan) !important; }}
        div[data-testid="stElementContainer"]:has(.wm-question-anchor) + div[data-testid="stLayoutWrapper"] [data-testid="stFormSubmitButton"] button {{
          width: 74px;
          height: 74px;
          padding: 0;
          border: 0;
          border-radius: 50%;
          color: white;
          background: var(--blue);
          font-weight: 700;
          box-shadow: 0 10px 24px rgba(22,94,232,.2);
        }}
        div[data-testid="stElementContainer"]:has(.wm-question-anchor) + div[data-testid="stLayoutWrapper"] [data-testid="stFormSubmitButton"] button:hover {{
          color: white;
          background: #0d50d2;
          transform: translateY(-1px);
        }}
        div[data-testid="stElementContainer"]:has(.wm-question-anchor) + div[data-testid="stLayoutWrapper"] [data-testid="stFormSubmitButton"] button:active {{ transform: scale(.98); }}
        button:focus-visible, input:focus-visible {{ outline: 3px solid #55d7e8 !important; outline-offset: 3px; }}

        .wm-trust {{
          margin: 1rem 0 3.4rem;
          color: #4f6a7d;
          font-size: .82rem;
          font-weight: 500;
          text-align: left;
        }}
        [data-testid="stSpinner"] {{
          position: relative;
          min-height: 96px;
          display: flex;
          align-items: center;
          gap: 1rem;
          color: var(--navy);
          overflow: hidden;
        }}
        [data-testid="stSpinner"]::before {{
          content: '';
          flex: 0 0 58px;
          width: 58px;
          height: 58px;
          border: 3px solid rgba(9,37,71,.18);
          border-top-color: var(--blue);
          border-right-color: var(--cyan);
          border-radius: 50%;
          box-shadow: inset 0 0 0 10px rgba(255,255,255,.45);
        }}
        [data-testid="stSpinner"]::after {{
          content: '';
          position: absolute;
          left: 73px;
          right: 0;
          bottom: 13px;
          height: 2px;
          background: linear-gradient(90deg, transparent, var(--blue), var(--cyan), transparent);
          transform: translateX(-65%);
        }}
        [data-testid="stSpinner"] svg {{ display: none !important; }}
        @media (prefers-reduced-motion: no-preference) {{
          [data-testid="stSpinner"]::before {{ animation: wm-drum-turn 1.15s linear infinite; }}
          [data-testid="stSpinner"]::after {{ animation: wm-manual-scan 1.65s cubic-bezier(.16,1,.3,1) infinite; }}
        }}
        @keyframes wm-drum-turn {{ to {{ transform: rotate(360deg); }} }}
        @keyframes wm-manual-scan {{ 0% {{ transform: translateX(-65%); opacity: 0; }} 24% {{ opacity: 1; }} 75%,100% {{ transform: translateX(65%); opacity: 0; }} }}

        .wm-answer-shell {{
          width: 100vw;
          margin-left: calc(50% - 50vw);
          margin-top: 2.4rem;
          background: var(--paper);
          border-top: 1px solid rgba(9,37,71,.08);
        }}
        .wm-answer {{ max-width: 1040px; margin: 0 auto; padding: 4.7rem 2rem 4.1rem; }}
        .wm-answer h2 {{
          max-width: 860px;
          margin: 0 0 1.2rem;
          color: var(--navy) !important;
          font-family: var(--font-display) !important;
          font-size: clamp(2.2rem, 4vw, 3.25rem) !important;
          font-weight: 610 !important;
          line-height: 1.08 !important;
          letter-spacing: -.03em !important;
        }}
        .wm-answer h2 > span[data-heading-text] {{ color: var(--navy) !important; }}
        .wm-answer h2 > span[data-heading-text] > span {{ color: var(--blue) !important; }}
        p.wm-answer-copy {{
          max-width: 75ch;
          margin: 0 0 2.1rem;
          color: #203d54;
          font-family: var(--font-text) !important;
          font-size: 1.36rem !important;
          font-weight: 400;
          line-height: 1.62 !important;
        }}
        .wm-sources {{ display: grid; gap: 1.15rem; margin: .4rem 0 2rem; }}
        .wm-source {{ display: grid; grid-template-columns: 48px minmax(0,1fr) auto; align-items: center; gap: 1rem; }}
        .wm-page {{
          width: 48px;
          height: 48px;
          display: grid;
          place-items: center;
          border-radius: 50%;
          color: white;
          background: var(--blue);
          font-size: .95rem;
          font-weight: 620;
          font-variant-numeric: tabular-nums;
        }}
        .wm-source-name {{ color: var(--blue); font-size: .96rem; font-weight: 500; line-height: 1.4; }}
        .wm-source-meta {{ margin-top: .25rem; color: #597084; font-size: .8rem; font-weight: 400; line-height: 1.5; }}
        .wm-source a {{ color: var(--blue); font-size: .8rem; font-weight: 560; text-decoration: none; text-underline-offset: 3px; }}
        .wm-source a:hover {{ text-decoration: underline; }}
        .wm-explanation {{ max-width: 72ch; margin-top: 2.4rem; }}
        .wm-explanation h3 {{ margin: 0 0 .5rem; font-size: 1rem; font-weight: 620; }}
        .wm-explanation p {{ max-width: 66ch; margin: 0; color: #597084; font-size: .88rem; line-height: 1.6; }}
        .wm-refusal h2 span {{ color: #b53838; }}
        .wm-slogan {{
          margin: 3rem auto .75rem;
          text-align: center;
          color: #31546d;
          font-family: var(--font-display) !important;
          font-size: clamp(1.15rem,2vw,1.55rem);
          font-weight: 560;
          letter-spacing: -.02em;
        }}

        @media (max-width: 700px) {{
          [data-testid="stMainBlockContainer"] {{ padding: .9rem .9rem 1.5rem; }}
          .wm-topbar {{ min-height: 54px; margin-bottom: .2rem; }}
          .wm-logo {{ width: 38px; height: 38px; }}
          .wm-wordmark {{ font-size: .8rem; }}
          .wm-wordmark span {{ display: block; margin: .1rem 0 0; }}
          .wm-hero {{ min-height: 610px; margin-bottom: 2.6rem; }}
          .wm-hero-copy {{ padding: 3.8rem 0 0; }}
          .wm-eyebrow {{ margin-bottom: .7rem; font-size: .68rem; }}
          div[data-testid="stMarkdownContainer"] h1.wm-title {{ max-width: 9ch; font-size: 3.65rem !important; line-height: .9 !important; }}
          .wm-promise {{ max-width: 22rem; padding: 0 .5rem; font-size: 1rem; }}
          .wm-machine-stage {{ min-height: 240px; margin-top: .5rem; }}
          .wm-machine-main {{ width: 43%; left: 28.5%; }}
          .wm-machine-left {{ width: 37%; left: -2%; }}
          .wm-machine-right {{ width: 31%; right: -2%; }}
          [data-testid="stForm"] [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important; gap: .75rem; }}
          [data-testid="stForm"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{ min-width: 0 !important; }}
          div[data-testid="stElementContainer"]:has(.wm-question-anchor) + div[data-testid="stLayoutWrapper"] [data-testid="stColumn"]:first-child {{ flex: 1 1 auto !important; width: auto !important; }}
          div[data-testid="stElementContainer"]:has(.wm-question-anchor) + div[data-testid="stLayoutWrapper"] [data-testid="stColumn"]:last-child {{ flex: 0 0 64px !important; width: 64px !important; }}
          div[data-testid="stElementContainer"]:has(.wm-question-anchor) + div[data-testid="stLayoutWrapper"] [data-testid="stHorizontalBlock"] {{ min-height: 8rem; padding: .9rem 1rem; }}
          div[data-testid="stElementContainer"]:has(.wm-question-anchor) + div[data-testid="stLayoutWrapper"] [data-testid="stTextArea"] textarea {{ font-size: 1rem !important; }}
          div[data-testid="stElementContainer"]:has(.wm-question-anchor) + div[data-testid="stLayoutWrapper"] [data-testid="stFormSubmitButton"] button {{ width: 64px; height: 64px; }}
          .wm-trust {{ margin-bottom: 2.8rem; font-size: .76rem; }}
          .wm-answer {{ padding: 3.6rem 1.25rem 3rem; }}
          .wm-answer h2 {{ font-size: 2rem; }}
          p.wm-answer-copy {{ font-size: 1.16rem !important; line-height: 1.64 !important; }}
          .wm-source {{ grid-template-columns: 42px minmax(0,1fr); gap: .8rem; }}
          .wm-page {{ width: 42px; height: 42px; font-size: .84rem; }}
          .wm-source a {{ display: none; }}
          .wm-source-name {{ font-size: .9rem; }}
          .wm-source-meta {{ font-size: .76rem; }}
          .wm-slogan {{ margin-top: 2.4rem; font-size: 1.12rem; }}
        }}
        @media (prefers-reduced-motion: reduce) {{
          *, *::before, *::after {{ scroll-behavior: auto !important; animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def load_catalogue() -> dict[str, list[str]]:
    """Load supported brands and models in their manifest order."""
    catalogue: dict[str, list[str]] = {}
    with MANIFEST_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            catalogue.setdefault(row["brand"], []).append(row["model"])
    return catalogue


def render_hero() -> None:
    """Render the product identity and its concise promise."""
    logo = data_uri(ASSET_DIR / "logo.svg", "image/svg+xml")
    gaggenau = data_uri(
        ASSET_DIR / "machines" / "gaggenau-wm260164.webp", "image/webp"
    )
    gaggenau_legacy = data_uri(
        ASSET_DIR / "machines" / "gaggenau-wm260162cn.png", "image/png"
    )
    zanussi = data_uri(
        ASSET_DIR / "machines" / "zanussi-zwg1120m.jpg", "image/png"
    )
    st.markdown(
        f"""
        <header class="wm-topbar">
          <img class="wm-logo" src="{logo}" alt="Washing Machine Manual Assistant logo">
          <div class="wm-wordmark">Washing Machine<span>Manual Assistant</span></div>
        </header>
        <section class="wm-hero">
          <div class="wm-hero-copy">
            <p class="wm-eyebrow">Five models. Official manuals.</p>
            <h1 class="wm-title"><span class="wm-title-line">Every cycle,</span><span class="wm-title-line wm-title-accent">made clear.</span></h1>
            <p class="wm-promise">Ask in your own words. Get an answer grounded in your exact model's official manual.</p>
          </div>
          <div class="wm-machine-stage" aria-label="Supported washing machine models from Gaggenau and Zanussi">
            <img class="wm-machine wm-machine-left" src="{gaggenau_legacy}" alt="Gaggenau WM260162CN washing machine">
            <img class="wm-machine wm-machine-main" src="{gaggenau}" alt="Gaggenau WM260164 washing machine">
            <img class="wm-machine wm-machine-right" src="{zanussi}" alt="Zanussi ZWG1120M washing machine">
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def trusted_url(raw_url: str) -> str:
    """Allow only ordinary HTTP links from the checked manifest."""
    parsed = urlparse(raw_url)
    return raw_url if parsed.scheme in {"http", "https"} else "#"


def render_result(result: dict[str, Any], brand: str, model: str) -> None:
    """Render an answer or refusal as a continuous manual section."""
    answered = result["status"] == "answer"
    heading = (
        "Answer from the <span>official manual.</span>"
        if answered
        else "The manual does <span>not support this answer.</span>"
    )
    answer = html.escape(str(result["answer"]))
    reason = html.escape(str(result.get("reason", "")))
    citations = result.get("citations", [])
    source_rows = []
    for citation in citations:
        page = html.escape(str(citation.get("page", "?")))
        filename = html.escape(str(citation.get("source_file", "Official manual")))
        label = html.escape(str(citation.get("label", "Evidence")))
        chunk_id = html.escape(str(citation.get("chunk_id", "")))
        url = html.escape(trusted_url(str(citation.get("source_url", ""))), quote=True)
        source_rows.append(
            f'<div class="wm-source"><div class="wm-page">{page}</div>'
            f'<div><div class="wm-source-name">{filename}</div>'
            f'<div class="wm-source-meta">Page {page} / {label} / {chunk_id}</div></div>'
            f'<a href="{url}" target="_blank" rel="noopener noreferrer">Open official manual</a></div>'
        )

    explanation_title = "Why this answer is shown" if answered else "Why the assistant refused"
    css_class = "wm-answer" if answered else "wm-answer wm-refusal"
    sources_html = f'<div class="wm-sources">{"".join(source_rows)}</div>' if source_rows else ""
    result_html = (
        f'<section class="wm-answer-shell"><div class="{css_class}"><h2>{heading}</h2>'
        f'<p class="wm-answer-copy">{answer}</p>{sources_html}'
        f'<div class="wm-explanation"><div><h3>{explanation_title}</h3>'
        f'<p>{reason} The request was routed only to {html.escape(brand)} '
        f'{html.escape(model)}.</p></div></div></div></section>'
    )
    st.markdown(result_html, unsafe_allow_html=True)


def user_facing_error(error: Exception) -> str:
    """Translate API and configuration failures into actionable UI copy."""
    if isinstance(error, GatewayAuthenticationError):
        return "OpenRouter rejected the API key. Check the configured OPENROUTER_API_KEY."
    if isinstance(error, GatewayPermissionError):
        return "The configured OpenRouter key cannot use the selected model. Check its model permissions."
    if isinstance(error, GatewayRateLimitError):
        return "The request reached an OpenRouter rate, credit, or spending limit. Check the account and try again."
    if isinstance(error, GatewayConnectionError):
        return "The app could not connect to OpenRouter. Check the internet connection and try again."
    if isinstance(error, GatewayRequestError):
        return (
            "OpenRouter did not return a usable answer. Please try again. "
            "If this continues, check the selected model configuration."
        )
    return str(error)


def hosted_secret(name: str) -> str | None:
    """Read an optional Streamlit-hosted secret without breaking local runs."""
    try:
        value = st.secrets.get(name)
    except (FileNotFoundError, KeyError):
        return None
    return str(value).strip() if value else None


def main() -> None:
    inject_styles()
    render_hero()
    catalogue = load_catalogue()
    brands = list(catalogue)
    default_brand = brands.index("Gaggenau") if "Gaggenau" in brands else 0

    brand_column, model_column = st.columns(2, gap="large")
    with brand_column:
        brand = st.selectbox("Brand", brands, index=default_brand)
    with model_column:
        models = catalogue[brand]
        default_model = models.index("WM260164") if "WM260164" in models else 0
        model = st.selectbox("Exact model", models, index=default_model)

    with st.form("manual_question", clear_on_submit=False):
        st.markdown('<div class="wm-question-anchor"></div>', unsafe_allow_html=True)
        question_column, button_column = st.columns([0.88, 0.12])
        with question_column:
            question = st.text_area(
                "Ask about this machine",
                value="What does error code E:30 / -80 mean?",
                height=78,
            )
        with button_column:
            submitted = st.form_submit_button("ASK", use_container_width=False)

    st.markdown(
        """
        <p class="wm-trust">Only the selected model's official manual is searched. No evidence means no answer.</p>
        """,
        unsafe_allow_html=True,
    )

    if submitted:
        st.session_state.pop("answer_result", None)
        st.session_state.pop("answer_brand", None)
        st.session_state.pop("answer_model", None)
        if not question.strip():
            st.error("Enter a question about the selected washing machine before asking.")
        else:
            try:
                with st.spinner("Searching the exact manual and checking the evidence..."):
                    st.session_state["answer_result"] = grounded_answer(
                        brand=brand,
                        model=model,
                        question=question.strip(),
                        api_key=hosted_secret("OPENROUTER_API_KEY"),
                        model_name=hosted_secret("OPENROUTER_MODEL"),
                        base_url=hosted_secret("OPENROUTER_BASE_URL"),
                    )
                    st.session_state["answer_brand"] = brand
                    st.session_state["answer_model"] = model
            except (
                RetrievalInputError,
                GenerationConfigurationError,
                FileNotFoundError,
                GatewayAuthenticationError,
                GatewayPermissionError,
                GatewayRateLimitError,
                GatewayConnectionError,
                GatewayRequestError,
            ) as error:
                st.error(user_facing_error(error))
            except Exception:
                LOGGER.exception("Unexpected failure while answering a manual question.")
                st.error(
                    "The answer service is temporarily unavailable. "
                    "Please try again in a moment."
                )

    if "answer_result" in st.session_state:
        render_result(
            st.session_state["answer_result"],
            st.session_state["answer_brand"],
            st.session_state["answer_model"],
        )

    st.markdown(
        '<div class="wm-slogan">Every answer starts with the right manual.</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
