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

SYSTEM_PROMPT = """You are a precise research assistant for Merantix Capital analyzing two companies: Mensch und Maschine and Tyson Foods.

CRITICAL RULES - STRICTLY FOLLOW WITHOUT EXCEPTION:
1. ONLY use information explicitly present in the DOCUMENT CONTEXT provided below
2. NEVER use general knowledge, internet knowledge, or external information
3. NEVER mention "general knowledge", "typically", "usually", or similar phrases
4. If information is not in documents, respond with: "I don't have that information in the available documents."

DOCUMENT CONTEXT RULES:
- The document excerpts are provided in the DOCUMENT CONTEXT section
- Each document is labeled with [filename]
- Only answer questions using these exact documents
- If the folder shows "(No documents available)", it means no documents were loaded for that company

COMPANY CONTEXT:
- Track which company user is asking about
- For ambiguous follow-ups, refer to the previously discussed company
- Ask for clarification if unclear

FORBIDDEN CONTENT:
- Funding rounds, employee salaries, contract details, client names
- General statements like "Based on typical companies..."
- Speculation or assumptions

ALLOWED CONTENT (if in documents):
- Revenue, profitability, business segments, products, market position
- Always cite which document the information came from

TONE: Direct, factual, honest about available information."""

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
                    # Only add if content is substantial (not just placeholders or READMEs)
                    if (
                        content.strip()
                        and len(content.strip()) > 50
                        and not content.startswith("[No documents")
                        and file_path.name != "README_ADD_DOCS_HERE.md"
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

        # NO PLACEHOLDERS - leave empty if no docs found
        if docs[company_key]:
            debug_log(f"Loaded {len(docs[company_key])} documents for {company_key}")
        else:
            debug_log(f"No documents found for {company_key}")
    return docs


# Convert PDFs to text on startup (silently)
convert_all_pdfs_to_txt()

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


# ── Core Chat Logic ────────────────────────────────────────────────────────────


def chat(
    user_message: str, history: list, last_company: str | None
) -> tuple[str, list, str | None]:
    """Process a user message and return assistant response."""

    if not user_message.strip():
        return "", history, last_company

    # RELOAD documents for this request (ensures fresh data)
    try:
        docs = load_documents()
    except Exception as e:
        debug_log(f"❌ Error loading documents: {type(e).__name__}: {str(e)}")
        error_msg = f"❌ Error loading documents. Check debug.log for details."
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": error_msg})
        return "", history, last_company

    # DEBUG: Log what's in documents when chat is called
    debug_log(f"chat() called - reloading documents")
    debug_log(f"Document keys: {list(docs.keys())}")
    for key in docs:
        num_docs = len(docs[key])
        debug_log(f"  {key}: {num_docs} documents")

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
    debug_log(
        f"DETECT COMPANY: message='{user_message[:50]}...' detected={current_company}"
    )

    # Build document context from freshly loaded docs
    if current_company is None:
        # No specific company mentioned - include documents from both if available
        parts = []
        docs_found_count = 0
        for key_name, info in COMPANIES.items():
            company_docs = docs.get(key_name, [])
            if company_docs:
                docs_found_count += len(company_docs)
                doc_text = "\n\n".join(
                    f"[{d['filename']}]\n{d['content']}" for d in company_docs
                )
                parts.append(f"=== {info['display_name']} ===\n{doc_text}")

        if not parts:
            # NO documents found at all - error
            error_msg = "❌ No documents available for either company. Please check that documents are in the documents/ folder."
            debug_log(f"ERROR: {error_msg}")
            history.append({"role": "user", "content": user_message})
            history.append({"role": "assistant", "content": error_msg})
            return "", history, current_company

        doc_context = "\n\n".join(parts)
        debug_log(f"multi-company mode: {docs_found_count} total documents found")
    else:
        info = COMPANIES[current_company]
        company_docs = docs.get(current_company, [])
        doc_count = len(company_docs)
        debug_log(
            f"build_context: {current_company} has {doc_count} documents, total context size: {sum(len(d['content']) for d in company_docs)} bytes"
        )
        if not company_docs:
            # CRITICAL: Documents truly didn't load - return immediate error
            error_msg = f"❌ No documents found for {info['display_name']}. The document folder may be empty or inaccessible. Expected folder: {info['folder']}"
            debug_log(f"ERROR: {error_msg}")
            history.append({"role": "user", "content": user_message})
            history.append({"role": "assistant", "content": error_msg})
            return "", history, current_company

        # Load documents successfully
        doc_text = "\n\n".join(
            f"[{d['filename']}]\n{d['content']}" for d in company_docs
        )
        doc_context = f"=== {info['display_name']} ===\n{doc_text}"

    # DEBUG: Log the actual context being sent
    context_length = len(doc_context)
    debug_log(f"doc_context length: {context_length} bytes")
    if context_length < 100:
        debug_log(f"WARNING: Context very small! Docs may not be loading.")

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
    debug_log(
        f"Sending to Claude, total message context: {sum(len(m['content']) for m in messages)} bytes"
    )

    try:
        debug_log(f"Creating Anthropic client...")
        client = anthropic.Anthropic(api_key=key)
        debug_log(f"Sending request to {MODEL}...")
        response = client.messages.create(
            model=MODEL, max_tokens=1024, system=SYSTEM_PROMPT, messages=messages
        )
        reply = response.content[0].text
        debug_log(f"✓ API response received: {len(reply)} characters")
    except anthropic.AuthenticationError as e:
        debug_log(f"❌ AUTH ERROR: {str(e)}")
        reply = "❌ Invalid API key. Please check ANTHROPIC_API_KEY in your .env file."
    except anthropic.RateLimitError as e:
        debug_log(f"⏱️  RATE LIMIT: {str(e)}")
        reply = "⏱️  Rate limit reached. Please wait a moment and try again."
    except anthropic.APIConnectionError as e:
        debug_log(f"🌐 CONNECTION ERROR: {str(e)}")
        reply = "🌐 Cannot connect to Anthropic API. Check your internet connection."
    except anthropic.APITimeoutError as e:
        debug_log(f"⏳ TIMEOUT: {str(e)}")
        reply = "⏳ Request to Claude timed out. Please try again."
    except Exception as e:
        debug_log(f"❌ UNEXPECTED ERROR: {type(e).__name__}: {str(e)}")
        reply = f"❌ Error: {type(e).__name__}. Check debug.log for details."

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
            """Handle text submission safely."""
            try:
                if not user_msg or not user_msg.strip():
                    return "", history, lc
                return chat(user_msg, history, lc)
            except Exception as e:
                debug_log(f"❌ submit_text error: {type(e).__name__}: {str(e)}")
                error_reply = f"❌ Error processing message: {type(e).__name__}"
                history.append({"role": "user", "content": user_msg})
                history.append({"role": "assistant", "content": error_reply})
                return "", history, lc

        def process_voice(audio_path, current_input, history, lc):
            """Process voice input and add to chat."""
            try:
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
            except Exception as e:
                debug_log(f"❌ process_voice error: {type(e).__name__}: {str(e)}")
                error_msg = f"🎤 Error processing voice: {type(e).__name__}"
                return error_msg, history, lc

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
