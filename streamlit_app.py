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

# ---------- PDF helpers ----------
RATING_BONUS = {"Needs Work": 0, "Okay": 5, "Good": 10, "Great": 15}

def compute_overall(sections):
    total = 55
    for s in sections:
        total += RATING_BONUS.get(s.get("rating", ""), 0)
    return min(total, 100)

def create_fix_my_call_pdf(data: dict) -> tuple:
    if not PDF_AVAILABLE:
        raise RuntimeError("reportlab is not available")
    
    advisor = data.get("advisor_name") or "Service Advisor"
    date_iso = data.get("date_iso") or datetime.now().strftime("%Y-%m-%d")
    sections = data.get("sections", [])
    next_steps = data.get("next_steps", [])
    transcript = data.get("transcript", "")

    overall = compute_overall(sections)

    safe_name = advisor.replace("/", "-").replace("\\", "-")
    filename = f"Fix My Call - {safe_name} - {date_iso}.pdf"
    temp_path = os.path.join(tempfile.gettempdir(), filename)

    doc = SimpleDocTemplate(temp_path, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=12,
        alignment=1,  # Center
        spaceAfter=20
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        bold=True,
        spaceAfter=10
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=10
    )
    
    red_style = ParagraphStyle(
        'RedText',
        parent=styles['Normal'],
        fontSize=12,
        textColor=red
    )

    story = []

    # Title
    title = Paragraph(f"Fix My Call — {date_iso} — {advisor}", title_style)
    story.append(title)
    story.append(Spacer(1, 20))

    # Sections
    for s in sections:
        name = s.get("name", "Section")
        rating = s.get("rating", "Needs Work")
        notes = s.get("notes", "Notes")
        opts = s.get("options") or ["Needs Work", "Okay", "Good", "Great"]

        # Section heading
        story.append(Paragraph(name, heading_style))
        
        # Rating options with selected one in red
        rating_text = ""
        for idx, opt in enumerate(opts):
            if opt == rating:
                rating_text += f'<font color="red">{opt}</font>'
            else:
                rating_text += opt
            if idx < len(opts) - 1:
                rating_text += "  |  "
        
        story.append(Paragraph(rating_text, normal_style))
        story.append(Paragraph(notes, normal_style))
        story.append(Spacer(1, 15))

    # Next Steps
    story.append(Paragraph("Next Steps", heading_style))
    if next_steps:
        for step in next_steps:
            story.append(Paragraph(f"• {step}", normal_style))
    else:
        story.append(Paragraph("• (none)", normal_style))
    
    story.append(Spacer(1, 15))

    # Overall Score
    score_text = f'Overall Score: <font color="red">{overall}%</font>'
    story.append(Paragraph(score_text, heading_style))
    story.append(Spacer(1, 15))

    # Footer
    footer_text = '<b>Your Reviewing Trainer:</b> Mike Tatich'
    story.append(Paragraph(footer_text, normal_style))

    doc.build(story)
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

        if files and PDF_AVAILABLE:
            try:
                data = json.loads(reply)
                if not data.get("date_iso"):
                    data["date_iso"] = datetime.now().strftime("%Y-%m-%d")
                pdf_path, pdf_filename = create_fix_my_call_pdf(data)
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        label=f"Download {pdf_filename}",
                        data=f.read(),
                        file_name=pdf_filename,
                        mime="application/pdf"
                    )
                st.success(f"Ready to download: {pdf_filename}")
            except Exception as je:
                st.error(f"[PDF generation issue: {je}]")
                st.markdown(f"**Assistant:** {reply}")
        else:
            if files and not PDF_AVAILABLE:
                st.warning("PDF functionality not available. Showing text output instead.")
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
