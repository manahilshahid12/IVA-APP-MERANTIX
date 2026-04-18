"""
Interactive Voice Application (IVA) for Company Analysis
Merantix Capital — Technical Assignment
Author: Manahil Shahid
email: manahilshahid13@gmail.com

"""

import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
import anthropic
import fitz  # PyMuPDF for PDF to text conversion
import gradio as gr

# Load environment variables from .env file
load_dotenv()

# Setup debug logging to file
DEBUG_LOG = Path("debug.log")


def debug_log(msg):
    """Write debug info to debug.log"""
    import datetime

    timestamp = datetime.datetime.now().isoformat()
    try:
        existing = DEBUG_LOG.read_text(errors="ignore") if DEBUG_LOG.exists() else ""
        DEBUG_LOG.write_text(existing + f"\n[{timestamp}] {msg}")
    except Exception as e:
        # Fallback: at least print to console
        print(f"[{timestamp}] {msg}")


try:
    import speech_recognition as sr

    SPEECH_AVAILABLE = True
except ImportError:
    SPEECH_AVAILABLE = False

# ── Configuration ──────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-opus-4-5"

COMPANIES = {
    "mensch_und_maschine": {
        "display_name": "Mensch und Maschine",
        "aliases": ["mensch und maschine", "mum", "m&m", "mensch", "maschine"],
        "folder": "documents/mensch_und_maschine",
    },
    "tyson_foods": {
        "display_name": "Tyson Foods",
        "aliases": ["tyson foods", "tyson", "tyson food"],
        "folder": "documents/tyson_foods",
    },
}

SYSTEM_PROMPT = """You are a knowledgeable and conversational assistant for Merantix Capital, specializing in company analysis. You help users explore information about two companies: Mensch und Maschine (a German CAD/PDM software provider) and Tyson Foods (a US food manufacturer).

CONTEXT TRACKING:
- Always track which company the user is asking about.
- If a user asks a follow-up question without specifying a company (e.g. "What about their Q2 results?"), assume they mean the last company discussed.
- If it is genuinely unclear which company they mean, ask for clarification politely.

INFORMATION RULES — STRICTLY FOLLOW THESE:
1. Answer based primarily on the document excerpts provided. Prefer document information.
2. If information is NOT found in the documents, say: "The documents I have don't contain specific details about [topic], but based on general industry knowledge, [answer]."
3. NEVER DISCLOSE: funding rounds, employee salaries, precise contract sizes, detailed financial deal terms, or client names.
4. ALLOWED to discuss: yearly revenue, quarterly revenue, business segments, products, market position, strategic initiatives mentioned in documents.
5. If asked about restricted topics, politely decline: "I'm not able to share that level of detail from these documents."

TONE:
- Be conversational, warm, and concise.
- Give direct answers — don't pad with unnecessary caveats.
- If a question is ambiguous, ask one clear clarifying question.

RESPONSE FORMAT:
- Keep responses to 3-5 sentences for simple questions.
- Use bullet points only for lists of 3+ items.
- Always end with an invitation to ask more if the topic seems complex."""

# ── Document Loading ───────────────────────────────────────────────────────────


def convert_all_pdfs_to_txt():
    """Convert all PDF files in company folders to .txt files."""
    for company_key, company_info in COMPANIES.items():
        folder = Path(company_info["folder"]).resolve()  # Resolve to absolute path
        if folder.exists():
            for pdf_file in folder.glob("*.pdf"):
                txt_file = pdf_file.with_suffix(".txt")
                if not txt_file.exists():  # Only convert if .txt doesn't already exist
                    try:
                        doc = fitz.open(pdf_file)
                        text = "\n".join(page.get_text() for page in doc)
                        txt_file.write_text(text, encoding="utf-8")
                        doc.close()
                    except Exception as e:
                        print(f"Error converting {pdf_file}: {e}")


def load_documents() -> dict:
    """Load all text documents from company folders."""
    docs = {}
    for company_key, company_info in COMPANIES.items():
        folder = Path(company_info["folder"]).resolve()  # Resolve to absolute path
        docs[company_key] = []
        if folder.exists():
            txt_files = (
                list(folder.glob("*.txt"))
                + list(folder.glob("*.md"))
                + list(folder.glob("*.csv"))
                + list(folder.glob("*.json"))
            )
            debug_log(f"Found {len(txt_files)} files in {company_key}")
            for file_path in sorted(txt_files):
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    # Only add if content is substantial (not just placeholders)
                    if (
                        content.strip()
                        and len(content.strip()) > 50
                        and not content.startswith("[No documents")
                    ):
                        docs[company_key].append(
                            {
                                "filename": file_path.name,
                                "content": content[:8000],  # cap per file
                            }
                        )
                        debug_log(f"  Added {file_path.name} ({len(content)} bytes)")
                except Exception as e:
                    debug_log(f"  Error reading {file_path}: {e}")
        if not docs[company_key]:
            docs[company_key] = [
                {
                    "filename": "placeholder.txt",
                    "content": f"[No documents loaded yet for {company_info['display_name']}. Please add documents to {company_info['folder']}]",
                }
            ]
            debug_log(f"No documents found for {company_key}, using placeholder")
        else:
            debug_log(f"Loaded {len(docs[company_key])} documents for {company_key}")
    return docs


# Convert PDFs to text first
convert_all_pdfs_to_txt()

# Then load all documents
DOCUMENTS = load_documents()

# ── Context Detection ──────────────────────────────────────────────────────────


def detect_company(message: str, last_company: str | None) -> str | None:
    """Detect which company the user is asking about."""
    msg_lower = message.lower()
    for company_key, info in COMPANIES.items():
        for alias in info["aliases"]:
            if alias in msg_lower:
                return company_key
    # Fall back to last mentioned company
    return last_company


def build_document_context(company_key: str | None) -> str:
    """Build the document context string to inject into the prompt."""
    if company_key is None:
        # Include both companies
        parts = []
        for key, info in COMPANIES.items():
            docs = DOCUMENTS.get(key, [])
            doc_count = len(
                [d for d in docs if not d["filename"].startswith("placeholder")]
            )
            debug_log(f"build_context: {key} has {doc_count} real documents")
            doc_text = "\n\n".join(f"[{d['filename']}]\n{d['content']}" for d in docs)
            parts.append(f"=== {info['display_name']} ===\n{doc_text}")
        return "\n\n".join(parts)
    else:
        info = COMPANIES[company_key]
        docs = DOCUMENTS.get(company_key, [])
        doc_count = len(
            [d for d in docs if not d["filename"].startswith("placeholder")]
        )
        debug_log(
            f"build_context: {company_key} has {doc_count} real documents, total context size: {sum(len(d['content']) for d in docs)} bytes"
        )
        doc_text = "\n\n".join(f"[{d['filename']}]\n{d['content']}" for d in docs)
        return f"=== {info['display_name']} ===\n{doc_text}"


# ── Core Chat Logic ────────────────────────────────────────────────────────────


def chat(
    user_message: str, history: list, last_company: str | None
) -> tuple[str, list, str | None]:
    """Process a user message and return assistant response."""

    if not user_message.strip():
        return "", history, last_company

    # DEBUG: Log what's in DOCUMENTS when chat is called
    debug_log(f"chat() called with message: {user_message[:50]}")
    debug_log(f"DOCUMENTS keys: {list(DOCUMENTS.keys())}")
    for key in DOCUMENTS:
        num_docs = len(
            [d for d in DOCUMENTS[key] if not d["filename"].startswith("placeholder")]
        )
        debug_log(f"  {key}: {num_docs} real docs")

    key = ANTHROPIC_API_KEY
    if not key:
        reply = (
            "⚠️ API key not found! Please set ANTHROPIC_API_KEY environment variable."
        )
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": reply})
        return "", history, last_company

    # Detect company context
    current_company = detect_company(user_message, last_company)

    # Build document context
    doc_context = build_document_context(current_company)

    # Build messages for Claude
    messages = []

    # Add conversation history (last 10 turns to stay within context)
    for turn in history[-10:]:
        messages.append({"role": turn["role"], "content": turn["content"]})

    # Add current user message with injected document context
    company_name = (
        COMPANIES[current_company]["display_name"]
        if current_company
        else "both companies"
    )
    augmented_message = f"""DOCUMENT CONTEXT (use only this information to answer):
{doc_context}

---
Current company context: {company_name}
User question: {user_message}"""

    messages.append({"role": "user", "content": augmented_message})

    try:
        client = anthropic.Anthropic(api_key=key)
        response = client.messages.create(
            model=MODEL, max_tokens=1024, system=SYSTEM_PROMPT, messages=messages
        )
        reply = response.content[0].text
    except anthropic.AuthenticationError:
        reply = "Invalid API key. Please check and re-enter your Anthropic API key."
    except anthropic.RateLimitError:
        reply = "Rate limit reached. Please wait a moment and try again."
    except Exception as e:
        reply = f"Something went wrong: {str(e)}"

    # Update history with clean user message (not augmented)
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": reply})

    return "", history, current_company


# ── Gradio UI ──────────────────────────────────────────────────────────────────


def build_ui():
    with gr.Blocks(
        title="Company Analysis Assistant",
    ) as demo:

        # State
        last_company = gr.State(None)

        # Minimal Header
        gr.HTML(
            """
        <div class="header-bar">
            <div class="header-content">
                <span class="logo">⚡ Company Assistant</span>
            </div>
        </div>
        """
        )

        # Chat Area
        chatbot = gr.Chatbot(
            label="",
            height=520,
            show_label=False,
            avatar_images=(None, "https://www.anthropic.com/favicon.ico"),
            placeholder="How can I help you? Ask about Mensch und Maschine or Tyson Foods",
        )

        # Input Area - ChatGPT style integrated
        with gr.Row(elem_classes="chat-bottom"):
            with gr.Row(elem_classes="input-wrapper"):
                audio_input = gr.Audio(
                    sources=["microphone"],
                    type="filepath",
                    label="",
                    show_label=False,
                    elem_classes="voice-button",
                )
                msg_input = gr.Textbox(
                    placeholder="Ask anything...",
                    label="",
                    show_label=False,
                    container=False,
                    elem_classes="chat-input",
                )
                submit_btn = gr.Button("➤", variant="primary", elem_classes="send-btn")

            clear_btn = gr.Button(
                "New chat", variant="secondary", elem_classes="new-chat-btn"
            )

        # ── Voice transcription ────────────────────────────────────────────────
        def transcribe_audio_file(audio_path: str) -> str:
            """Transcribe audio file to text."""
            if not audio_path:
                return ""

            if not SPEECH_AVAILABLE:
                return "🎤 Voice feature requires 'speech_recognition' package. Install it with: pip install SpeechRecognition pydub"

            try:
                recognizer = sr.Recognizer()
                with sr.AudioFile(audio_path) as source:
                    audio_data = recognizer.record(source)
                    text = recognizer.recognize_google(audio_data)
                    return text
            except sr.UnknownValueError:
                return "🎤 Could not understand audio. Please try again."
            except sr.RequestError as e:
                return f"🎤 Speech recognition error: {str(e)}"
            except Exception as e:
                return f"🎤 Error processing audio: {str(e)}"

        # ── Event handlers ────────────────────────────────────────────────────
        def submit_text(user_msg, history, lc):
            return chat(user_msg, history, lc)

        def process_voice(audio_path, current_input, history, lc):
            """Process voice input and add to chat."""
            if not audio_path:
                return current_input, history, lc

            # Transcribe audio
            transcribed_text = transcribe_audio_file(audio_path)

            if transcribed_text.startswith("🎤"):  # Error message
                # Show error but allow retry
                return transcribed_text, history, lc
            else:
                # Add transcribed text to input and auto-submit
                new_input = transcribed_text
                response, history, lc = chat(new_input, history, lc)
                return new_input, history, lc

        submit_btn.click(
            fn=submit_text,
            inputs=[msg_input, chatbot, last_company],
            outputs=[msg_input, chatbot, last_company],
        )

        msg_input.submit(
            fn=submit_text,
            inputs=[msg_input, chatbot, last_company],
            outputs=[msg_input, chatbot, last_company],
        )

        audio_input.change(
            fn=process_voice,
            inputs=[audio_input, msg_input, chatbot, last_company],
            outputs=[msg_input, chatbot, last_company],
        )

        clear_btn.click(fn=lambda: ([], None), outputs=[chatbot, last_company])

    return demo


# ── Entry Point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Clean up any existing processes using port 7860
    import subprocess
    import time

    try:
        # Kill any process using port 7860 on Windows
        subprocess.run(
            'for /f "tokens=5" %a in (\'netstat -aon ^| find ":7860" ^| find "LISTENING"\') do taskkill /PID %a /F',
            shell=True,
            capture_output=True,
            timeout=2,
        )
        time.sleep(1)
    except Exception:
        pass

    demo = build_ui()
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        show_error=True,
        quiet=False,
        theme=gr.themes.Soft(primary_hue="amber"),
        css="""
* { box-sizing: border-box; }

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: #ffffff;
    margin: 0;
    padding: 0;
}

/* Header */
.header-bar {
    background: #000000;
    padding: 1rem 0;
    margin: -1rem -1rem 1.5rem -1rem;
    border-bottom: 3px solid #fbbf24;
}

.header-content {
    max-width: 900px;
    margin: 0 auto;
    padding: 0 1.5rem;
}

.logo {
    font-size: 1.1rem;
    font-weight: 700;
    color: #fbbf24;
    letter-spacing: 0.5px;
}

/* Chat Interface */
.gr-chatbot {
    background: #ffffff !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 12px !important;
    padding: 1.5rem !important;
    margin-bottom: 1.5rem !important;
}

.empty-chat {
    text-align: center;
    padding: 3rem 1.5rem;
}

.empty-title {
    font-size: 2rem;
    font-weight: 700;
    color: #000000;
    margin-bottom: 0.5rem;
}

.empty-subtitle {
    font-size: 1rem;
    color: #666666;
}

/* User and assistant messages */
.gr-chatbot .message.user .message-content {
    background: #fbbf24 !important;
    color: #000000 !important;
    border-radius: 12px;
    padding: 0.75rem 1rem;
}

.gr-chatbot .message.assistant .message-content {
    background: #f3f4f6 !important;
    color: #000000 !important;
    border-radius: 12px;
    padding: 0.75rem 1rem;
}

/* Input Container */
.chat-bottom {
    flex-direction: column;
    gap: 1rem;
    margin-bottom: 1rem;
}

.input-wrapper {
    background: #ffffff;
    border: 2px solid #e5e7eb;
    border-radius: 32px;
    padding: 0.5rem 0.75rem;
    gap: 0.5rem;
    align-items: center;
    transition: all 0.2s ease;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.input-wrapper:focus-within {
    border-color: #fbbf24;
    box-shadow: 0 4px 16px rgba(251, 191, 36, 0.2);
}

.voice-button {
    display: flex !important;
    align-items: center !important;
    gap: 0.5rem;
}

.voice-button button {
    background: transparent !important;
    border: none !important;
    color: #666666 !important;
    padding: 0.5rem !important;
    cursor: pointer !important;
    font-size: 1.2rem !important;
    min-width: auto !important;
    height: auto !important;
    transition: all 0.2s ease;
}

.voice-button button:hover {
    color: #fbbf24 !important;
}

.chat-input {
    flex: 1 !important;
}

.chat-input input {
    background: transparent !important;
    border: none !important;
    color: #000000 !important;
    padding: 0 !important;
    font-size: 1rem !important;
    font-family: inherit !important;
    outline: none !important;
}

.chat-input input:focus {
    box-shadow: none !important;
}

.chat-input input::placeholder {
    color: #999999 !important;
}

/* Send Button */
.send-btn {
    background: #fbbf24 !important;
    border: none !important;
    color: #000000 !important;
    font-weight: 700 !important;
    border-radius: 24px !important;
    padding: 0.625rem 1rem !important;
    font-size: 1rem !important;
    cursor: pointer !important;
    transition: all 0.2s ease;
    min-width: auto !important;
    height: auto !important;
    box-shadow: none;
}

.send-btn:hover {
    background: #eab308 !important;
    transform: scale(1.05);
}

.send-btn:active {
    transform: scale(0.98);
}

/* New Chat Button */
.new-chat-btn {
    background: transparent !important;
    border: 2px solid #e5e7eb !important;
    color: #666666 !important;
    border-radius: 8px !important;
    padding: 0.5rem 1rem !important;
    font-weight: 600 !important;
    transition: all 0.2s ease;
    font-size: 0.9rem !important;
}

.new-chat-btn:hover {
    border-color: #fbbf24 !important;
    color: #fbbf24 !important;
    background: transparent !important;
}

footer { display: none !important; }
        """,
    )
