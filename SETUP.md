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

### 2. Configure OpenAI API Key

**Important: Never commit your API key to version control!**

Choose one of these methods:

#### Option A: Environment Variable (Recommended)
```bash
export OPENAI_API_KEY="your-api-key-here"
streamlit run streamlit_app.py
```

#### Option B: .env File (Local Development)
1. Create a `.env` file in the project root:
```
OPENAI_API_KEY=your-api-key-here
```
2. The `.env` file is already in `.gitignore` and won't be committed

#### Option C: Streamlit Secrets (Streamlit Cloud)
1. Create `.streamlit/secrets.toml`:
```toml
OPENAI_API_KEY = "your-api-key-here"
```
2. This file is already in `.gitignore`

### 3. Run the Application

```bash
streamlit run streamlit_app.py
```

## Usage

1. Upload an MP3 voicemail file
2. Click "🎯 Generate Report"
3. Wait for processing (transcription + analysis)
4. Download the generated Word document

## Deployment

For production deployment:
- Use environment variables or cloud secret management
- Never hardcode API keys in source code
- Ensure `.env` and `secrets.toml` are in `.gitignore`

## Security Notes

- API keys are loaded securely from environment variables or secrets
- The application includes multiple fallback methods for API key loading
- Debug information shows only the first 10 characters of API keys
- All sensitive files are excluded from version control