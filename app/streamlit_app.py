"""
SAS to Python converter: drag in SAS programs, get Python files and a
finance summary out.

Run locally:   streamlit run app/streamlit_app.py
Secrets (Streamlit Cloud > App settings > Secrets, or .streamlit/secrets.toml):
    GEMINI_API_KEY = "..."      # required; stays on the server
    ACCESS_CODE = "..."         # required; share only with people who should use the key
    DAILY_TRANSLATION_LIMIT = 50                   # optional
    GEMINI_INPUT_PRICE_PER_M = 0.0                 # optional, USD per 1M tokens (0 = free tier)
    GEMINI_OUTPUT_PRICE_PER_M = 0.0                # optional
"""
from __future__ import annotations

import io
import os
import sys
import zipfile
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))

import finance  # noqa: E402
import guard  # noqa: E402
from translator import MODEL, TokenUsageTracker, order_files, translate_files  # noqa: E402

EXAMPLE_DIR = APP_DIR.parent / "src" / "translation" / "sas_files"

st.set_page_config(page_title="SAS to Python Converter", page_icon="🔁", layout="wide")


def secret(name: str, default=None):
    """An environment variable, else a Streamlit secret, else the default."""
    if os.environ.get(name):
        return os.environ[name]
    try:
        # without this, a missing secrets.toml shows Streamlit's own error (with server paths)
        st.secrets.set_suppress_print_error_on_exception(True)
        return st.secrets.get(name, default)
    except Exception:  # no secrets file at all
        return default


@st.cache_resource
def daily_limit() -> guard.DailyLimit:
    return guard.DailyLimit(int(secret("DAILY_TRANSLATION_LIMIT", guard.DEFAULT_DAILY_LIMIT)))


def session_guard() -> guard.SessionGuard:
    if "guard" not in st.session_state:
        st.session_state.guard = guard.SessionGuard()
    return st.session_state.guard


# ---------------------------------------------------------------- header
st.title("SAS to Python Converter")
st.caption("Drop in SAS programs and get Python translations plus an estimated finance summary. "
           f"Powered by Google Gemini ({MODEL}).")

api_key, access_code = secret("GEMINI_API_KEY"), secret("ACCESS_CODE")
if not api_key or not access_code:
    st.error("This app isn't configured yet: the owner needs to add `GEMINI_API_KEY` and `ACCESS_CODE` "
             "to the app's secrets.")
    st.stop()

# ---------------------------------------------------------------- access code
g = session_guard()
if not st.session_state.get("unlocked"):
    wait = g.locked()
    with st.form("access"):
        st.subheader("Enter the access code")
        st.write("Translations use a shared API key, so access is limited to people with the code.")
        entered = st.text_input("Access code", type="password")
        submitted = st.form_submit_button("Unlock", disabled=wait > 0)
    if wait > 0:
        st.warning(f"Too many wrong codes. Try again in {int(wait // 60) + 1} minute(s).")
    elif submitted:
        if guard.code_matches(entered, access_code):
            st.session_state.unlocked = True
            st.rerun()
        else:
            g.record_failed_code()
            st.error("That code isn't right.")
    st.stop()

# ---------------------------------------------------------------- sidebar: assumptions
defaults = finance.default_assumptions()
with st.sidebar:
    st.header("Finance assumptions")
    st.caption("Defaults are placeholders from `config/cost_assumptions.json`. Use your organization's figures.")
    a = dict(defaults)
    a["sas_annual_license_cost"] = st.number_input(
        "SAS licence cost per year (for these programs)", min_value=0.0,
        value=float(defaults["sas_annual_license_cost"]), step=500.0)
    a["license_allocation"] = st.radio(
        "Split licence cost by", ["lines_of_code", "equal"],
        index=0 if defaults.get("license_allocation") != "equal" else 1,
        format_func=lambda v: "Lines of code" if v == "lines_of_code" else "Equally")
    col1, col2 = st.columns(2)
    a["sas_maintenance_hours_per_script"] = col1.number_input(
        "SAS upkeep h/yr per script", min_value=0.0, value=float(defaults["sas_maintenance_hours_per_script"]))
    a["python_maintenance_hours_per_script"] = col2.number_input(
        "Python upkeep h/yr per script", min_value=0.0, value=float(defaults["python_maintenance_hours_per_script"]))
    a["sas_developer_hourly_rate"] = col1.number_input(
        "SAS dev rate /h", min_value=0.0, value=float(defaults["sas_developer_hourly_rate"]))
    a["python_developer_hourly_rate"] = col2.number_input(
        "Python dev rate /h", min_value=0.0, value=float(defaults["python_developer_hourly_rate"]))
    st.subheader("Token prices (USD per 1M)")
    st.caption("Leave at 0 when using the free tier.")
    input_price = st.number_input("Input", min_value=0.0, value=float(secret("GEMINI_INPUT_PRICE_PER_M", 0.0)),
                                  format="%.4f")
    output_price = st.number_input("Output", min_value=0.0, value=float(secret("GEMINI_OUTPUT_PRICE_PER_M", 0.0)),
                                   format="%.4f")
    st.divider()
    st.caption(f"Your translations left this hour: {g.runs_left()} of {guard.RUNS_PER_HOUR}  \n"
               f"App translations left today: {daily_limit().remaining()}")

# ---------------------------------------------------------------- 1. upload
st.subheader("1. Add SAS files")
st.info("Don't upload confidential code. Files are sent to Google's Gemini API for translation, "
        "and free-tier requests may be used by Google to improve its products.", icon="ℹ️")
uploads = st.file_uploader(f"Drag and drop .sas files here (up to {guard.MAX_FILES} files, "
                           f"{guard.MAX_FILE_BYTES // 1000} KB each)", type=["sas"], accept_multiple_files=True,
                           help=f"Up to {guard.MAX_FILES} files, {guard.MAX_FILE_BYTES // 1000} KB each. "
                                "Upload related programs together (e.g. macros + the programs that use them).")
use_example = st.toggle("Use the example instead: the CMS hospital star rating programs (4 files)",
                        value=False)

if use_example:
    files = [(p.name, p.read_bytes()) for p in sorted(EXAMPLE_DIR.glob("*.sas"))]
else:
    files = [(u.name, u.getvalue()) for u in (uploads or [])]

if files:
    problems = guard.check_uploads(files)
    order = [name for name, _ in order_files([(n, "") for n, _ in files])]
    st.write("**Translation order:** " + " → ".join(f"`{n}`" for n in order))
    for p in problems:
        st.error(p)
else:
    problems = ["no files"]

# ---------------------------------------------------------------- 2. translate
st.subheader("2. Convert")
runs_left, today_left = g.runs_left(), daily_limit().remaining()
blocked = None
if runs_left == 0:
    blocked = "You've used all your translations for this hour. Try again later."
elif today_left == 0:
    blocked = "The app has reached today's translation limit. Try again tomorrow."
if blocked:
    st.warning(blocked)

if st.button("Convert to Python", type="primary", disabled=bool(problems) or bool(blocked)):
    if not daily_limit().take():
        st.warning("The app has reached today's translation limit. Try again tomorrow.")
        st.stop()
    g.record_run()
    usage = TokenUsageTracker(model=MODEL)
    sources = [(name, guard.decode_sas(data)) for name, data in files]
    progress = st.progress(0.0, text="Starting…")

    def on_progress(i, n, name):
        progress.progress((i - 1) / n, text=f"Translating {i} of {n}: {name}")

    try:
        with st.spinner("Translating with Gemini…"):
            results = translate_files(sources, api_key=api_key, usage=usage, on_progress=on_progress)
    except Exception as exc:  # API errors: quota, invalid key, network
        progress.empty()
        msg = str(exc)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            st.error("The API key's quota is used up for now. Try again later.")
        elif "API key" in msg or "401" in msg or "403" in msg:
            st.error("The server's API key was rejected. The app owner needs to check it.")
        else:
            st.error(f"Translation failed: {type(exc).__name__}")
        st.stop()
    st.session_state.results = results
    st.session_state.usage = usage
    st.rerun()  # refresh so the sidebar's remaining-translation counts are current

# ---------------------------------------------------------------- 3. results
results = st.session_state.get("results")
if results:
    usage = st.session_state.usage
    summary = finance.finance_summary(results, usage, a, input_price, output_price)
    t, cur = summary["totals"], summary["currency"]

    st.subheader("3. Results")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Estimated savings / year", f"{cur} {t['annual_savings']:,.0f}")
    m2.metric("First-year net", f"{cur} {t['first_year_net_savings']:,.0f}")
    m3.metric("AI conversion cost", f"{cur} {t['ai_conversion_cost']:,.4f}",
              help="Translation tokens only, with no review labor. $0 when token prices are 0 (free tier).")
    m4.metric("Tokens used", f"{t['tokens_used']:,}" if t["tokens_used"] is not None else "n/a")

    bad = [r for r in results if not r.syntax_ok]
    if bad:
        st.warning(f"{len(bad)} file(s) came back with Python syntax errors. Review them before use.")
    st.caption("AI-generated code is syntax-checked but not executed or validated against SAS output. "
               "Review and test it before relying on it.")

    tab_code, tab_finance = st.tabs(["Python files", "Finance summary"])
    with tab_code:
        for r in results:
            status = "✅ syntax OK" if r.syntax_ok else f"⚠️ syntax error ({r.syntax_error})"
            secs = f"{r.seconds:.1f}s" if r.seconds is not None else "n/a"
            toks = f"{r.tokens:,} tokens" if r.tokens is not None else "tokens n/a"
            with st.expander(f"{r.python_name}  ·  {status}  ·  {toks}  ·  {secs}", expanded=len(results) == 1):
                left, right = st.columns(2)
                left.caption(f"SAS: {r.sas_name}")
                left.code(r.sas_source, language="sas")
                right.caption(f"Python: {r.python_name}")
                right.code(r.python_code, language="python")
                st.download_button(f"Download {r.python_name}", r.python_code, file_name=r.python_name,
                                   mime="text/x-python", key=f"dl-{r.python_name}")
    with tab_finance:
        shown = [c for c in finance.COLUMNS if c[0] not in ("sas_lines", "license_share_pct")]
        rows = [{label: row.get(key) for key, label in shown} for row in summary["scripts"]]
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.caption("Savings/yr = SAS cost (licence share + upkeep) − Python cost (upkeep). Scripts aren't run "
                   "here, so compute savings aren't included. Licence savings only happen if the SAS "
                   "licence is reduced or retired. Change the assumptions in the sidebar.")
        st.download_button("Download finance summary (CSV)", finance.summary_csv(summary),
                           file_name="finance_summary.csv", mime="text/csv")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for r in results:
            z.writestr(f"python/{r.python_name}", r.python_code)
        z.writestr("finance_summary.csv", finance.summary_csv(summary))
        z.writestr("summary.md", finance.summary_markdown(summary, results))
    st.download_button("⬇️ Download everything (.zip)", buffer.getvalue(), file_name="sas_to_python.zip",
                       mime="application/zip", type="primary")
