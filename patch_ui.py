import re

with open("static/index.html", "r", encoding="utf-8") as f:
    content = f.read()

sidebar_replacement = """
    <div class="sidebar-section-title">Presets</div>
    <div class="sidebar-items" id="history-list" style="flex: 0 0 auto; max-height: 180px;">
      <div class="chat-history-item" onclick="usePrompt('Extract the table of thickness readings from inspection_report.jpg and save it to an Excel file.')">
        📊 Scan to Excel
      </div>
      <div class="chat-history-item" onclick="usePrompt('What is the maximum allowable pressure according to the SOPs? Give me the exact source citation.')">
        📖 SOP Compliance Search
      </div>
      <div class="chat-history-item" onclick="usePrompt('Write a python script that calculates the stress on a 10 inch carbon steel pipe with 500 psi internal pressure and prints it.')">
        💻 Pipe Stress Calculation
      </div>
      <div class="chat-history-item" onclick="usePrompt('Draft a formal internal Approval Note for Sector 4 vessel maintenance based on recent ultrasonic inspection findings.')">
        📝 Executive Approval Note
      </div>
    </div>

    <div class="sidebar-section-title">Generated Files</div>
    <div class="sidebar-items" id="files-list" style="flex: 0 0 auto; max-height: 120px;">
    </div>

    <div class="sidebar-section-title">SOPs Indexed</div>
    <div class="sidebar-items" id="sops-list" style="flex: 0 0 auto; max-height: 100px;">
    </div>

    <div class="sidebar-section-title">Audit Logs</div>
    <div class="sidebar-items" id="audit-list" style="flex: 1;">
    </div>
"""

# Replace the presets section
content = re.sub(
    r'<div class="sidebar-section-title">Presets</div>.*?</div>.*?</div>.*?</div>.*?</div>.*?</div>',
    sidebar_replacement,
    content,
    flags=re.DOTALL
)

js_addition = """
  async function fetchBackendData() {
    try {
      const healthRes = await fetch('/health');
      const health = await healthRes.json();
      const statusBadge = document.querySelector('.status-badge');
      if (health.air_gapped) {
        statusBadge.innerHTML = `<span class="status-dot"></span><span>100% Air-Gapped</span>`;
      } else {
        statusBadge.innerHTML = `<span class="status-dot" style="background:#f87171;box-shadow:0 0 8px #f87171;"></span><span style="color:#f87171;">Online</span>`;
      }
      const gpuStatus = document.querySelector('.sidebar-footer span:last-child');
      if (health.active_reasoning) {
        gpuStatus.textContent = health.active_reasoning;
      }
    } catch (e) {}

    try {
      const filesRes = await fetch('/files');
      const files = await filesRes.json();
      const filesList = document.getElementById('files-list');
      if (filesList) {
        filesList.innerHTML = files.map(f => `
          <div class="chat-history-item" onclick="window.open('/download/${encodeURIComponent(f.name)}')">
            📄 ${f.name} (${f.size_kb}KB)
          </div>
        `).join('');
      }
    } catch (e) {}

    try {
      const sopsRes = await fetch('/sops');
      const sopsData = await sopsRes.json();
      const sopsList = document.getElementById('sops-list');
      if (sopsList) {
        sopsList.innerHTML = sopsData.sops.map(s => `
          <div class="chat-history-item">
            📖 ${s.name}
          </div>
        `).join('');
      }
    } catch (e) {}

    try {
      const auditRes = await fetch('/audit');
      const auditData = await auditRes.json();
      const auditList = document.getElementById('audit-list');
      if (auditList) {
        auditList.innerHTML = auditData.logs.reverse().map(l => `
          <div class="chat-history-item" style="font-size:10px; white-space:normal; line-height:1.2; padding:4px 8px;">
            ${l}
          </div>
        `).join('');
      }
    } catch (e) {}
  }

  window.addEventListener('load', fetchBackendData);
"""

# Insert JS additions
content = content.replace("</script>", js_addition + "\n</script>")

# Find `if (e.data === '[DONE]') {` in index.html to add `fetchBackendData();`
content = content.replace("es.close();\n        isThinking = false;", "es.close();\n        isThinking = false;\n        fetchBackendData();")

with open("static/index.html", "w", encoding="utf-8") as f:
    f.write(content)
print("patched")
