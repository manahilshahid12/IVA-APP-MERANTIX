# Interactive Voice Application — Company Analysis

### Merantix Capital Technical Assignment | Manahil Shahid

A conversational AI assistant that lets users ask natural language questions about **Mensch und Maschine** and **Tyson Foods**, with voice input support, context tracking, and built-in financial/client data guardrails (for privacy).

---

## Quick Start (3 steps)

**1. Install dependencies**

```bash
pip install -r requirements.txt
```

**2. Set your API key**

```bash
cp .env.example .env
# Open .env and replace with your Anthropic API key
```

**3. Add your documents and run**

```bash
#  Documents have already been added but in case any other docs in future
#  Drop your .txt or .md document files into:
#   documents/mensch_und_maschine/
#   documents/tyson_foods/

python app.py
# Open http://localhost:7860 in your browser
```

That's it.

---

## Adding Your Documents

The app automatically loads all `.txt` and `.md` files from the two document folders:

```
documents/
├── mensch_und_maschine/    ← drop MuM files here
│   └── your_file.txt
└── tyson_foods/            ← drop Tyson files here
    └── your_file.txt
```

Supported formats: `.txt`, `.md`, `.csv`, `.json`

For PDFs, convert to text first:

```bash
pip install pymupdf
python -c "import fitz; doc=fitz.open('file.pdf'); open('out.txt','w').write(''.join(p.get_text() for p in doc))"
```

---

## Features

| Feature                | Implementation                                                  |
| ---------------------- | --------------------------------------------------------------- |
| Natural language Q&A   | Claude claude-opus-4-5 with document context injection          |
| Voice input            | Browser microphone via Gradio audio component                   |
| Context tracking       | Company detected per turn, persisted across follow-ups          |
| Financial guardrails   | System prompt restrictions on funding, salaries, contract sizes |
| Client name protection | System prompt instruction, never disclosed                      |
| Error handling         | Graceful responses when info not in documents                   |
| Conversation memory    | Last 10 turns passed to model each request                      |

---

## Architectural Overview

### Why this stack?

**Claude (Anthropic)** as the LLM backbone — one of the best model for instruction-following and guardrail adherence. The system prompt approach gives precise control over what the model will and won't disclose.

**Gradio** for the UI — gives a production-ready chat interface with built-in microphone support in a single Python file. No frontend code needed, deploys instantly to Hugging Face Spaces if required.

**Document injection (RAG-lite)** rather than a vector database since given the document set is small (two companies, limited files), injecting the full document context into each prompt is simpler, more reliable, and easier to debug than setting up a vector store. For a larger document set (50+ files), I would switch to a proper RAG pipeline using LlamaIndex or LangChain with a ChromaDB or Pinecone backend.

### How it works

```
User message
     │
     ▼
Company detection
(keyword match → falls back to last company in conversation)
     │
     ▼
Document context builder
(loads relevant company docs from folder, injects into prompt)
     │
     ▼
Claude API call
(system prompt with guardrails + conversation history + augmented user message)
     │
     ▼
Response → displayed in chat UI
```

### Guardrail implementation

Financial and client data protection is enforced at the system prompt level with explicit instructions. Claude is instructed to:

- Never disclose funding rounds, employee salaries, or precise contract sizes
- Only share: yearly revenue, quarterly revenue, next-quarter projections
- Never name any clients of either company
- Redirect gracefully when these topics arise or give a satisfactory response

### Context tracking

Company context is maintained in Gradio state (`last_company`). Each user message is checked for company name mentions (including common aliases like "MuM", "Tyson"). If no company is mentioned, the last detected company is assumed — matching the expected behavior in the assignment examples.

---

## Example Interactions

| User says                           | App does                                             |
| ----------------------------------- | ---------------------------------------------------- |
| "What does Mensch und Maschine do?" | Answers from MuM documents                           |
| "What about their Q2 revenue?"      | Knows they mean MuM, answers from MuM docs           |
| "Tell me about the other company"   | Switches to Tyson Foods                              |
| "Who are their clients?"            | Declines, explains it can't share client names       |
| "What was their funding round?"     | Declines, explains financial restriction             |
| "Who are the founders of both?"     | Asks for clarification if ambiguous                  |
| "What's their long-term strategy?"  | "I don't have that in the documents I've been given" |

---

## Deployment Options

### Local (default)

```bash
python app.py
# Runs at http://localhost:7860
```

---

## Project Structure

```
iva_app/
├── app.py                          # Main application (single file)
├── requirements.txt                # Python dependencies
├── .env                            # API key template
├── README.md                       # This file
└── documents/
    ├── mensch_und_maschine/        # Add MuM documents here
    └── tyson_foods/                # Add Tyson documents here
```

---

## Trade-offs & What I'd Add With More Time

| What                    | Why not now                | How I'd add it                       |
| ----------------------- | -------------------------- | ------------------------------------ |
| Full RAG with vector DB | Overkill for small doc set | LlamaIndex + ChromaDB if docs grow   |
| ElevenLabs voice output | Adds API dependency        | ~20 lines with elevenlabs Python SDK |
| Whisper transcription   | Needs separate API call    | OpenAI Whisper API on audio upload   |
| Streaming responses     | Minor UX improvement       | `stream=True` in Anthropic client    |
| Persistent chat history | Not required by brief      | SQLite + session IDs                 |
