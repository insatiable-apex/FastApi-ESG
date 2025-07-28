from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_ollama import ChatOllama
from langchain.prompts import PromptTemplate
from fpdf import FPDF
import shutil
import re
import uuid

app = FastAPI()


def load_pdf_text(file_path):
    loader = PyMuPDFLoader(file_path)
    documents = loader.load()
    return "\n".join(doc.page_content for doc in documents)


def beautify_compliance_output(raw_output: str) -> str:
    import re

    header = "SG Compliance Analysis Report\n\n"
    beautified = header

    # Remove markdown bolds and extra whitespace
    raw_output = raw_output.replace("**", "").strip()
    raw_output = re.sub(r'\n+', ' ', raw_output)  # Collapse all newlines to single line
    raw_output = re.sub(r'\s{2,}', ' ', raw_output)  # Remove excessive spaces

    # Use punctuation to break into paragraphs
    paragraphs = re.split(r'(?<=[.!?])\s+(?=[A-Z])', raw_output)

    for para in paragraphs:
        para = para.strip()
        if para:
            beautified += f"{para}\n\n"

    return beautified.strip()




def remove_emojis(text):
    emoji_pattern = re.compile("[^\x00-\x7F]+")
    return emoji_pattern.sub('', text)


def analyze_compliance(compliance_text, user_text):
    prompt = PromptTemplate(
        input_variables=["compliance", "user_doc"],
        template="""
You are an ESG Compliance Auditor for Saint-Gobain. Your task is to assess the compliance level of a vendor’s ESG report against the Saint-Gobain ESG Compliance Policy.

Compare the following ESG compliance policy:

{compliance}

With the following vendor-submitted ESG document:

{user_doc}

Instructions:
1. Evaluate the three pillars:
   - Environmental (E)
   - Social (S)
   - Governance (G)

2. For each:
   - Identify matching policy requirements.
   - Check coverage, alignment, and completeness.
   - Mark compliant / partially compliant / missing.

3. Assign a score (out of 100) per ESG pillar and overall.

4. Provide:
   - Bullet-pointed summaries per pillar
   - Overall compliance score
   - Actionable recommendations

Format output for a professional report.
"""
    )

    llm = ChatOllama(model="gemma", temperature=0.0)
    chain = prompt | llm
    result = chain.invoke({"compliance": compliance_text, "user_doc": user_text})
    return result.content


def generate_pdf(text: str, file_path: str):
    clean_text = remove_emojis(text)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)

    # Add a title
    pdf.set_font("Arial", style="B", size=14)
    pdf.cell(200, 10, txt="SG ESG Compliance Audit Report", ln=True, align="C")
    pdf.ln(10)

    pdf.set_font("Arial", size=12)
    for line in clean_text.split('\n'):
        pdf.multi_cell(0, 10, line)

    pdf.output(file_path)


@app.post("/analyze")
async def analyze_api(user_file: UploadFile = File(...)):
    user_doc_path = f"user_doc_{uuid.uuid4()}.pdf"
    report_path = f"compliance_report_{uuid.uuid4()}.pdf"

    # Save uploaded file
    with open(user_doc_path, "wb") as f:
        shutil.copyfileobj(user_file.file, f)

    
    # Load text
    compliance_text = load_pdf_text("ESG_SG_compliance.pdf")
    user_text = load_pdf_text(user_doc_path)

    # Analyze
    result = analyze_compliance(compliance_text, user_text)
    beautified = beautify_compliance_output(result)

    # Generate report
    generate_pdf(beautified, report_path)

    return FileResponse(
        path=report_path,
        filename="ComplianceReport.pdf",
        media_type="application/pdf"
    )

   
