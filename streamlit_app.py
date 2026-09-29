"""Streamlit interface for the model-specific manual assistant."""

from __future__ import annotations

import base64
import csv
import html
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import streamlit as st
from openai import (
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    PermissionDeniedError,
    RateLimitError,
)


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
ASSET_DIR = PROJECT_ROOT / "assets"
FONT_DIR = ASSET_DIR / "fonts"
MANIFEST_PATH = PROJECT_ROOT / "data" / "manuals_manifest.csv"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from generate import GenerationConfigurationError, grounded_answer  # noqa: E402
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


def font_face(name: str, filename: str, weight: str) -> str:
    """Build a self-hosted font-face rule when the asset is available."""
    path = FONT_DIR / filename
    if not path.exists():
        return ""
    return f"""
    @font-face {{
      font-family: '{name}';
      src: url('{data_uri(path, "font/ttf")}') format('truetype');
      font-style: normal;
      font-weight: {weight};
      font-display: swap;
    }}
    """


def inject_styles() -> None:
    """Apply the approved, card-free visual system to Streamlit."""
    fonts = "".join(
        [
            font_face("Familjen Grotesk", "FamiljenGrotesk-Variable.ttf", "400 700"),
            font_face(
                "Atkinson Hyperlegible Next",
                "AtkinsonHyperlegibleNext-Variable.ttf",
                "200 800",
            ),
            font_face("Literata", "Literata-Variable.ttf", "200 900"),
        ]
    )
    st.markdown(
        f"""
        <style>
        {fonts}
        :root {{
          --navy: #092547;
          --blue: #165ee8;
          --cyan: #55d7e8;
          --paper: #fffdf8;
          --muted: #526e83;
          --mist: #eaf5f8;
        }}
        html, body, [class*="css"] {{
          font-family: 'Atkinson Hyperlegible Next', 'Arial', sans-serif;
        }}
        [data-testid="stAppViewContainer"] {{
          color: var(--navy) !important;
          background:
            radial-gradient(circle at 50% 12rem, rgba(255,255,255,.58) 0 12rem, transparent 12.1rem),
            radial-gradient(circle at 50% 12rem, transparent 0 16rem, rgba(40,112,194,.08) 16.1rem 21rem, transparent 21.1rem),
            linear-gradient(180deg, #dff4f7 0%, #eff9fb 45%, #e7f4f7 100%);
        }}
        [data-testid="stAppViewContainer"]::before {{
          content: '';
          position: absolute;
          left: 0;
          right: 0;
          top: 36rem;
          height: 17rem;
          pointer-events: none;
          background: rgba(85,215,232,.12);
          clip-path: polygon(0 31%, 14% 18%, 31% 35%, 48% 17%, 67% 36%, 84% 18%, 100% 29%, 100% 100%, 0 100%);
        }}
        [data-testid="stHeader"], [data-testid="stToolbar"], footer {{ display: none; }}
        [data-testid="stMainBlockContainer"] {{
          position: relative;
          z-index: 1;
          max-width: 1088px;
          padding-top: 2.25rem;
          padding-bottom: 2rem;
        }}
        ::selection {{ background: #9be4ed; color: var(--navy); }}

        .wm-hero {{ text-align: center; margin: 0 auto 2rem; }}
        .wm-logo {{ width: 148px; height: 148px; filter: drop-shadow(0 20px 22px rgba(9,37,71,.12)); }}
        div[data-testid="stMarkdownContainer"] h1.wm-title {{
          margin: .75rem auto .55rem;
          max-width: 930px;
          text-align: center !important;
          color: var(--navy) !important;
          font-family: 'Familjen Grotesk', 'Arial', sans-serif !important;
          font-size: clamp(3rem, 5.35vw, 4.65rem) !important;
          font-weight: 650 !important;
          line-height: .98 !important;
          letter-spacing: -.035em !important;
          text-wrap: balance;
        }}
        div[data-testid="stMarkdownContainer"] h1.wm-title > span[data-heading-text] {{
          display: inline-flex;
          flex-direction: column;
          align-items: center;
          color: var(--navy) !important;
        }}
        .wm-title-line {{ display: block; white-space: nowrap; text-align: center; }}
        .wm-title-line-primary {{ color: var(--navy) !important; }}
        .wm-title-line-accent {{ color: var(--blue) !important; letter-spacing: -.018em; }}
        .wm-promise {{
          max-width: 1000px;
          margin: 0 auto;
          text-align: center;
          color: #49667d;
          font-size: 1.03rem;
          line-height: 1.55;
          white-space: nowrap;
        }}

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
          font-family: 'Atkinson Hyperlegible Next', 'Arial', sans-serif !important;
          font-size: 1.05rem !important;
          font-weight: 560 !important;
        }}
        [data-testid="stSelectbox"] .react-aria-ComboBox > [role="group"]:focus-within {{
          border-bottom-color: var(--blue) !important;
          box-shadow: 0 2px 0 var(--blue) !important;
        }}
        .wm-dial-wrap {{ display: grid; place-items: center; padding-bottom: .2rem; }}
        .wm-dial {{
          width: 76px;
          height: 76px;
          display: grid;
          place-items: center;
          border-radius: 50%;
          color: #6a7f8f;
          background: radial-gradient(circle, #fbfdfe 0 43%, #cfdce4 44% 53%, #879baa 54% 56%, #eef4f7 57% 100%);
          box-shadow: 0 5px 10px rgba(31,62,82,.17), inset 0 2px 2px white;
          font-size: .55rem;
          font-weight: 700;
          letter-spacing: .12em;
        }}
        .wm-dial::before {{
          content: '';
          position: absolute;
          width: 3px;
          height: 15px;
          margin-top: -48px;
          border-radius: 2px;
          background: var(--blue);
          transform: rotate(24deg);
        }}
        .wm-question-anchor {{ margin-top: .4rem; }}
        div[data-testid="stElementContainer"]:has(.wm-question-anchor) + div[data-testid="stLayoutWrapper"] [data-testid="stHorizontalBlock"] {{
          min-height: 7rem;
          padding: 1.05rem 1.1rem 1rem 1.35rem;
          background: #082a4f;
          align-items: center;
        }}
        div[data-testid="stElementContainer"]:has(.wm-question-anchor) + div[data-testid="stLayoutWrapper"] [data-testid="stTextArea"] label {{ color: #95dfe8 !important; }}
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
          color: white !important;
          background: transparent !important;
          box-shadow: none !important;
          font-family: 'Atkinson Hyperlegible Next', 'Arial', sans-serif !important;
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
          color: #082a4f;
          background: var(--cyan);
          font-weight: 700;
          box-shadow: none;
        }}
        div[data-testid="stElementContainer"]:has(.wm-question-anchor) + div[data-testid="stLayoutWrapper"] [data-testid="stFormSubmitButton"] button:hover {{
          color: #082a4f;
          background: #72e2ee;
          transform: translateY(-1px);
        }}
        div[data-testid="stElementContainer"]:has(.wm-question-anchor) + div[data-testid="stLayoutWrapper"] [data-testid="stFormSubmitButton"] button:active {{ transform: scale(.98); }}
        button:focus-visible, input:focus-visible {{ outline: 3px solid #55d7e8 !important; outline-offset: 3px; }}

        .wm-trust {{
          display: flex;
          justify-content: center;
          flex-wrap: wrap;
          gap: .7rem 1.6rem;
          margin: 1.1rem auto 3.4rem;
          color: #4f6a7d;
          font-size: .78rem;
          font-weight: 520;
        }}
        .wm-trust span::before {{ content: ''; display: inline-block; width: 7px; height: 7px; margin-right: 8px; border-radius: 50%; background: var(--cyan); box-shadow: 0 0 0 4px rgba(85,215,232,.16); }}
        [data-testid="stSpinner"] {{ color: var(--navy); }}

        .wm-answer-shell {{
          width: 100vw;
          margin-left: calc(50% - 50vw);
          background: var(--paper);
          clip-path: polygon(0 2.2rem, 24% .7rem, 45% 2rem, 67% .5rem, 84% 1.8rem, 100% .9rem, 100% 100%, 0 100%);
        }}
        .wm-answer {{ max-width: 1040px; margin: 0 auto; padding: 5.5rem 2rem 4.1rem; }}
        .wm-answer h2 {{
          max-width: 860px;
          margin: 0 0 1.2rem;
          color: var(--navy) !important;
          font-family: 'Familjen Grotesk', 'Arial', sans-serif !important;
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
          font-family: 'Literata', Georgia, serif;
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
        .wm-explanation {{ display: grid; grid-template-columns: minmax(0,1.3fr) minmax(240px,.7fr); gap: 3rem; align-items: start; margin-top: 2.4rem; }}
        .wm-explanation h3 {{ margin: 0 0 .5rem; font-size: 1rem; font-weight: 620; }}
        .wm-explanation p {{ max-width: 66ch; margin: 0; color: #597084; font-size: .88rem; line-height: 1.6; }}
        .wm-readouts {{ display: flex; justify-content: flex-end; gap: 2.4rem; }}
        .wm-readout strong {{ display: block; color: var(--blue); font-size: 1.15rem; font-weight: 620; font-variant-numeric: tabular-nums; }}
        .wm-readout small {{ color: #6b7f8e; font-size: .67rem; letter-spacing: .06em; text-transform: uppercase; }}
        .wm-refusal h2 span {{ color: #b53838; }}
        .wm-footer {{ margin: 2.4rem auto 0; text-align: center; color: #60798b; font-size: .72rem; }}

        @media (max-width: 700px) {{
          [data-testid="stMainBlockContainer"] {{ padding: 1.4rem .75rem 1.5rem; }}
          .wm-logo {{ width: 118px; height: 118px; }}
          div[data-testid="stMarkdownContainer"] h1.wm-title {{ font-size: 2.65rem !important; margin-top: .45rem; }}
          .wm-promise {{ max-width: 34rem; font-size: .96rem; white-space: normal; }}
          .wm-dial-wrap {{ display: none; }}
          [data-testid="stForm"] [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important; gap: .75rem; }}
          [data-testid="stForm"] [data-testid="column"]:has(.wm-dial-wrap) {{ display: none; }}
          [data-testid="stForm"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{ min-width: 0 !important; }}
          div[data-testid="stElementContainer"]:has(.wm-question-anchor) + div[data-testid="stLayoutWrapper"] [data-testid="stColumn"]:first-child {{ flex: 1 1 auto !important; width: auto !important; }}
          div[data-testid="stElementContainer"]:has(.wm-question-anchor) + div[data-testid="stLayoutWrapper"] [data-testid="stColumn"]:last-child {{ flex: 0 0 64px !important; width: 64px !important; }}
          div[data-testid="stElementContainer"]:has(.wm-question-anchor) + div[data-testid="stLayoutWrapper"] [data-testid="stHorizontalBlock"] {{ min-height: 8rem; padding: .9rem 1rem; }}
          div[data-testid="stElementContainer"]:has(.wm-question-anchor) + div[data-testid="stLayoutWrapper"] [data-testid="stTextArea"] textarea {{ font-size: 1rem !important; }}
          div[data-testid="stElementContainer"]:has(.wm-question-anchor) + div[data-testid="stLayoutWrapper"] [data-testid="stFormSubmitButton"] button {{ width: 64px; height: 64px; }}
          .wm-trust {{ margin-bottom: 2.8rem; gap: .65rem 1.1rem; font-size: .72rem; }}
          .wm-answer-shell {{ clip-path: polygon(0 1.3rem, 33% .3rem, 64% 1.2rem, 100% .45rem, 100% 100%, 0 100%); }}
          .wm-answer {{ padding: 4.1rem 1.25rem 3rem; }}
          .wm-answer h2 {{ font-size: 2rem; }}
          p.wm-answer-copy {{ font-size: 1.16rem !important; line-height: 1.64 !important; }}
          .wm-source {{ grid-template-columns: 42px minmax(0,1fr); gap: .8rem; }}
          .wm-page {{ width: 42px; height: 42px; font-size: .84rem; }}
          .wm-source a {{ display: none; }}
          .wm-source-name {{ font-size: .9rem; }}
          .wm-source-meta {{ font-size: .76rem; }}
          .wm-explanation {{ grid-template-columns: 1fr; gap: 1.5rem; }}
          .wm-readouts {{ justify-content: flex-start; }}
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
    st.markdown(
        f"""
        <section class="wm-hero">
          <img class="wm-logo" src="{logo}" alt="Washing Machine Manual Assistant logo">
          <h1 class="wm-title"><span class="wm-title-line wm-title-line-primary">Washing Machine</span><span class="wm-title-line wm-title-line-accent">Manual Assistant</span></h1>
          <p class="wm-promise">Ask in your own words. Get a model-specific answer from the official manual, with the exact page shown or a clear refusal when the manual does not say.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def trusted_url(raw_url: str) -> str:
    """Allow only ordinary HTTP links from the checked manifest."""
    parsed = urlparse(raw_url)
    return raw_url if parsed.scheme in {"http", "https"} else "#"


def format_cost(value: Any) -> str:
    """Format small API costs without implying unavailable precision."""
    if value is None:
        return "Not reported"
    return f"${float(value):.8f}".rstrip("0").rstrip(".")


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

    usage = result.get("usage") or {}
    readouts = ""
    if usage:
        latency = html.escape(f"{float(usage.get('latency_seconds', 0)):.2f}s")
        cost = html.escape(format_cost(usage.get("estimated_cost_usd")))
        readouts = (
            f'<div class="wm-readouts"><div class="wm-readout"><strong>{latency}</strong>'
            f'<small>Answer time</small></div><div class="wm-readout"><strong>{cost}</strong>'
            '<small>Estimated cost</small></div></div>'
        )

    explanation_title = "Why this answer is shown" if answered else "Why the assistant refused"
    css_class = "wm-answer" if answered else "wm-answer wm-refusal"
    sources_html = f'<div class="wm-sources">{"".join(source_rows)}</div>' if source_rows else ""
    result_html = (
        f'<section class="wm-answer-shell"><div class="{css_class}"><h2>{heading}</h2>'
        f'<p class="wm-answer-copy">{answer}</p>{sources_html}'
        f'<div class="wm-explanation"><div><h3>{explanation_title}</h3>'
        f'<p>{reason} The request was routed only to {html.escape(brand)} '
        f'{html.escape(model)}.</p></div>{readouts}</div></div></section>'
    )
    st.markdown(result_html, unsafe_allow_html=True)


def user_facing_error(error: Exception) -> str:
    """Translate API and configuration failures into actionable UI copy."""
    if isinstance(error, AuthenticationError):
        return "OpenRouter rejected the API key. Check OPENROUTER_API_KEY in the local .env file."
    if isinstance(error, PermissionDeniedError):
        return "The configured OpenRouter key cannot use the selected model. Check its model permissions."
    if isinstance(error, RateLimitError):
        return "The request reached an OpenRouter rate, credit, or spending limit. Check the account and try again."
    if isinstance(error, APIConnectionError):
        return "The app could not connect to OpenRouter. Check the internet connection and try again."
    if isinstance(error, BadRequestError):
        return "OpenRouter rejected the request. Check the selected model configuration."
    return str(error)


def main() -> None:
    inject_styles()
    render_hero()
    catalogue = load_catalogue()
    brands = list(catalogue)
    default_brand = brands.index("Gaggenau") if "Gaggenau" in brands else 0

    brand_column, dial_column, model_column = st.columns([1, 0.24, 1])
    with brand_column:
        brand = st.selectbox("Brand", brands, index=default_brand)
    with dial_column:
        st.markdown('<div class="wm-dial-wrap"><div class="wm-dial">MODEL</div></div>', unsafe_allow_html=True)
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
        <div class="wm-trust">
          <span>Exact-model filter active</span>
          <span>Official manual only</span>
          <span>Evidence required before answering</span>
        </div>
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
                    )
                    st.session_state["answer_brand"] = brand
                    st.session_state["answer_model"] = model
            except (
                RetrievalInputError,
                GenerationConfigurationError,
                FileNotFoundError,
                AuthenticationError,
                PermissionDeniedError,
                RateLimitError,
                APIConnectionError,
                BadRequestError,
            ) as error:
                st.error(user_facing_error(error))

    if "answer_result" in st.session_state:
        render_result(
            st.session_state["answer_result"],
            st.session_state["answer_brand"],
            st.session_state["answer_model"],
        )

    st.markdown(
        '<div class="wm-footer">Five verified manuals / Source-aware answers / Designed for safe refusal</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
