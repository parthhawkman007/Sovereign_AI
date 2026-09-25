"""
SOVEREIGN AI WORKBENCH — HARD TEST SUITE
Tests: Reasoning, Coding (multi-lang), Document Extraction, Vision, Memory, Tools
"""
import requests
import json
import time
import sys

BASE = "http://localhost:8000"
PASS = "[PASS]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"

results = []
session_counter = [0]

def new_session():
    session_counter[0] += 1
    sid = f"hard_test_{session_counter[0]}"
    try:
        requests.post(f"{BASE}/reset-session", timeout=5)
    except Exception:
        pass
    return sid

def chat(message, session_id, timeout=180):
    """Stream a chat message, return (nodes_hit, result_text, latency)."""
    t0 = time.time()
    try:
        r = requests.get(
            f"{BASE}/chat",
            params={"message": message, "session_id": session_id},
            stream=True, timeout=timeout
        )
        nodes, result = [], ""
        for line in r.iter_lines():
            if not line:
                continue
            decoded = line.decode("utf-8") if isinstance(line, bytes) else line
            if decoded.startswith("data:"):
                try:
                    d = json.loads(decoded[5:])
                    if d.get("type") == "step":
                        nodes.append(d.get("node", "?"))
                    if d.get("type") == "result":
                        result = d.get("text", "")
                except Exception:
                    pass
            if result:
                break
        r.close()
        return nodes, result, round(time.time() - t0, 1)
    except Exception as e:
        return [], f"ERROR: {e}", round(time.time() - t0, 1)

def check(name, nodes, result, latency,
          expected_node=None, must_contain=None, must_not_contain=None,
          min_chars=20, notes=""):
    ok = True
    fails = []

    if expected_node and expected_node not in nodes:
        ok = False
        fails.append(f"Expected node '{expected_node}' not in {nodes}")

    if must_contain:
        for kw in must_contain:
            if kw.lower() not in result.lower():
                ok = False
                fails.append(f"Missing keyword: '{kw}'")

    if must_not_contain:
        for kw in must_not_contain:
            if kw.lower() in result.lower():
                ok = False
                fails.append(f"Should NOT contain: '{kw}'")

    if len(result.strip()) < min_chars:
        ok = False
        fails.append(f"Response too short ({len(result)} chars, need {min_chars})")

    status = PASS if ok else FAIL
    results.append((name, ok, latency, result[:120].replace("\n", " ")))

    print(f"\n  {status}  {name}  [{latency}s]")
    if notes:
        print(f"         NOTE: {notes}")
    print(f"         Nodes : {nodes}")
    print(f"         Result: {result[:150].replace(chr(10), ' ')}")
    if fails:
        for f_ in fails:
            print(f"         FAIL : {f_}")
    return ok


# ─────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("  SOVEREIGN AI WORKBENCH — HARD TEST SUITE")
print("="*70)

# ─── SECTION 1: REASONING ────────────────────────────────────────
print("\n" + "─"*70)
print("  SECTION 1 — REASONING NODE (phi4-mini)")
print("─"*70)

sid = new_session()

nodes, result, lat = chat("What is the Pythagorean theorem? Give me the formula and an example.", sid)
check("Reasoning: Math — Pythagorean theorem", nodes, result, lat,
      expected_node="reasoning", must_contain=["a²", "b²", "c²"] or ["a^2"],
      notes="Basic math knowledge")

nodes, result, lat = chat("Explain what LangGraph is and how it differs from LangChain.", sid)
check("Reasoning: Technical — LangGraph vs LangChain", nodes, result, lat,
      expected_node="reasoning", must_contain=["graph", "node"],
      notes="Technical knowledge")

nodes, result, lat = chat(
    "A train leaves City A at 9 AM going 80 km/h. Another train leaves City B "
    "(320 km away) at 10 AM going 100 km/h toward City A. When do they meet?",
    new_session()
)
check("Reasoning: Logic — Train meeting problem", nodes, result, lat,
      expected_node="reasoning", must_contain=["km", "hour"],
      notes="Multi-step logic problem")

nodes, result, lat = chat(
    "Summarize the key differences between REST and GraphQL APIs in 3 bullet points.",
    new_session()
)
check("Reasoning: Summary — REST vs GraphQL", nodes, result, lat,
      expected_node="reasoning", must_contain=["REST", "GraphQL"],
      notes="Structured summarization")

# ─── SECTION 2: CODING ───────────────────────────────────────────
print("\n" + "─"*70)
print("  SECTION 2 — CODING NODE (qwen2.5-coder)")
print("─"*70)

nodes, result, lat = chat(
    "Write a Python function that calculates fibonacci(n) recursively and print fibonacci(10).",
    new_session()
)
check("Coding: Python — Fibonacci", nodes, result, lat,
      expected_node="coding",
      must_contain=["```python", "55"],
      notes="Python execution — fib(10)=55")

nodes, result, lat = chat(
    "Write a Python script using pandas to create a DataFrame with 3 columns "
    "(Name, Age, Score), add 3 sample rows, and print the mean score.",
    new_session()
)
check("Coding: Python + Pandas — DataFrame stats", nodes, result, lat,
      expected_node="coding",
      must_contain=["```python"],
      notes="Pandas usage")

nodes, result, lat = chat(
    "Write a Python script that reads workspace/uploads/industrial_equipment_inspection.csv "
    "and prints the column names and first 3 rows.",
    new_session()
)
check("Coding: Python — Read real CSV file from workspace", nodes, result, lat,
      expected_node="coding",
      must_contain=["```python"],
      must_not_contain=["Security Policy Violation", "NameError"],
      notes="Real file I/O test")

nodes, result, lat = chat(
    "Write a JavaScript function that reverses a string and show an example.",
    new_session()
)
check("Coding: JavaScript — String reverse", nodes, result, lat,
      expected_node="coding",
      must_contain=["function"],
      notes="JS code generation (not executed, just generated)")

nodes, result, lat = chat(
    "Write a SQL query to find the top 5 employees by salary from a table "
    "called 'employees' with columns: id, name, department, salary.",
    new_session()
)
check("Coding: SQL — Top-5 salary query", nodes, result, lat,
      expected_node="coding",
      must_contain=["SELECT", "salary"],
      notes="SQL code generation")

nodes, result, lat = chat(
    "Write a Python class called BankAccount with deposit, withdraw, and balance methods. "
    "Create an instance, deposit 1000, withdraw 250, and print the balance.",
    new_session()
)
check("Coding: Python OOP — BankAccount class", nodes, result, lat,
      expected_node="coding",
      must_contain=["```python", "750"],
      notes="OOP + execution — balance should be 750")

nodes, result, lat = chat(
    "Write a Python script that sorts a list [5, 2, 8, 1, 9, 3] using bubble sort "
    "and prints each step.",
    new_session()
)
check("Coding: Python — Bubble sort with steps", nodes, result, lat,
      expected_node="coding",
      must_contain=["```python"],
      notes="Algorithm implementation + execution")

# ─── SECTION 3: DOCUMENT EXTRACTION ─────────────────────────────
print("\n" + "─"*70)
print("  SECTION 3 — DOCUMENT TOOLS NODE (granite3.2-vision)")
print("─"*70)

nodes, result, lat = chat(
    "Read the file workspace/uploads/inspection_report.txt and summarize its contents.",
    new_session(), timeout=120
)
check("Document: TXT — inspection_report.txt summary", nodes, result, lat,
      expected_node="document_tools",
      must_contain=["inspection_report.txt"],
      notes="Plain text file read")

nodes, result, lat = chat(
    "Extract key findings from workspace/uploads/MRPL_Synthetic_Inspection_Report_T301.docx",
    new_session(), timeout=180
)
check("Document: DOCX — MRPL inspection report extraction", nodes, result, lat,
      expected_node="document_tools",
      must_contain=["MRPL_Synthetic_Inspection_Report_T301.docx"],
      notes="Word document extraction")

nodes, result, lat = chat(
    "Read workspace/uploads/industrial_equipment_inspection.csv and "
    "tell me what equipment types are listed.",
    new_session(), timeout=120
)
check("Document: CSV — equipment types extraction", nodes, result, lat,
      expected_node="document_tools",
      must_contain=["industrial_equipment_inspection.csv"],
      notes="CSV document read")

nodes, result, lat = chat(
    "Summarize the key inspection findings from workspace/uploads/sample_refinery_inspection_report.pdf",
    new_session(), timeout=240
)
check("Document: PDF — refinery inspection report", nodes, result, lat,
      expected_node="document_tools",
      must_contain=["sample_refinery_inspection_report.pdf"],
      min_chars=50,
      notes="PDF extraction with granite vision")

nodes, result, lat = chat(
    "Read workspace/uploads/ArohanXRef.pdf and give me the first 3 key topics.",
    new_session(), timeout=300
)
check("Document: PDF (large) — ArohanXRef topics", nodes, result, lat,
      expected_node="document_tools",
      must_contain=["ArohanXRef.pdf"],
      min_chars=50,
      notes="Large PDF extraction")

# ─── SECTION 4: VISION / IMAGE ───────────────────────────────────
print("\n" + "─"*70)
print("  SECTION 4 — VISION NODE (granite3.2-vision)")
print("─"*70)

nodes, result, lat = chat(
    "Analyze the image workspace/uploads/pid_sample.png and describe what you see in this P&ID diagram.",
    new_session(), timeout=120
)
check("Vision: P&ID diagram analysis", nodes, result, lat,
      expected_node="vision",
      must_contain=["pid_sample.png"],
      notes="Engineering drawing analysis")

nodes, result, lat = chat(
    "Look at workspace/uploads/Screenshot 2026-03-07 192222.png and tell me what is shown on screen.",
    new_session(), timeout=120
)
check("Vision: Screenshot analysis", nodes, result, lat,
      expected_node="vision",
      must_contain=["Screenshot 2026-03-07 192222.png"],
      notes="General image analysis")

nodes, result, lat = chat(
    "Extract any text visible in workspace/uploads/test1.jpg using OCR.",
    new_session(), timeout=120
)
check("Vision: OCR text extraction from JPG", nodes, result, lat,
      expected_node="vision",
      must_contain=["test1.jpg"],
      notes="OCR extraction")

nodes, result, lat = chat(
    "Analyze workspace/uploads/technical-drawing.webp and identify any components or labels visible.",
    new_session(), timeout=120
)
check("Vision: Technical drawing analysis (webp)", nodes, result, lat,
      expected_node="vision",
      must_contain=["technical-drawing.webp"],
      notes="Technical drawing component identification")

# ─── SECTION 5: TOOLS + PLUGIN ───────────────────────────────────
print("\n" + "─"*70)
print("  SECTION 5 — TOOLS NODE (plugin + built-in tools)")
print("─"*70)

nodes, result, lat = chat(
    "Convert 100 PSI to Bar and also convert 250 degrees Celsius to Fahrenheit.",
    new_session(), timeout=60
)
check("Tools: Unit conversion (PSI->Bar, C->F)", nodes, result, lat,
      must_contain=["bar", "fahrenheit"] or ["6.89", "482"],
      notes="Engineering unit converter plugin")

# ─── SECTION 6: STRUCTURED EXTRACTION + VALIDATION ──────────────
print("\n" + "─"*70)
print("  SECTION 6 — MULTI-STEP PIPELINE (extraction → validation → tools)")
print("─"*70)

nodes, result, lat = chat(
    "Read workspace/uploads/industrial_equipment_inspection.csv and create an Excel file "
    "with a summary of the equipment inspection data.",
    new_session(), timeout=300
)
check("Pipeline: CSV → Excel generation", nodes, result, lat,
      must_contain=["document_tools"] or ["coding"],
      notes="Multi-step: read CSV → extract → generate XLSX")

# ─── FINAL REPORT ────────────────────────────────────────────────
print("\n" + "="*70)
print("  FINAL RESULTS")
print("="*70)

passed = sum(1 for _, ok, _, _ in results if ok)
failed = sum(1 for _, ok, _, _ in results if not ok)
total = len(results)

for name, ok, lat, snippet in results:
    status = PASS if ok else FAIL
    print(f"  {status}  [{lat:>5.1f}s]  {name}")

print()
print(f"  TOTAL: {passed}/{total} PASSED  |  {failed} FAILED")
print("="*70)

sys.exit(0 if failed == 0 else 1)
