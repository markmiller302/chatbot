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

### 2. Run the Application

```bash
streamlit run streamlit_app.py
```

## Usage

1. **Upload File**: Upload an MP3 voicemail file
2. **Generate Report**: Click "🎯 Generate Report"
3. **Wait for Processing**: The app will transcribe and analyze the audio
4. **Download**: Click the download button for the generated Word document

## Security Notes

- API key is stored securely in Streamlit Cloud secrets
- No API keys are stored in source code or configuration files
- The app automatically loads the API key from the cloud deployment

## Deployment

This app is configured to run on Streamlit Cloud with the OpenAI API key stored as a secret in the deployment settings.

**Note**: The API key is already configured in the Streamlit Cloud deployment. No additional setup required.