# extractor.py
# Legal Document Automation Tool
# Built by Muna Aden — 2026

import click
import os
import re
import anthropic
from rich.console import Console
from rich.table import Table
import PyPDF2
from docx import Document

console = Console()

def read_pdf(filepath):
    """Extract text from a PDF file."""
    text = ""
    with open(filepath, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() or ""
    return text

def read_docx(filepath):
    """Extract text from a Word document."""
    doc = Document(filepath)
    return "\n".join([para.text for para in doc.paragraphs])

def read_document(filepath):
    """Detect file type and read accordingly."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.pdf':
        return read_pdf(filepath)
    elif ext == '.docx':
        return read_docx(filepath)
    else:
        console.print("[red]Unsupported file type. Use PDF or DOCX.[/red]")
        return None

def extract_dates(text):
    """Find all dates mentioned in the document."""
    patterns = [
        r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',
        r'\b\d{1,2}-\d{1,2}-\d{2,4}\b',
        r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',
        r'\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b',
    ]
    dates = []
    for pattern in patterns:
        found = re.findall(pattern, text, re.IGNORECASE)
        dates.extend(found)
    return list(set(dates))

def extract_parties(text):
    """Find parties involved."""
    parties = []
    vs_pattern = re.findall(r'([A-Z][a-zA-Z\s]+)\s+v\.?\s+([A-Z][a-zA-Z\s]+)', text)
    for match in vs_pattern[:5]:
        parties.append(f"{match[0].strip()} v. {match[1].strip()}")
    plaintiff = re.findall(r'(?:Plaintiff|PLAINTIFF)[:\s]+([A-Z][a-zA-Z\s,]+)', text)
    defendant = re.findall(r'(?:Defendant|DEFENDANT)[:\s]+([A-Z][a-zA-Z\s,]+)', text)
    if plaintiff:
        parties.append(f"Plaintiff: {plaintiff[0].strip()}")
    if defendant:
        parties.append(f"Defendant: {defendant[0].strip()}")
    return list(set(parties))[:8]

def extract_keywords(text):
    """Find important legal keywords present in the document."""
    legal_terms = [
        "contract", "agreement", "breach", "damages", "liability",
        "negligence", "plaintiff", "defendant", "verdict", "judgment",
        "settlement", "evidence", "testimony", "witness", "appeal",
        "constitutional", "amendment", "rights", "privacy", "data",
        "confidential", "disclosure", "penalty", "injunction", "statute"
    ]
    found = []
    text_lower = text.lower()
    for term in legal_terms:
        if term in text_lower:
            found.append(term)
    return found

def extract_dollar_amounts(text):
    """Find any monetary amounts mentioned."""
    pattern = r'\$[\d,]+(?:\.\d{2})?(?:\s*(?:million|billion|thousand))?'
    amounts = re.findall(pattern, text, re.IGNORECASE)
    return list(set(amounts))[:10]

def ai_analyze(text):
    """Use Claude to intelligently analyze the legal document."""
    client = anthropic.Anthropic()

    trimmed = text[:8000]

    prompt = f"""You are a legal document analyst. Analyze this legal document and provide:

1. SUMMARY — 2-3 sentences explaining what this document is about in plain English
2. KEY PARTIES — who is involved and what their role is
3. MAIN ISSUES — the core legal questions or disputes
4. IMPORTANT OBLIGATIONS — what each party is required to do
5. RISK FLAGS — any deadlines, penalties, liabilities, or concerning clauses
6. DOCUMENT TYPE — what kind of legal document this is (contract, case, motion, etc.)

Keep each section concise and clear. Write for someone who is not a lawyer.

DOCUMENT:
{trimmed}"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return message.content[0].text

def save_summary(file, dates, parties, keywords, amounts, ai_summary):
    """Save extracted info to a text file."""
    output_name = os.path.splitext(file)[0] + "_summary.txt"
    with open(output_name, 'w') as f:
        f.write("LEGAL DOCUMENT SUMMARY\n")
        f.write("=" * 40 + "\n\n")
        f.write("AI ANALYSIS\n")
        f.write(ai_summary + "\n\n")
        f.write("=" * 40 + "\n\n")
        f.write("DATES FOUND\n")
        for d in dates:
            f.write(f"  • {d}\n")
        f.write("\nPARTIES INVOLVED\n")
        for p in parties:
            f.write(f"  • {p}\n")
        f.write("\nMONETARY AMOUNTS\n")
        for a in amounts:
            f.write(f"  • {a}\n")
        f.write("\nLEGAL KEYWORDS DETECTED\n")
        for k in keywords:
            f.write(f"  • {k}\n")
    return output_name

@click.command()
@click.option('--file', '-f', required=True, help='Path to legal document (PDF or DOCX)')
def analyze(file):
    """Legal Document Analyzer — extracts key info from contracts and legal docs."""
    console.print(f"\n[bold magenta]===== Legal Doc Analyzer =====[/bold magenta]")
    console.print(f"File: [cyan]{file}[/cyan]\n")

    text = read_document(file)

    if not text:
        return

    console.print(f"[green]Document read successfully[/green] — {len(text):,} characters\n")

    dates = extract_dates(text)
    parties = extract_parties(text)
    keywords = extract_keywords(text)
    amounts = extract_dollar_amounts(text)

    console.print("[bold yellow]DATES FOUND[/bold yellow]")
    if dates:
        for d in dates:
            console.print(f"  • {d}")
    else:
        console.print("  [dim]None found[/dim]")

    console.print(f"\n[bold yellow]PARTIES INVOLVED[/bold yellow]")
    if parties:
        for p in parties:
            console.print(f"  • {p}")
    else:
        console.print("  [dim]None found[/dim]")

    console.print(f"\n[bold yellow]MONETARY AMOUNTS[/bold yellow]")
    if amounts:
        for a in amounts:
            console.print(f"  • {a}")
    else:
        console.print("  [dim]None found[/dim]")

    console.print(f"\n[bold yellow]LEGAL KEYWORDS DETECTED[/bold yellow]")
    table = Table(show_header=False, box=None, padding=(0,2))
    chunks = [keywords[i:i+4] for i in range(0, len(keywords), 4)]
    for chunk in chunks:
        table.add_row(*[f"[green]✓[/green] {k}" for k in chunk])
    console.print(table)

    console.print(f"\n[bold yellow]AI ANALYSIS[/bold yellow]")
    console.print("[dim]Reading document with AI...[/dim]\n")
    ai_summary = ai_analyze(text)
    console.print(ai_summary)

    output = save_summary(file, dates, parties, keywords, amounts, ai_summary)
    console.print(f"\n[green]Summary saved to:[/green] [cyan]{output}[/cyan]")

    console.print(f"\n[bold magenta]===== Analysis Complete =====[/bold magenta]\n")

if __name__ == '__main__':
    analyze()

    










    