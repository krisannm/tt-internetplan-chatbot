import glob
import json
import os

import google.generativeai as genai
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

import plans_data as pdata

MODEL_NAME = "gemini-3.5-flash-lite"  # if Google retires it, change it here only

load_dotenv()
try:
    api_key = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
except Exception:
    api_key = None
genai.configure(api_key=api_key)

PLAN_TYPES = {
    "Home Broadband": "home_broadband",
    "Mobile Prepaid": "mobile_prepaid",
    "Mobile Postpaid": "mobile_postpaid",
}

# ── DATA: always derived from the dates in the JSON ──────────────────────────
@st.cache_data
def load_all():
    return pdata.load_all()


ALL = load_all()
AS_OF = pdata.today_tt()
CURRENT = pdata.current_plans(ALL, AS_OF)
UPCOMING = pdata.upcoming_changes(ALL, AS_OF)


def build_system_prompt(selected_types):
    plans = CURRENT[CURRENT["plan_type"].isin(selected_types)]
    upcoming = UPCOMING[UPCOMING["plan_type"].isin(selected_types)]
    upcoming_lines = [
        f"- {r.provider} {r.plan_name}: ${r.current_price_ttd:,.2f} -> ${r.price_ttd:,.2f} from {r.effective_date:%d %b %Y}"
        for r in upcoming.itertuples()
    ]
    return f"""
You are a helpful assistant that helps people in Trinidad and Tobago choose the
best home internet or mobile plan for their needs. Today is {AS_OF:%d %B %Y}.

Use ONLY the plan data below. Prices are in TTD, VAT inclusive, taken from the
TATT (Telecommunications Authority of T&T) price schedules and operator notices.
Each plan has a "plan_type": "home_broadband", "mobile_prepaid" or "mobile_postpaid".

Rules:
- Never invent plans, prices, speeds or data amounts. A field that is missing
  means it was not stated - say so instead of guessing.
- "unlimited_anywhere_minutes": true means unlimited Anywhere minutes.
- "validity_days" is how long a mobile plan lasts. Compare plans of different
  lengths fairly (e.g. a 3-day plan is not the same as a 30-day plan).
- The data has no coverage or location information. If the user's area matters,
  tell them to check the provider's coverage map before buying.
- If a request could mean home internet or mobile data, ask a short clarifying
  question first.
- Explain your recommendation briefly: price, data or speed, and why it fits.
  Sound like a knowledgeable friend, not a sales pitch.

CURRENT PLANS:
{json.dumps(pdata.to_prompt_records(plans), separators=(",", ":"))}

PRICE CHANGES ALREADY ANNOUNCED (mention them if relevant to the user's choice):
{chr(10).join(upcoming_lines) if upcoming_lines else "None."}
""".strip()


# ── TABLE HELPERS ────────────────────────────────────────────────────────────
def mins_label(row):
    if bool(row["unlimited_anywhere_minutes"]):
        return "Unlimited"
    return "Not stated" if pd.isna(row["anywhere_minutes"]) else f"{int(row['anywhere_minutes']):,}"


def make_table(df, plan_type, show_status):
    d = df[df["plan_type"] == plan_type].copy()
    d["Anywhere mins"] = d.apply(mins_label, axis=1)
    d["Rollover"] = d["rollover_data"].map({True: "Yes", False: "No"}).fillna("Not stated")
    d["Price from"] = d["effective_date"].dt.strftime("%Y-%m-%d")
    d["Last verified"] = d["last_verified"].dt.strftime("%Y-%m-%d")
    d = d.rename(columns={
        "provider": "Provider", "plan_name": "Plan", "price_ttd": "Price (TTD)",
        "validity_days": "Validity (days)", "data_gb": "Data (GB)", "roaming_gb": "Roaming (GB)",
        "download_speed_mbps": "Download (Mbps)", "upload_speed_mbps": "Upload (Mbps)",
        "connection_type": "Connection", "notes": "Notes", "source": "Source",
    })
    if plan_type == "home_broadband":
        cols = ["Provider", "Plan", "Price (TTD)", "Download (Mbps)", "Upload (Mbps)", "Connection"]
    elif plan_type == "mobile_prepaid":
        cols = ["Provider", "Plan", "Price (TTD)", "Validity (days)", "Data (GB)", "Anywhere mins", "Roaming (GB)", "Rollover"]
    else:
        cols = ["Provider", "Plan", "Price (TTD)", "Data (GB)", "Anywhere mins", "Roaming (GB)", "Rollover"]
    cols += ["Price from", "Last verified", "Notes", "Source"]
    if show_status:
        cols = ["Status"] + cols
        d["Status"] = d["status_label"]
    return d[cols]


COLUMN_CONFIG = {
    "Price (TTD)": st.column_config.NumberColumn(format="$%.2f"),
    "Notes": st.column_config.TextColumn(width="large"),
}

# ── "WHAT SHOULD I TELL IT?" HINTS (collapsed by default) ───────────────────
HOME_HINTS = [
    "How many people live in your home",
    "How many devices connect to your wifi",
    "Roughly how many hours a day people are online",
    "What you mostly do: streaming, gaming, working from home, video calls, online classes",
    "Your monthly budget",
]
MOBILE_HINTS = [
    "Apps and websites you use most (WhatsApp, YouTube, TikTok, Netflix...)",
    "Hours a day on mobile data (not wifi), and whether you use a hotspot",
    "Calls: how many, and any international calls or travel",
    "How many lines you need (just you, or family)",
    "Pay upfront (prepaid) or billed monthly (postpaid), and your budget",
]


def show_hints(selected_types):
    want_home = "home_broadband" in selected_types
    want_mobile = any(t in selected_types for t in ("mobile_prepaid", "mobile_postpaid"))
    with st.expander("💡 What should I tell the chatbot?"):
        blocks = []
        if want_home:
            blocks.append(("🏠 Home broadband", HOME_HINTS))
        if want_mobile:
            blocks.append(("📱 Mobile (prepaid or postpaid)", MOBILE_HINTS))
        for col, (title, items) in zip(st.columns(len(blocks)), blocks):
            with col:
                st.markdown(f"**{title}**")
                st.markdown("\n".join(f"- {i}" for i in items))
        st.caption(
            'Example: "4 people, about 8 devices, lots of Netflix and online classes, budget around $350 a month."  '
            "The more detail you give, the better the match. I can't check coverage at your address, "
            "so confirm that with the provider before you buy."
        )


# ── PAGE ─────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="TT Plan Finder", page_icon="📶", layout="wide")
st.title("TT Data and Broadband Finder")
st.caption(f"Prices in effect on {AS_OF:%d %B %Y}, from TATT price schedules and operator notices.")

st.sidebar.header("Filter plan types")
selected_labels = st.sidebar.multiselect("Only consider:", options=list(PLAN_TYPES), default=list(PLAN_TYPES))
selected_types = [PLAN_TYPES[x] for x in selected_labels] or list(PLAN_TYPES.values())

tab_chat, tab_tables = st.tabs(["💬 Plan finder chat", "📋 Browse all plans"])

# ── CHAT TAB ─────────────────────────────────────────────────────────────────
with tab_chat:
    filter_key = tuple(sorted(selected_types))
    if st.session_state.get("filter_key") != filter_key:
        st.session_state.filter_key = filter_key
        model = genai.GenerativeModel(model_name=MODEL_NAME, system_instruction=build_system_prompt(selected_types))
        st.session_state.chat = model.start_chat(history=[])
        st.session_state.messages = []

    show_hints(selected_types)

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Tell me about your household or phone use and your budget...")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = st.session_state.chat.send_message(user_input)
                st.markdown(response.text)
        st.session_state.messages.append({"role": "assistant", "content": response.text})

# ── TABLES TAB ───────────────────────────────────────────────────────────────
with tab_tables:
    if not UPCOMING.empty:
        lines = [
            f"**{r.provider} {r.plan_name}**: ${r.current_price_ttd:,.2f} → ${r.price_ttd:,.2f} from {r.effective_date:%d %b %Y}"
            for r in UPCOMING.itertuples()
        ]
        st.info("**Announced price changes not yet in effect**\n\n" + "\n\n".join(f"- {x}" for x in lines))

    c1, c2 = st.columns([3, 2])
    providers = sorted(ALL["provider"].unique())
    chosen = c1.multiselect("Provider", providers, default=providers)
    show_history = c2.checkbox("Show price history (every recorded price)", value=False)

    source_df = pdata.history_with_status(ALL, AS_OF) if show_history else CURRENT.assign(status_label="Current")
    source_df = source_df[source_df["provider"].isin(chosen)]

    t_bb, t_pre, t_post = st.tabs(["Home Broadband", "Mobile Prepaid", "Mobile Postpaid"])
    for tab, ptype in zip((t_bb, t_pre, t_post), PLAN_TYPES.values()):
        with tab:
            table = make_table(source_df, ptype, show_history)
            st.caption(f"{table['Plan'].nunique()} plans")
            st.dataframe(table, hide_index=True, column_config=COLUMN_CONFIG, width="stretch")

    with st.expander("Verify the data yourself (source documents)"):
        st.write(
            "Every row lists its source. The TATT price schedules are public documents "
            "published at tatt.org.tt; copies of the ones used here are below. "
            "Always confirm with the provider before buying."
        )
        for path in sorted(glob.glob("sources/*.pdf")):
            with open(path, "rb") as f:
                st.download_button(os.path.basename(path), f.read(), file_name=os.path.basename(path), mime="application/pdf", key=path)
