import subprocess
import os
import tempfile
import base64
import requests
import re
import csv
import io
import datetime
import ast

from docx import Document
from docx.shared import Inches, Pt, RGBColor
import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor as PptxRGBColor
import yaml
from pypdf import PdfReader
import pytesseract
from PIL import Image, ImageEnhance
from langchain_core.tools import tool

from model_router import router
OLLAMA_MODEL_VISION = router.get_vision_model()
OLLAMA_API = "http://localhost:11434/api/generate"

def _get_timestamped_filename(base_name: str) -> str:
    parts = base_name.split('.')
    name = ".".join(parts[:-1])
    ext = parts[-1]
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    return f"{name}_{timestamp}.{ext}"

@tool
def read_local_file(filepath: str) -> str:
    """Reads a local file. Supports .txt, .md, .csv, .docx"""
    try:
        if not os.path.exists(filepath):
            return f"Error: File not found at {filepath}"
        ext = filepath.lower().split('.')[-1]
        if ext == 'docx':
            doc = Document(filepath)
            return "\n".join([p.text for p in doc.paragraphs])
        else:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

@tool
def read_pdf_file(filepath: str) -> str:
    """Reads a local PDF file and extracts text."""
    try:
        if not os.path.exists(filepath):
            return f"Error: File not found at {filepath}"
        reader = PdfReader(filepath)
        return "\n".join([page.extract_text() for page in reader.pages]).strip()
    except Exception as e:
        return f"Error reading PDF: {e}"

@tool
def compare_documents(file1_path: str, file2_path: str) -> str:
    """Compares two files (txt, pdf, docx) and returns a summary of differences."""
    try:
        content1 = read_pdf_file.invoke({"filepath": file1_path}) if file1_path.endswith(".pdf") else read_local_file.invoke({"filepath": file1_path})
        content2 = read_pdf_file.invoke({"filepath": file2_path}) if file2_path.endswith(".pdf") else read_local_file.invoke({"filepath": file2_path})
        return f"--- FILE 1 ({file1_path}) ---\n{content1}\n\n--- FILE 2 ({file2_path}) ---\n{content2}\n\nPlease analyze these two documents and summarize the differences."
    except Exception as e:
        return f"Error comparing documents: {e}"

@tool
def ocr_image(image_path: str) -> str:
    """Performs on-device OCR on an image using pytesseract."""
    try:
        if not os.path.exists(image_path):
            return f"Error: File not found at {image_path}"
        img = Image.open(image_path).convert('L')
        img = ImageEnhance.Contrast(img).enhance(2.0)
        
        if os.path.exists(r"C:\Program Files\Tesseract-OCR\tesseract.exe"):
            pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            
        text = pytesseract.image_to_string(img)
        return text.strip() if text.strip() else "No text found in image."
    except Exception as e:
        return f"OCR Error: {e}"

@tool
def analyze_engineering_drawing(image_path: str) -> str:
    """Specifically tuned vision prompt for P&IDs and Engineering Drawings."""
    prompt = "You are an expert piping engineer. Analyze this P&ID / engineering drawing carefully. Extract all equipment tag numbers, instrument loops, pipe classes, valve designations, and line sizes. Be extremely precise."
    return analyze_image.invoke({"image_path": image_path, "prompt": prompt})

@tool
def extract_table_to_excel(image_path: str, filename: str = "Extracted_Table.xlsx") -> str:
    """Extracts tabular data from an image/scan and saves it directly to an Excel file."""
    prompt = "Extract any tables in this image. Output ONLY the table data in CSV format. Use commas to separate columns and newlines to separate rows. Do not include markdown formatting like ```csv."
    try:
        csv_data = analyze_image.invoke({"image_path": image_path, "prompt": prompt})
        ts_filename = _get_timestamped_filename(filename)
        return create_excel_report.invoke({"data": csv_data, "filename": ts_filename})
    except Exception as e:
        return f"Error extracting table to Excel: {e}"


def _add_markdown_runs(paragraph, text):
    """Helper to parse **bold** and *italic* in a single Word paragraph."""
    parts = re.split(r'(\*\*.*?\*\*)', text)
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            paragraph.add_run(part[2:-2]).bold = True
        else:
            subparts = re.split(r'(\*.*?\*)', part)
            for sub in subparts:
                if sub.startswith('*') and sub.endswith('*') and len(sub) > 2:
                    paragraph.add_run(sub[1:-1]).italic = True
                else:
                    paragraph.add_run(sub)

@tool
def create_approval_note(content: str, filename: str = "Approval_Note.docx") -> str:
    """Creates a highly formatted 'Approval Note' Word document parsing markdown (headers, bullets, bold)."""
    try:
        ts_filename = _get_timestamped_filename(filename)
        doc = Document()
        
        # Professional Header
        section = doc.sections[0]
        header = section.header
        hp = header.paragraphs[0]
        hp.text = "SOVEREIGN AI WORKBENCH - INTERNAL COMPANY DOCUMENT"
        hp.style.font.size = Pt(8)
        hp.style.font.color.rgb = RGBColor(128, 128, 128)
        
        # Title Page / Header section
        title = doc.add_heading("Formal Approval Note", level=0)
        title.alignment = 1 # Center
        
        meta = doc.add_paragraph()
        meta.add_run(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d')}\n").bold = True
        run = meta.add_run("CLASSIFICATION: CONFIDENTIAL / INTERNAL ONLY\n")
        run.bold = True
        run.font.color.rgb = RGBColor(255, 0, 0)
        meta.alignment = 1
        
        doc.add_paragraph("_" * 55).alignment = 1
        doc.add_paragraph("\n")
        
        # Basic markdown parser for the content
        # Clean potential code blocks
        content = content.replace("```markdown", "").replace("```", "")
        
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('### '):
                doc.add_heading(line[4:], level=3)
            elif line.startswith('## '):
                doc.add_heading(line[3:], level=2)
            elif line.startswith('# '):
                doc.add_heading(line[2:], level=1)
            elif line.startswith('- ') or line.startswith('* '):
                p = doc.add_paragraph(style='List Bullet')
                _add_markdown_runs(p, line[2:])
            else:
                p = doc.add_paragraph()
                _add_markdown_runs(p, line)
                
        doc.save(ts_filename)
        return f"Successfully saved highly formatted approval note to {ts_filename}"
    except Exception as e:
        return f"Error creating approval note: {e}"

@tool
def create_excel_report(data: str, filename: str = "Report.xlsx") -> str:
    """Creates a styled Excel report. Strips markdown and applies corporate formatting (Zebra striping, borders)."""
    try:
        # Clean markdown if present
        data = data.replace('```csv', '').replace('```', '').strip()
        
        ts_filename = _get_timestamped_filename(filename)
        wb = Workbook()
        ws = wb.active
        ws.title = "Data Report"

        reader = csv.reader(io.StringIO(data))
        rows = list(reader)
        
        if not rows:
            return "No data provided for Excel."

        # Styles
        header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        zebra_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

        for r_idx, row_data in enumerate(rows, 1):
            for c_idx, value in enumerate(row_data, 1):
                cell = ws.cell(row=r_idx, column=c_idx, value=value.strip() if isinstance(value, str) else value)
                cell.border = thin_border
                
                # Header styling
                if r_idx == 1:
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = Alignment(horizontal='center', vertical='center')
                # Zebra striping
                elif r_idx % 2 == 0:
                    cell.fill = zebra_fill
                    
        # Auto-adjust columns & add autofilter
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter 
            for cell in col:
                try: 
                    if len(str(cell.value)) > max_length:
                        max_length = len(cell.value)
                except: pass
            adjusted_width = (max_length + 2)
            ws.column_dimensions[column].width = min(adjusted_width, 50) # Cap width

        ws.auto_filter.ref = ws.dimensions
        
        wb.save(ts_filename)
        return f"Successfully saved styled Excel report to {ts_filename}"
    except Exception as e:
        return f"Error creating Excel report: {e}"

@tool
def read_excel_file(filepath: str) -> str:
    """Reads an existing Excel (.xlsx) file and returns plain text."""
    try:
        if not os.path.exists(filepath):
            return f"Error: File not found at {filepath}"
        wb = openpyxl.load_workbook(filepath)
        output = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            output.append(f"Sheet: {sheet_name}")
            for row in ws.iter_rows(values_only=True):
                row_str = " | ".join([str(c) if c is not None else "" for c in row])
                output.append(row_str)
        return "\n".join(output)
    except Exception as e:
        return f"Error reading Excel file: {e}"

@tool
def create_presentation(content: str, filename: str = "Presentation.pptx") -> str:
    """Creates a branded PowerPoint with a formal Title Slide and styled content slides."""
    try:
        ts_filename = _get_timestamped_filename(filename)
        prs = Presentation()
        
        # 1. Title Slide (Layout 0)
        title_slide_layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(title_slide_layout)
        title = slide.shapes.title
        subtitle = slide.placeholders[1]
        
        title.text = "Executive Summary"
        subtitle.text = f"Sovereign AI Generated\nDate: {datetime.datetime.now().strftime('%Y-%m-%d')}"
        
        # Change title font color to a corporate blue
        for run in title.text_frame.paragraphs[0].runs:
            run.font.color.rgb = PptxRGBColor(31, 78, 120)

        # Parse slides separated by ---
        content = content.replace("```markdown", "").replace("```", "")
        slide_contents = content.strip().split("---")
        
        for slide_text in slide_contents:
            lines = [l.strip() for l in slide_text.strip().split("\n") if l.strip()]
            if not lines: continue

            # Content Slide (Layout 1)
            slide_layout = prs.slide_layouts[1]
            slide = prs.slides.add_slide(slide_layout)
            
            # Title
            title_shape = slide.shapes.title
            title_shape.text = lines[0].replace('#', '').strip()
            for run in title_shape.text_frame.paragraphs[0].runs:
                run.font.color.rgb = PptxRGBColor(31, 78, 120)
            
            # Footer Watermark
            txBox = slide.shapes.add_textbox(Inches(0.5), Inches(7.0), Inches(5), Inches(0.5))
            tf = txBox.text_frame
            p = tf.paragraphs[0]
            p.text = "CLASSIFICATION: CONFIDENTIAL INTERNAL ONLY"
            p.font.size = Pt(10)
            p.font.color.rgb = PptxRGBColor(255, 0, 0)
            p.font.bold = True

            # Bullets
            if len(lines) > 1:
                body = slide.placeholders[1]
                tf = body.text_frame
                tf.clear()
                for i, bullet in enumerate(lines[1:]):
                    bullet_text = bullet.lstrip("-* ").strip()
                    if not bullet_text: continue
                    
                    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                    p.text = bullet_text
                    p.level = 0
                    
                    # If it was indented in markdown, indent in PPT
                    if bullet.startswith('  -') or bullet.startswith('  *'):
                        p.level = 1

        prs.save(ts_filename)
        return f"Successfully saved branded presentation to {ts_filename}"
    except Exception as e:
        return f"Error creating presentation: {e}"

@tool
def analyze_image(image_path: str, prompt: str = "Describe this image in detail.") -> str:
    """Analyzes an image using the local vision model."""
    try:
        if not os.path.exists(image_path):
            return f"Error: File not found at {image_path}"
        with open(image_path, "rb") as f:
            encoded_string = base64.b64encode(f.read()).decode('utf-8')
        payload = {"model": OLLAMA_MODEL_VISION, "prompt": prompt, "images": [encoded_string], "stream": False}
        response = requests.post(OLLAMA_API, json=payload)
        response.raise_for_status()
        return response.json()['response'].strip()
    except Exception as e:
        return f"Error analyzing image: {e}"

def _check_sandbox_security(code: str):
    """Parses AST to block dangerous imports like os, sys, subprocess"""
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ['os', 'sys', 'subprocess', 'socket']:
                    raise SecurityError(f"Import of {alias.name} is blocked in sandbox.")
        elif isinstance(node, ast.ImportFrom):
            if node.module in ['os', 'sys', 'subprocess', 'socket']:
                raise SecurityError(f"Import from {node.module} is blocked in sandbox.")

class SecurityError(Exception):
    pass

@tool
def execute_python_code(code: str, timeout: int = 5) -> str:
    """Executes python code in a hardened local sandbox."""
    try:
        _check_sandbox_security(code)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_script:
            temp_script.write(code)
            temp_script_path = temp_script.name

        result = subprocess.run(
            ["python", temp_script_path],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        os.remove(temp_script_path)
        
        output = result.stdout
        if result.stderr:
            output += f"\nErrors:\n{result.stderr}"
        return output.strip() if output else "Execution successful with no output."
        
    except SecurityError as se:
        return f"Sandbox Security Policy Violation: {se}"
    except subprocess.TimeoutExpired:
        if os.path.exists(temp_script_path):
            os.remove(temp_script_path)
        return f"Error: Execution timed out."
    except Exception as e:
        return f"Error executing code: {e}"
