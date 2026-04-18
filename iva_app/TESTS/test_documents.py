from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

COMPANIES = {
    "mensch_und_maschine": {
        "folder": "documents/mensch_und_maschine",
    },
    "tyson_foods": {
        "folder": "documents/tyson_foods",
    },
}

def load_documents() -> dict:
    docs = {}
    for company_key, company_info in COMPANIES.items():
        folder = Path(company_info["folder"]).resolve()
        docs[company_key] = []
        if folder.exists():
            txt_files = list(folder.glob("*.txt")) + list(folder.glob("*.md")) + list(folder.glob("*.csv")) + list(folder.glob("*.json"))
            print(f"Found {len(txt_files)} files in {company_key}")
            for file_path in sorted(txt_files):
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    if content.strip() and len(content.strip()) > 50 and not content.startswith("[No documents"):
                        docs[company_key].append({"filename": file_path.name, "content": content[:8000]})
                        print(f"  Added {file_path.name}")
                except Exception as e:
                    print(f"  Error: {e}")
        if not docs[company_key]:
            docs[company_key] = [{"filename": "placeholder.txt", "content": "[No documents]"}]
            print(f"  WARNING: Using placeholder for {company_key}")
    return docs

docs = load_documents()
for key in docs:
    real_docs = [d for d in docs[key] if not d['filename'].startswith('placeholder')]
    print(f"\n{key}: {len(real_docs)} real documents")
    for d in real_docs[:3]:
        print(f"  - {d['filename']}: {len(d['content'])} bytes")
