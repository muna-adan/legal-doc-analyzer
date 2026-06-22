from flask import Flask, render_template, request, redirect, url_for, session, send_file
import os
import re
import anthropic
import PyPDF2
from docx import Document
import markdown
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

load_dotenv()

def read_pdf(filepath):
    text = ""
    with open(filepath, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() or ""
    return text

def read_docx(filepath):
    doc = Document(filepath)
    return "\n".join([para.text for para in doc.paragraphs])

def read_document(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.pdf':
        return read_pdf(filepath)
    elif ext == '.docx':
        return read_docx(filepath)
    return None

def extract_dates(text):
    patterns = [
        r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',
        r'\b\d{1,2}-\d{1,2}-\d{2,4}\b',
        r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',
    ]
    dates = []
    for pattern in patterns:
        found = re.findall(pattern, text, re.IGNORECASE)
        dates.extend(found)
    return list(set(dates))

def extract_parties(text):
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
    pattern = r'\$[\d,]+(?:\.\d{2})?(?:\s*(?:million|billion|thousand))?'
    amounts = re.findall(pattern, text, re.IGNORECASE)
    return list(set(amounts))[:10]

def ai_analyze(text):
    client = anthropic.Anthropic()
    trimmed = text[:8000]
    prompt = f"""You are a legal document analyst. Analyze this legal document and provide:

1. SUMMARY — 2-3 sentences explaining what this document is about in plain English
2. KEY PARTIES — who is involved and what their role is
3. MAIN ISSUES — the core legal questions or disputes
4. IMPORTANT OBLIGATIONS — what each party is required to do
5. RISK FLAGS — any deadlines, penalties, liabilities, or concerning clauses
6. DOCUMENT TYPE — what kind of legal document this is

Keep each section concise. Write for someone who is not a lawyer.

DOCUMENT:
{trimmed}"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    return markdown.markdown(message.content[0].text)

def generate_pdf_report(filename, dates, parties, keywords, amounts, ai_summary):
    output_path = os.path.join('uploads', f"{filename}_report.pdf")
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=50, leftMargin=50,
        topMargin=50, bottomMargin=50
    )

    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from reportlab.platypus import HRFlowable

    NAVY = colors.HexColor('#1c2b4a')
    GOLD = colors.HexColor('#c9a84c')
    MUTED = colors.HexColor('#6b7280')

    title_style = ParagraphStyle('Title',
        fontSize=22, textColor=NAVY, fontName='Times-Bold',
        spaceAfter=4, alignment=TA_LEFT
    )
    subtitle_style = ParagraphStyle('Subtitle',
        fontSize=10, textColor=MUTED, fontName='Times-Roman',
        spaceAfter=20
    )
    section_style = ParagraphStyle('Section',
        fontSize=10, textColor=GOLD, fontName='Helvetica-Bold',
        spaceBefore=18, spaceAfter=6,
        textTransform='uppercase', letterSpacing=1.5
    )
    body_style = ParagraphStyle('Body',
        fontSize=10, textColor=NAVY, fontName='Times-Roman',
        spaceAfter=5, leading=16
    )
    bullet_style = ParagraphStyle('Bullet',
        fontSize=10, textColor=NAVY, fontName='Times-Roman',
        spaceAfter=4, leftIndent=12, leading=15
    )
    keyword_style = ParagraphStyle('Keyword',
        fontSize=9, textColor=GOLD, fontName='Helvetica-Bold',
        spaceAfter=4
    )

    story = []

    story.append(Paragraph("Legal Document Analysis Report", title_style))
    story.append(Paragraph(f"File: {filename}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=GOLD, spaceAfter=16))

    story.append(Paragraph("AI Analysis", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GOLD, spaceAfter=10))
    clean_summary = re.sub(r'<[^>]+>', '', ai_summary)
    clean_summary = clean_summary.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    for line in clean_summary.split('\n'):
        line = line.strip()
        if line:
            story.append(Paragraph(line, body_style))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Dates Found", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GOLD, spaceAfter=10))
    if dates:
        for d in dates:
            story.append(Paragraph(f"• {d}", bullet_style))
    else:
        story.append(Paragraph("None found.", body_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Parties Involved", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GOLD, spaceAfter=10))
    if parties:
        for p in parties:
            story.append(Paragraph(f"• {p}", bullet_style))
    else:
        story.append(Paragraph("None found.", body_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Monetary Amounts", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GOLD, spaceAfter=10))
    if amounts:
        for a in amounts:
            story.append(Paragraph(f"• {a}", bullet_style))
    else:
        story.append(Paragraph("None found.", body_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Legal Keywords Detected", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GOLD, spaceAfter=10))
    if keywords:
        story.append(Paragraph("  ·  ".join(keywords), keyword_style))
    else:
        story.append(Paragraph("None found.", body_style))

    story.append(Spacer(1, 24))
    story.append(HRFlowable(width="100%", thickness=1, color=NAVY, spaceAfter=6))
    story.append(Paragraph("Generated by Legal Doc Analyzer — Built by Muna Aden", ParagraphStyle(
        'Footer', fontSize=8, textColor=MUTED, fontName='Times-Roman', alignment=TA_CENTER
    )))

    doc.build(story)
    return output_path

app = Flask(__name__)
app.secret_key = 'legally_AI3'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs('uploads', exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'file' not in request.files:
        return redirect(url_for('index'))

    file = request.files['file']

    if file.filename == '':
        return redirect(url_for('index'))

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    try:
        text = read_document(filepath)
    except Exception as e:
        return render_template('error.html', message=str(e))

    if not text:
        return render_template('error.html', message="Could not extract text from this file. Make sure it is a valid PDF or DOCX.")

    dates = extract_dates(text)
    parties = extract_parties(text)
    keywords = extract_keywords(text)
    amounts = extract_dollar_amounts(text)
    ai_summary = ai_analyze(text)

    session['dates'] = dates
    session['parties'] = parties
    session['keywords'] = keywords
    session['amounts'] = amounts
    session['ai_summary'] = ai_summary
    session['filename'] = file.filename

    return render_template('results.html',
        filename=file.filename,
        dates=dates,
        parties=parties,
        keywords=keywords,
        amounts=amounts,
        ai_summary=ai_summary
    )

@app.route('/download')
def download():
    filename = session.get('filename')
    dates = session.get('dates', [])
    parties = session.get('parties', [])
    keywords = session.get('keywords', [])
    amounts = session.get('amounts', [])
    ai_summary = session.get('ai_summary', '')

    pdf_path = generate_pdf_report(filename, dates, parties, keywords, amounts, ai_summary)
    return send_file(pdf_path, as_attachment=True, download_name=f"{filename}_analysis.pdf")

if __name__ == '__main__':
    app.run(debug=True)
    




