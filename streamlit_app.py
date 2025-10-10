# Ensure python-docx is installed before any imports
import streamlit as st
import os
import json
from datetime import datetime
from openai import OpenAI
import traceback
from typing import List, Dict
import tempfile

# Show title and description.
st.title("💬 Service Advisor Review")
st.write(
    "This is a chatbot that uses OpenAI's GPT-5 model to generate responses. "
   " To use this app, upload a .mp3 voicemail file and hit 'send'."
)

# Sidebar for API key input
st.sidebar.header("OpenAI API Key")
if "api_key" not in st.session_state:
    st.session_state.api_key = ""
api_key_input = st.sidebar.text_input(
    "Enter your OpenAI API key", 
    value=st.session_state.api_key, 
    type="password"
)
st.session_state.api_key = api_key_input

ASSISTANT_MODEL = "gpt-5"
ASSISTANT_INSTRUCTIONS = (
    "Review uploaded voicemails between service advisors within the automotive repair industry and customers. "
    "Fill out the corresponding Fix My Call Template with input from the audio file and reference the Sales Fix training courses "
    "when recommending next steps for improvement. Maintain a professional and positive tone and focus on creating top of the line sales teams. "
    "Reference the Example Voicemail file as a base for showing what the transcription of audio should look like and what the analysis from the coach should be. "
    "This GPT can also reference https://www.salesfix.com/ for suggestions. This GPT is only for service advisor help in the automotive industry, any other questions should result in a response of 'I am only a service advisor expert, please ask a relevant question.' "
    "When responding to the attached audio clip, automatically fill out the Fix My Call Template and format for .docx files. Remove pre and post text. The document should have bold headers for each section, the spacing should be unified with no line section breaks, the font should be unified and size 12, the title should be 'Fix My Call' with today's date and the name of the service advisor from the call. "
    "The sections for review should be 'Impression [Tonality/Charisma/Speed/Word Choice]' and 'Leadership & Professionalism [Conciseness/Confidence/Preparedness]' and 'Execution [Scripts Used/Driving Conversation/Achieved Goals]'"
    "Each section should contain notes beneath the score"
    "In the individual sections, the scoring should be highlighted red and all the options should always be displayed. The overall score should be calculated using a base of 55%, each section can add to that score for a total of 100%. "
    "A section score of Okay results in 5% increase, Good is 10% increase, and Great is 15% increase."
    "The bottom should have an overall score, then 'Your Reviewing Trainer: Mike Tatich'"
)
ASSISTANT_TOOLS = [
    {"type": "file_search", "vector_store_ids": ["vs_68961cff51bc8191a8a5f825639a7d51"]}
]

# ---------- App state ----------
if "conversation" not in st.session_state:
    st.session_state.conversation = []
if "attached_files" not in st.session_state:
    st.session_state.attached_files = []

# ---------- Helpers ----------
def get_openai_client():
    if not st.session_state.api_key:
        st.error("Please enter your OpenAI API key in the sidebar.")
        return None
    return OpenAI(api_key=st.session_state.api_key)


def transcribe_file(file) -> str:
    client = get_openai_client()
    if client is None:
        return "[No API key provided]"
    resp = client.audio.transcriptions.create(model="gpt-4o-mini-transcribe", file=file)
    return resp.text


def build_combined_user_text(user_text: str, files) -> str:
    transcripts = []
    for uploaded_file in files:
        try:
            t = transcribe_file(uploaded_file)
            transcripts.append((uploaded_file.name, t))
        except Exception as e:
            transcripts.append((uploaded_file.name, f"[TRANSCRIPTION ERROR: {e}]"))
    if transcripts:
        parts = []
        if user_text.strip():
            parts.append(user_text.strip())
        blocks = [f"--- Transcript: {fname} ---\n{text}" for fname, text in transcripts]
        parts.append("\n\n".join(blocks))
        combined = "\n\n".join(parts)
    else:
        combined = user_text.strip() or "(no text, see attachments)"
    return combined

# ---------- Responses API call ----------

def _json_schema_instruction() -> str:
    return (
        "When an audio clip is attached, output ONLY the following JSON (no prose before or after):"
        "{"
        "  \"advisor_name\": \"...\","
        "  \"date_iso\": \"YYYY-MM-DD\","
        "  \"sections\": ["
        "    {"
        "      \"name\": \"Impression [Tonality/Charisma/Speed/Word Choice]\","
        "      \"rating\": \"Needs Work|Okay|Good|Great\","
        "      \"notes\": \"coach analysis\","
        "      \"options\": [\"Needs Work\",\"Okay\",\"Good\",\"Great\"]"
        "    },"
        "    { \"name\": \"Leadership & Professionalism [Conciseness/Confidence/Preparedness]\", \"rating\": \"...\", \"notes\": \"...\", \"options\": [\"Needs Work\",\"Okay\",\"Good\",\"Great\"] },"
        "    { \"name\": \"Execution [Scripts Used/Driving Conversation/Achieved Goals]\", \"rating\": \"...\", \"notes\": \"...\", \"options\": [\"Needs Work\",\"Okay\",\"Good\",\"Great\"] },"
        "  ],"
        "  \"next_steps\": [\"...\", \"...\"],"
        "  \"transcript\": \"verbatim or cleaned transcript\""
        "}"
        "Ensure ratings reflect the call; always include all options in each section."
    )


def call_responses(conversation_messages: List[Dict], attachments_present: bool):
    client = get_openai_client()
    if client is None:
        return type("DummyResp", (), {"output_text": "[No API key provided]"})()
    input_messages = []
    if ASSISTANT_INSTRUCTIONS:
        input_messages.append({"role": "system", "content": ASSISTANT_INSTRUCTIONS})
    if attachments_present:
        input_messages.append({"role": "system", "content": _json_schema_instruction()})
    input_messages.extend(conversation_messages)

    kwargs = {"model": ASSISTANT_MODEL, "input": input_messages}
    if ASSISTANT_TOOLS:
        kwargs["tools"] = ASSISTANT_TOOLS
    return client.responses.create(**kwargs)

# ---------- Main request ----------

def do_request(user_text: str, files):
    try:
        combined = build_combined_user_text(user_text, files)
        st.session_state.conversation.append({"role": "user", "content": combined})

        resp = call_responses(st.session_state.conversation, attachments_present=bool(files))
        reply = getattr(resp, "output_text", None)
        if not reply:
            st.error("Responses API returned no text output.")
            return

        st.session_state.conversation.append({"role": "assistant", "content": reply})
        st.markdown(f"**Assistant:** {reply}")

    except Exception as e:
        tb = traceback.format_exc()
        st.error(f"Error: {type(e).__name__}: {e}")
        with open("error.log", "a", encoding="utf-8") as log:
            log.write(tb + "")
    finally:
        st.session_state.attached_files = []

# ---------- Streamlit UI ----------
uploaded_files = st.file_uploader("Attach MP3 files", type=["mp3"], accept_multiple_files=True)
user_input = st.text_area("Type your message", height=100)

if st.button("Send"):
    do_request(user_input, uploaded_files or [])

# Display conversation
for msg in st.session_state.conversation:
    if msg["role"] == "user":
        st.markdown(f"**You:** {msg['content']}")
    else:
        st.markdown(f"**Assistant:** {msg['content']}")
