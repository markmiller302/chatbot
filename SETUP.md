# Service Advisor Review Chatbot

A Streamlit application that analyzes service advisor voicemails and generates structured feedback reports.

## Features

- Upload MP3 voicemail files
- AI-powered transcription using OpenAI Whisper
- Automated analysis and scoring using GPT-4
- Generates downloadable Word documents with structured feedback

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Get OpenAI API Key

1. Go to https://platform.openai.com/account/api-keys
2. Create a new API key
3. Copy the key (starts with `sk-`)

### 3. Run the Application

```bash
streamlit run streamlit_app.py
```

## Usage

1. **Enter API Key**: Paste your OpenAI API key in the sidebar
2. **Upload File**: Upload an MP3 voicemail file
3. **Generate Report**: Click "🎯 Generate Report"
4. **Wait for Processing**: The app will transcribe and analyze the audio
5. **Download**: Click the download button for the generated Word document

## Security Notes

- API keys are entered directly into the app interface
- Keys are stored only in browser session (not saved to disk)
- No API keys are stored in the source code
- Each user must provide their own API key

## Deployment

This app can be deployed to any Streamlit-compatible platform:
- Streamlit Cloud
- Heroku
- AWS/GCP/Azure
- Local deployment

No environment variables or secrets configuration required.