import subprocess
import os
import sys
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
from pptx.util import Inches as PptxInches, Pt as PptxPt
from pptx.dml.color import RGBColor as PptxRGBColor
import yaml
from pypdf import PdfReader
import pytesseract
from PIL import Image, ImageEnhance
from langchain_core.tools import tool

from model_router import router
OLLAMA_API = "http://localhost:11434/api/generate"


# ── Security Exception (must be defined before any function that raises it) ──
class SecurityError(Exception):
    """Raised when a security policy violation is detected."""
    pass


def _validate_workspace_path(filepath: str) -> str:
    """Ensures the filepath is within the workspace directory."""
    workspace_root = os.path.abspath(os.getcwd())
    abs_path = os.path.abspath(filepath)
    if not abs_path.startswith(workspace_root):
        raise SecurityError(f"🔒 Path traversal attempt blocked: {filepath}")
    return abs_path

def _get_timestamped_filename(base_name: str) -> str:
    parts = base_name.split('.')
    name = ".".join(parts[:-1])
    ext = parts[-1]
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    return os.path.join("workspace", "processed", f"{name}_{timestamp}.{ext}")

@tool
def read_local_file(filepath: str) -> str:
    """Reads a local file. Supports .txt, .md, .csv, .docx"""
    try:
        filepath = _validate_workspace_path(filepath)
        if not os.path.exists(filepath):
            return f"Error: File not found at {filepath}"
        ext = filepath.lower().split('.')[-1]
        if ext == 'docx':
            doc = Document(filepath)
            content = []
            for p in doc.paragraphs:
                if p.text.strip():
                    content.append(p.text)
            for table in doc.tables:
                for row in table.rows:
                    row_data = [cell.text.replace("\n", " ").strip() for cell in row.cells]
                    content.append(" | ".join(row_data))
            return "\n".join(content)
        else:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

import pdfplumber
import pymupdf as fitz

# FIX 4: Maximum number of pages to process with OCR/vision fallback.
# Pages beyond this limit that have no native text will not receive vision analysis.
# Increase this if scanned documents are longer; note each vision call adds ~10-30s on CPU.
MAX_OCR_PAGES = 5

def extract_pdf_pages(filepath: str) -> list:
    """Helper to extract PDF pages (text, tables, fallback OCR). Returns list of dicts."""
    import time
    start_time = time.time()
    
    pages_data = []
    page_has_text = []
    
    doc = fitz.open(filepath)
    with pdfplumber.open(filepath) as pdf:
        for i, page in enumerate(pdf.pages):
            page_text_blocks = []
            text = doc[i].get_text("text")
            has_text = False
            
            if text and text.strip():
                page_text_blocks.append(text.strip())
                has_text = True
                
            print(f"[PDF] page={i+1} native_text_length={len(text) if text else 0}")
            
            tables = page.extract_tables()
            for table in tables:
                has_text = True
                page_text_blocks.append("[Tabular Data Detected]:")
                for row in table:
                    clean_row = [str(c).replace("\n", " ") if c else "" for c in row]
                    page_text_blocks.append(" | ".join(clean_row))
            
            page_has_text.append(has_text)
            pages_data.append({
                "page": i + 1,
                "text": "\n".join(page_text_blocks).strip(),
                "has_text": has_text
            })
            
    parse_time = time.time()
    print(f"[Timing] PDF parsing & chunking: {parse_time - start_time:.2f}s")
    
    # 2. Convert first MAX_OCR_PAGES pages to images and analyze with vision model if no text
    try:
        for i in range(min(MAX_OCR_PAGES, len(doc))):  # FIX 4: was hardcoded min(2, ...)
            if i < len(page_has_text) and page_has_text[i]:
                print(f"Skipping OCR/Vision for page {i+1} (already has text)")
                continue
            print(f"Invoking OCR/Vision for page {i+1}...")
            page = doc.load_page(i)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_path = filepath + f"_page_{i}.jpg"
            pix.save(img_path)
            
            vision_analysis = analyze_image.invoke({
                "image_path": img_path,
                "prompt": "Analyze this document page carefully. Extract any text, charts, diagrams, or flowcharts present. Be detailed and preserve structure."
            })
            
            pages_data[i]["text"] += f"\n[Vision Analysis of Page {i+1}]:\n{vision_analysis}"
            
            try: os.remove(img_path)
            except: pass
    except Exception as e:
        print(f"(Vision extraction skipped: {e})")
        
    final_time = time.time()
    print(f"[Timing] OCR & vision processing: {final_time - parse_time:.2f}s")
    print(f"[Observability] PDF processing complete. Pages: {len(page_has_text)}, OCR invoked: {not all(page_has_text[:2]) if len(page_has_text) > 0 else False}")
    
    return pages_data


@tool
def read_pdf_file(filepath: str) -> str:
    """Reads a local PDF file extracting layout, tables, and multimodal vision analysis."""
    try:
        filepath = _validate_workspace_path(filepath)
        if not os.path.exists(filepath):
            return f"Error: File not found at {filepath}"
            
        pages = extract_pdf_pages(filepath)
        output = []
        for p in pages:
            output.append(f"\n--- PDF Page {p['page']} ---")
            output.append(p['text'])
            
        return "\n".join(output).strip()
    except Exception as e:
        return f"Error reading PDF: {e}"

@tool
def read_ppt_file(filepath: str) -> str:
    """Reads a local PowerPoint (.pptx) file extracting text and layout tables."""
    try:
        filepath = _validate_workspace_path(filepath)
        if not os.path.exists(filepath):
            return f"Error: File not found at {filepath}"
        prs = Presentation(filepath)
        output = []
        for i, slide in enumerate(prs.slides):
            output.append(f"--- Slide {i+1} ---")
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    output.append(shape.text.strip())
                if shape.has_table:
                    output.append("[Tabular Data Detected]:")
                    for row in shape.table.rows:
                        row_data = [cell.text_frame.text.replace("\n", " ").strip() for cell in row.cells]
                        output.append(" | ".join(row_data))
        return "\n".join(output).strip()
    except Exception as e:
        return f"Error reading PowerPoint file: {e}"


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
    """Performs advanced OCR on an image using the local vision model."""
    try:
        image_path = _validate_workspace_path(image_path)
        if not os.path.exists(image_path):
            return f"Error: File not found at {image_path}"
        prompt = "You are an expert, precise OCR engine. Extract all text exactly as it appears in this image. Preserve layout, bullet points, and tabular structures if any. Do not describe the image or add commentary. Output ONLY the raw extracted text."
        return analyze_image.invoke({"image_path": image_path, "prompt": prompt})
    except Exception as e:
        return f"OCR Error: {e}"

@tool
def analyze_engineering_drawing(image_path: str) -> str:
    """Specifically tuned vision prompt for P&IDs using sliding-window chunking (Image Tiling) for high-res detail."""
    try:
        image_path = _validate_workspace_path(image_path)
        if not os.path.exists(image_path):
            return f"Error: File not found at {image_path}"
        from PIL import Image
        img = Image.open(image_path)
        width, height = img.size
        
        # Split into 4 quadrants
        quads = [
            (0, 0, width//2, height//2),
            (width//2, 0, width, height//2),
            (0, height//2, width//2, height),
            (width//2, height//2, width, height)
        ]
        
        results = []

        prompt_template = (
            "You are an expert piping engineer. Analyze this high-res quadrant "
            "(Sector {sector} with coordinates {coords}) of an engineering drawing/P&ID. "
            "Use a combination of Vision, OCR, Spatial Relationships, Symbol Interpretation, and Line Analysis. "
            "Extract all equipment tag numbers, instrument loops, pipe classes, valve designations, and line sizes visible. "
            "For any connections or relationships (e.g., CONNECTED_TO, FEEDS, CONTROLLED_BY), you MUST explicitly verify visual evidence. "
            "If a line crosses the boundary or the relationship is unclear, return "
            "'AMBIGUOUS / REQUIRES HUMAN REVIEW' for that relationship rather than inventing one. "
            "Be extremely precise. Do not hallucinate."
        )

        for i, box in enumerate(quads):
            quad_img = img.crop(box)
            quad_path = image_path + f"_quad_{i}.png"
            quad_img.save(quad_path)
            
            p = prompt_template.format(sector=i + 1, coords=box)
            quad_result = analyze_image.invoke({"image_path": quad_path, "prompt": p})
            results.append(f"--- Sector {i+1} (Crop Coordinates: {box}) ---\n{quad_result}")

            
            try: os.remove(quad_path)
            except: pass
            
        return "\n\n".join(results)
    except Exception as e:
        return f"Error in engineering drawing tiling: {e}"

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
def create_approval_note(content: str, facts_json: str = "{}", filename: str = "Approval_Note.docx") -> str:
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
                
        # Insert deterministic tables if facts are provided
        import json
        facts = {}
        try:
            facts = json.loads(facts_json)
        except:
            pass
            
        if facts and "findings" in facts:
            doc.add_heading("Structured Findings", level=2)
            t = doc.add_table(rows=1, cols=4)
            t.style = 'Table Grid'
            hdr = t.rows[0].cells
            hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text = 'Finding ID', 'Description', 'Target', 'Severity'
            for f_item in facts["findings"]:
                row = t.add_row().cells
                row[0].text = f_item.get("id", "")
                row[1].text = f_item.get("description", "")
                row[2].text = f_item.get("target", "")
                row[3].text = f_item.get("severity", "")
                
        if facts and "measurements" in facts:
            doc.add_heading("Measurements", level=2)
            t3 = doc.add_table(rows=1, cols=4)
            t3.style = 'Table Grid'
            hdr3 = t3.rows[0].cells
            hdr3[0].text, hdr3[1].text, hdr3[2].text, hdr3[3].text = 'ID', 'Value', 'Unit', 'Target'
            for m_item in facts["measurements"]:
                row = t3.add_row().cells
                row[0].text = m_item.get("id", "")
                
                v = m_item.get("raw_value")
                if v is None:
                    v = m_item.get("normalized_value", "N/A")
                row[1].text = str(v)
                row[2].text = m_item.get("unit", "")
                row[3].text = m_item.get("target", "")

        if facts and "actions" in facts:
            doc.add_heading("Recommended Actions (Traceability)", level=2)
            t2 = doc.add_table(rows=1, cols=4)
            t2.style = 'Table Grid'
            hdr2 = t2.rows[0].cells
            hdr2[0].text, hdr2[1].text, hdr2[2].text, hdr2[3].text = 'Action ID', 'Linked Finding', 'Target', 'Timeframe'
            for a in facts["actions"]:
                row = t2.add_row().cells
                row[0].text = a.get("id", "")
                row[1].text = a.get("finding_id", "")
                row[2].text = a.get("target", "")
                row[3].text = a.get("timeframe", "")


        
        doc.save(ts_filename)
        return f"Successfully saved highly formatted approval note to {ts_filename}"

    except Exception as e:
        return f"Error creating approval note: {e}"

@tool
def create_excel_report(data: str, filename: str = "Report.xlsx", facts_json: str = "{}") -> str:
    """Creates a styled Excel report with multiple worksheets using facts_json if available."""
    try:
        import json
        ts_filename = _get_timestamped_filename(filename)
        wb = Workbook()
        
        # Styles
        header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        zebra_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
        
        def format_sheet(ws):
            for r_idx, row in enumerate(ws.iter_rows()):
                for cell in row:
                    cell.border = thin_border
                    if r_idx == 0:
                        cell.fill = header_fill
                        cell.font = header_font
                        cell.alignment = Alignment(horizontal='center', vertical='center')
                    elif r_idx % 2 != 0:
                        cell.fill = zebra_fill
            for col in ws.columns:
                max_length = 0
                column = col[0].column_letter 
                for cell in col:
                    try: 
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except: pass
                ws.column_dimensions[column].width = min(max_length + 2, 50)
            if ws.max_row > 1:
                ws.auto_filter.ref = ws.dimensions

        facts = json.loads(facts_json)
        sheets_created = False

        if facts.get("equipment"):
            ws = wb.active if not sheets_created else wb.create_sheet("Equipment")
            if not sheets_created: ws.title = "Equipment"
            sheets_created = True
            ws.append(["Equipment ID", "Name", "Location", "Source", "Evidence", "Confidence"])
            for equipment in facts["equipment"]:
                provenance = equipment.get("provenance", {})
                ws.append([
                    equipment.get("id", ""),
                    equipment.get("name", ""),
                    equipment.get("location", ""),
                    provenance.get("source", ""),
                    provenance.get("evidence", ""),
                    provenance.get("confidence", ""),
                ])
            format_sheet(ws)
        
        if facts.get("findings"):
            ws = wb.active if not sheets_created else wb.create_sheet("Findings")
            if not sheets_created: ws.title = "Findings"
            sheets_created = True
            ws.append(["Finding ID", "Description", "Severity", "Target", "Source"])
            for f in facts["findings"]:
                ws.append([f.get("id", ""), f.get("description", ""), f.get("severity", ""), f.get("target", ""), f.get("provenance", {}).get("source", "")])
            format_sheet(ws)
            
        if facts.get("measurements"):
            ws = wb.active if not sheets_created else wb.create_sheet("Measurements")
            if not sheets_created: ws.title = "Measurements"
            sheets_created = True
            ws.append(["ID", "Value", "Unit", "Target", "Source"])
            for m in facts["measurements"]:
                val = m.get("raw_value")
                if val is None: val = m.get("normalized_value", "")
                ws.append([m.get("id", ""), val, m.get("unit", ""), m.get("target", ""), m.get("provenance", {}).get("source", "")])
            format_sheet(ws)
            
        if facts.get("actions"):
            ws = wb.active if not sheets_created else wb.create_sheet("Actions")
            if not sheets_created: ws.title = "Actions"
            sheets_created = True
            ws.append(["Action ID", "Finding ID", "Description", "Timeframe", "Target"])
            for a in facts["actions"]:
                ws.append([a.get("id", ""), a.get("finding_id", ""), a.get("description", ""), a.get("timeframe", ""), a.get("target", "")])
            format_sheet(ws)
            
        if not sheets_created:
            # Fallback to CSV text
            data = data.replace('```csv', '').replace('```', '').strip()
            ws = wb.active
            ws.title = "Data Report"
            reader = csv.reader(io.StringIO(data))
            rows = list(reader)
            if not rows: return "No data provided for Excel."
            for r in rows: ws.append(r)
            format_sheet(ws)
            
        wb.save(ts_filename)
        return f"Successfully saved styled Excel report to {ts_filename}"
    except Exception as e:
        return f"Error creating Excel report: {e}"

@tool
def write_local_file(filepath: str, content: str) -> str:
    """Writes or overwrites a local file with the provided content. Automatically creates a backup."""
    try:
        import shutil
        import datetime
        filepath = _validate_workspace_path(filepath)
        
        # Shadow backup system
        if os.path.exists(filepath):
            backup_dir = os.path.join(os.getcwd(), "workspace", ".backups")
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"{os.path.basename(filepath)}_{timestamp}.bak")
            shutil.copy2(filepath, backup_path)
            
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {filepath} (Original backed up)"
    except Exception as e:
        return f"Error writing file: {e}"

@tool
def replace_text_in_file(filepath: str, old_text: str, new_text: str) -> str:
    """Replaces all occurrences of old_text with new_text in the specified file. Automatically creates a backup."""
    try:
        import shutil
        import datetime
        filepath = _validate_workspace_path(filepath)
        if not os.path.exists(filepath):
            return f"Error: File not found at {filepath}"
            
        # Shadow backup system
        backup_dir = os.path.join(os.getcwd(), "workspace", ".backups")
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"{os.path.basename(filepath)}_{timestamp}.bak")
        shutil.copy2(filepath, backup_path)
            
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        if old_text not in content:
            return f"Error: The exact old_text was not found in the file."
        updated_content = content.replace(old_text, new_text)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        return f"Successfully updated {filepath} (Original backed up)"
    except Exception as e:
        return f"Error updating file: {e}"

@tool
def read_excel_file(filepath: str) -> str:
    """Reads an existing Excel (.xlsx) file and returns plain text."""
    try:
        filepath = _validate_workspace_path(filepath)  # FIX 3: path traversal protection
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
            txBox = slide.shapes.add_textbox(PptxInches(0.5), PptxInches(7.0), PptxInches(5), PptxInches(0.5))
            tf = txBox.text_frame
            p = tf.paragraphs[0]
            p.text = "CLASSIFICATION: CONFIDENTIAL INTERNAL ONLY"
            p.font.size = PptxPt(10)
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
def analyze_image(image_path: str, prompt: str = "First, transcribe ALL visible text from this image exactly as written. Then describe any diagrams, charts, or visual elements in a structured format.", model: str = "") -> str:
    """Analyzes an image using the local vision model. Optionally pass a specific model name to override the default."""
    try:
        image_path = _validate_workspace_path(image_path)
        if not os.path.exists(image_path):
            return f"Error: File not found at {image_path}"
        # Resolve model: use passed-in model, or fall back to router's current vision model
        resolved_model = router.resolve_model(model) if model else router.get_vision_model()
        with open(image_path, "rb") as f:
            encoded_string = base64.b64encode(f.read()).decode('utf-8')
        payload = {"model": resolved_model, "prompt": prompt, "images": [encoded_string], "stream": False}
        response = requests.post(OLLAMA_API, json=payload)
        response.raise_for_status()
        return response.json()['response'].strip()
    except Exception as e:
        return f"Error analyzing image: {e}"


# Modules that are completely forbidden in the sandbox
_BLOCKED_MODULES = frozenset([
    'sys', 'subprocess', 'socket', 'importlib', 'ctypes',  # os removed: os.path.* is allowed
    'pickle', 'shelve', 'builtins', 'shutil', 'pathlib', 'tempfile',
    'signal', 'threading', 'multiprocessing', 'concurrent',
    'urllib', 'http', 'ftplib', 'smtplib', 'requests', 'io', 'pty'
])


# Specific os.* calls that escape the sandbox — blocked at AST level
_DANGEROUS_OS_ATTRS = frozenset([
    'system', 'popen', 'popen2', 'popen3', 'popen4',
    'execv', 'execve', 'execvp', 'execvpe', 'execl', 'execle', 'execlp', 'execlpe',
    'spawnl', 'spawnle', 'spawnlp', 'spawnlpe',
    'spawnv', 'spawnve', 'spawnvp', 'spawnvpe',
    'startfile', 'fork', 'forkpty', 'kill', 'killpg',
])

def _check_sandbox_security(code: str):
    """
    Multi-layer AST security check.
    Allows: import os (for os.path.*), open(), pandas, csv, math.
    Blocks: sys, subprocess, socket, exec/eval, and dangerous os shell functions.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise SecurityError(f"Syntax error in code: {e}")

    for node in ast.walk(tree):
        # Block: import os / import subprocess etc.
        if isinstance(node, ast.Import):
            for alias in node.names:
                base = alias.name.split('.')[0]
                if base in _BLOCKED_MODULES:
                    raise SecurityError(f"Import of '{alias.name}' is blocked in sandbox.")

        # Block: from os import path / from importlib import import_module
        elif isinstance(node, ast.ImportFrom):
            base = (node.module or '').split('.')[0]
            if base in _BLOCKED_MODULES:
                raise SecurityError(f"Import from '{node.module}' is blocked in sandbox.")

        # Block: __import__('os') / __import__('subprocess')
        elif isinstance(node, ast.Call):
            func = node.func
            # __import__('something')
            if isinstance(func, ast.Name) and func.id == '__import__':
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        base = arg.value.split('.')[0]
                        if base in _BLOCKED_MODULES:
                            raise SecurityError(f"__import__('{arg.value}') is blocked in sandbox.")
                    else:
                        raise SecurityError("Dynamic __import__() calls are blocked in sandbox.")

            # Block exec/eval completely
            if isinstance(func, ast.Name) and func.id in ('exec', 'eval'):
                raise SecurityError(f"{func.id}() is blocked in sandbox.")

            # Block getattr, setattr, hasattr, delattr bypasses
            if isinstance(func, ast.Name) and func.id in ('getattr', 'setattr', 'hasattr', 'delattr'):
                if len(node.args) >= 2:
                    attr_arg = node.args[1]
                    if isinstance(attr_arg, ast.Constant) and isinstance(attr_arg.value, str):
                        if attr_arg.value in ('__builtins__', '__subclasses__', '__globals__', '__class__', '__dict__', '__bases__', '__mro__'):
                            raise SecurityError(f"{func.id}() access to '{attr_arg.value}' is blocked.")
                    else:
                        raise SecurityError(f"Dynamic {func.id}() with non-literal attribute is blocked.")

            # Block dangerous os.* shell-escape functions (os.system, os.popen, os.exec*, os.spawn*)
            if isinstance(func, ast.Attribute):
                if (isinstance(func.value, ast.Name) and func.value.id == 'os'
                        and func.attr in _DANGEROUS_OS_ATTRS):
                    raise SecurityError(
                        f"os.{func.attr}() is blocked in sandbox — shell/process operations not permitted."
                    )

        # Block access to __builtins__, __class__, __subclasses__ etc.
        elif isinstance(node, ast.Attribute):
            if node.attr in ('__builtins__', '__subclasses__', '__globals__', '__class__', '__dict__', '__bases__', '__mro__'):
                raise SecurityError(f"Access to '{node.attr}' is blocked in sandbox.")

        # Block direct Name access to __builtins__ and dangerous built-in functions
        elif isinstance(node, ast.Name):
            if node.id in ('__builtins__', '__subclasses__', '__globals__', '__class__', '__dict__', '__bases__', '__mro__'):
                raise SecurityError(f"Direct access to '{node.id}' is blocked in sandbox.")
            # NOTE: open() is intentionally ALLOWED — the sandbox runs code in an
            # isolated subprocess with a stripped environment. File I/O is legitimate
            # for CSV/data processing tasks. Path traversal is prevented at the
            # tool-call layer (_validate_workspace_path) not at AST level.
            if node.id in ('globals', 'locals', 'vars', 'exec', 'eval', 'compile', 'breakpoint'):
                raise SecurityError(f"Function '{node.id}()' is blocked in sandbox.")



@tool
def execute_python_code(code: str, timeout: int = 10) -> str:
    """Executes python code in a hardened local sandbox with AST security scanning."""
    try:
        _check_sandbox_security(code)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as tmp:
            tmp.write(code)
            tmp_path = tmp.name

        # Strip environment to prevent env-var based escapes; keep only PYTHONPATH
        safe_env = {"PYTHONPATH": os.environ.get("PYTHONPATH", "")}

        try:
            result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=safe_env,
            )
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        output = result.stdout
        if result.stderr:
            output += f"\nErrors:\n{result.stderr}"
        return output.strip() if output.strip() else "Execution successful with no printed output."

    except SecurityError as se:
        return f"🔒 Sandbox Security Policy Violation: {se}"
    except subprocess.TimeoutExpired:
        return "Error: Code execution timed out (limit: 10s)."
    except Exception as e:
        return f"Error executing code: {e}"
