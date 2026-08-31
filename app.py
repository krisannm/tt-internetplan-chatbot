import streamlit as st
import google.generativeai as genai
import json
import os
from dotenv import load_dotenv

# Load API key
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# Load your unified plan data once
with open("tt_all_plans.json", "r") as f:
    ALL_PLANS = json.load(f)

# Split by plan_type so the sidebar filter and prompt context can use it
PLAN_TYPES = {
    "Home Broadband": "home_broadband",
    "Mobile Prepaid": "mobile_prepaid",
    "Mobile Postpaid": "mobile_postpaid",
}

def build_system_prompt(selected_types):
    """Builds the system prompt using only the plan types the user wants considered."""
    filtered = [p for p in ALL_PLANS if p["plan_type"] in selected_types]

    return f"""
You are a helpful assistant that helps people in Trinidad and Tobago choose
the best home internet or mobile plan for their needs.

Here is the current plan data you must use to answer questions. Every plan
has a "plan_type" field — either "home_broadband", "mobile_prepaid", or
"mobile_postpaid" — use this to understand what kind of plan each one is.

Do not make up plans, prices, speeds, or data amounts that are not in this
data. If information is missing (e.g. speed not stated), say so honestly
instead of guessing.

PLAN DATA:
{json.dumps(filtered, indent=2)}

When recommending a plan, explain your reasoning briefly — mention price,
data/speed, and why it fits what the user described. If the user's request
could reasonably be answered by more than one plan_type (e.g. they didn't
specify home internet vs mobile data), ask a quick clarifying question
before recommending. Keep responses conversational and concise, like a
knowledgeable friend, not a sales pitch.
"""

# ── STREAMLIT UI ──────────────────────────────────────────────────────────
st.set_page_config(page_title="TT Plan Finder", page_icon="📶")
st.title("📶 TT Internet & Mobile Plan Finder")
st.caption("Ask me anything about home broadband or mobile plans in Trinidad and Tobago")

# Sidebar — let the user scope which plan types Gemini should consider
st.sidebar.header("Filter plan types")
selected_labels = st.sidebar.multiselect(
    "Only consider:",
    options=list(PLAN_TYPES.keys()),
    default=list(PLAN_TYPES.keys()),
)
selected_types = [PLAN_TYPES[label] for label in selected_labels] or list(PLAN_TYPES.values())

# Rebuild the model if the filter selection changes
filter_key = tuple(sorted(selected_types))
if st.session_state.get("filter_key") != filter_key:
    st.session_state.filter_key = filter_key
    system_prompt = build_system_prompt(selected_types)
    model = genai.GenerativeModel(
        model_name="gemini-3.5-flash-lite",
        system_instruction=system_prompt,
    )
    st.session_state.chat = model.start_chat(history=[])
    st.session_state.messages = []

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display past messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
user_input = st.chat_input("e.g. I need cheap data for a household of 4...")

if user_input:
    # Show user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Get Gemini's response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = st.session_state.chat.send_message(user_input)
            st.markdown(response.text)

    st.session_state.messages.append({"role": "assistant", "content": response.text})