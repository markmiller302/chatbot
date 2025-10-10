import subprocess
import sys
import os

# Force install python-docx if not available
def install_python_docx():
    try:
        import docx
        return True
    except ImportError:
        try:
            # Try installing without --user flag for virtual environments
            subprocess.check_call([sys.executable, "-m", "pip", "install", "python-docx"])
            return True
        except subprocess.CalledProcessError:
            try:
                subprocess.check_call(["pip3", "install", "python-docx"])
                return True
            except subprocess.CalledProcessError:
                try:
                    os.system("pip3 install python-docx")
                    return True
                except:
                    return False

# Attempt installation
docx_installed = install_python_docx()

import streamlit as st
import json
from datetime import datetime
from openai import OpenAI
import traceback
from typing import List, Dict
import tempfile

# Import docx with proper error handling - no automatic installation
DOCX_AVAILABLE = False
try:
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    DOCX_AVAILABLE = True
except ImportError:
    st.warning("python-docx not available. Please run 'pip install python-docx' manually if you need DOCX functionality.")
except Exception as e:
    st.warning(f"Error importing docx: {e}. DOCX functionality disabled.")

if not DOCX_AVAILABLE:
    st.info("Note: DOCX functionality is not available. Text output will be shown instead.")


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

# ---------- DOCX helpers ----------
RATING_BONUS = {"Needs Work": 0, "Okay": 5, "Good": 10, "Great": 15}

def compute_overall(sections):
    total = 55
    for s in sections:
        total += RATING_BONUS.get(s.get("rating", ""), 0)
    return min(total, 100)

def _apply_body_font(run):
    run.font.size = Pt(12)

def _add_heading(p, text):
    run = p.add_run(text)
    run.bold = True
    _apply_body_font(run)

def _add_text(p, text):
    run = p.add_run(text)
    _apply_body_font(run)

def _add_red_text(p, text):
    run = p.add_run(text)
    _apply_body_font(run)
    run.font.color.rgb = RGBColor(0xFF, 0x00, 0x00)

def create_fix_my_call_docx(data: dict) -> tuple:
    if not DOCX_AVAILABLE:
        raise RuntimeError("python-docx is not available")
    
    advisor = data.get("advisor_name") or "Service Advisor"
    date_iso = data.get("date_iso") or datetime.now().strftime("%Y-%m-%d")
    sections = data.get("sections", [])
    next_steps = data.get("next_steps", [])
    transcript = data.get("transcript", "")

    overall = compute_overall(sections)

    doc = Document()

    # Title
    title_para = doc.add_paragraph()
    t = title_para.add_run(f"Fix My Call — {date_iso} — {advisor}")
    t.bold = True
    t.font.size = Pt(12)
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph("")

    # Sections
    for s in sections:
        name = s.get("name", "Section")
        rating = s.get("rating", "Needs Work")
        notes = s.get("notes", "Notes")
        opts = s.get("options") or ["Needs Work", "Okay", "Good", "Great"]

        p = doc.add_paragraph()
        _add_heading(p, name)

        p2 = doc.add_paragraph()
        for idx, opt in enumerate(opts):
            if opt == rating:
                _add_red_text(p2, opt)
            else:
                _add_text(p2, opt)
            if idx < len(opts) - 1:
                _add_text(p2, "  |  ")

        p3 = doc.add_paragraph()
        _add_text(p3, notes)

        doc.add_paragraph("")

    # Next Steps
    p = doc.add_paragraph()
    _add_heading(p, "Next Steps")
    if next_steps:
        for step in next_steps:
            li = doc.add_paragraph()
            _add_text(li, f"• {step}")
    else:
        li = doc.add_paragraph()
        _add_text(li, "• (none)")

    doc.add_paragraph("")

    # Overall Score
    p = doc.add_paragraph()
    _add_heading(p, "Overall Score: ")
    _add_red_text(p, f"{overall}%")

    doc.add_paragraph("")

    # Footer
    p = doc.add_paragraph()
    _add_heading(p, "Your Reviewing Trainer: ")
    _add_text(p, "Mike Tatich")

    safe_name = advisor.replace("/", "-").replace("\\", "-")
    filename = f"Fix My Call - {safe_name} - {date_iso}.docx"
    temp_path = os.path.join(tempfile.gettempdir(), filename)
    doc.save(temp_path)
    return temp_path, filename

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

        if files and DOCX_AVAILABLE:
            try:
                data = json.loads(reply)
                if not data.get("date_iso"):
                    data["date_iso"] = datetime.now().strftime("%Y-%m-%d")
                docx_path, docx_filename = create_fix_my_call_docx(data)
                with open(docx_path, "rb") as f:
                    st.download_button(
                        label=f"Download {docx_filename}",
                        data=f.read(),
                        file_name=docx_filename,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                st.success(f"Ready to download: {docx_filename}")
            except Exception as je:
                st.error(f"[DOCX generation issue: {je}]")
                st.markdown(f"**Assistant:** {reply}")
        else:
            if files and not DOCX_AVAILABLE:
                st.warning("DOCX functionality not available. Showing text output instead.")
            st.markdown(f"**Assistant:** {reply}")

        st.session_state.conversation.append({"role": "assistant", "content": reply})

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
