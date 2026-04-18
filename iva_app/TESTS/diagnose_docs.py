#!/usr/bin/env python
"""Diagnose why documents aren't loading"""
from pathlib import Path

COMPANIES = {
    "mensch_und_maschine": {
        "display_name": "Mensch und Maschine",
        "folder": "documents/mensch_und_maschine",
    },
    "tyson_foods": {
        "display_name": "Tyson Foods",
        "folder": "documents/tyson_foods",
    },
}

print("=" * 70)
print("DOCUMENT LOADING DIAGNOSTIC")
print("=" * 70)

for company_key, company_info in COMPANIES.items():
    folder = Path(company_info["folder"]).resolve()
    print(f"\n{company_key}:")
    print(f"  Folder: {folder}")
    print(f"  Exists: {folder.exists()}")

    if folder.exists():
        txt_files = (
            list(folder.glob("*.txt"))
            + list(folder.glob("*.md"))
            + list(folder.glob("*.csv"))
            + list(folder.glob("*.json"))
        )
        print(f"  Total files found: {len(txt_files)}")

        accepted = 0
        rejected = 0

        for file_path in sorted(txt_files):
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                content_len = len(content.strip())

                # Check each filter condition
                passes_content_check = bool(content.strip())
                passes_length_check = content_len > 50
                passes_placeholder_check = not content.startswith("[No documents")
                passes_readme_check = file_path.name != "README_ADD_DOCS_HERE.md"

                will_accept = (
                    passes_content_check
                    and passes_length_check
                    and passes_placeholder_check
                    and passes_readme_check
                )

                status = "✓ ACCEPT" if will_accept else "✗ REJECT"
                reason = []
                if not passes_content_check:
                    reason.append("empty")
                if not passes_length_check:
                    reason.append(f"too short ({content_len} chars)")
                if not passes_placeholder_check:
                    reason.append("is placeholder")
                if not passes_readme_check:
                    reason.append("is README")

                reason_str = f" ({', '.join(reason)})" if reason else ""
                print(f"    {status}: {file_path.name}{reason_str}")

                if will_accept:
                    accepted += 1
                else:
                    rejected += 1

            except Exception as e:
                print(f"    ✗ ERROR: {file_path.name} - {e}")
                rejected += 1

        print(f"  Summary: {accepted} accepted, {rejected} rejected")
    else:
        print(f"  ERROR: Folder does not exist!")

print("\n" + "=" * 70)
