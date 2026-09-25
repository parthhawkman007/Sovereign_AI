code = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sovereign AI</title>
<style>
  :root {
    --bg-page: #212121;
    --bg-sidebar: #171717;
    --bg-surface: #2f2f2f;
    --bg-surface-hover: #3a3a3a;
    --bg-input: #2f2f2f;
    --text-primary: #ececec;
    --text-secondary: #b4b4b4;
    --text-muted: #8e8e8e;
    --border-color: rgba(255, 255, 255, 0.1);
    --accent: #10a37f;
    --accent-blue: #3b82f6;
    --radius-pill: 9999px;
    --radius-card: 16px;
    --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: var(--font);
    background-color: var(--bg-page);
    color: var(--text-primary);
    height: 100vh;
    display: flex;
    overflow: hidden;
    -webkit-font-smoothing: antialiased;
  }

  /* ── Layout ── */
  #app {
    display: flex;
    width: 100vw;
    height: 100vh;
  }

  /* ── Sidebar (Collapsible, ChatGPT style) ── */
  #sidebar {
    width: 260px;
    background: var(--bg-sidebar);
    border-right: 1px solid var(--border-color);
    display: flex;
    flex-direction: column;
    padding: 12px;
    flex-shrink: 0;
    transition: margin-left 0.25s ease;
  }

  #sidebar.closed {
    margin-left: -260px;
  }

  .new-chat-btn {
    background: transparent;
    color: var(--text-primary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-pill);
    padding: 10px 14px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: space-between;
    transition: background 0.15s ease;
    margin-bottom: 16px;
  }
  .new-chat-btn:hover {
    background: var(--bg-surface);
  }

  .sidebar-section-title {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    padding: 6px 8px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .sidebar-items {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .chat-history-item {
    padding: 9px 12px;
    border-radius: 8px;
    font-size: 13px;
    color: var(--text-secondary);
    cursor: pointer;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .chat-history-item:hover {
    background: var(--bg-surface);
    color: var(--text-primary);
  }

  .sidebar-footer {
    padding-top: 12px;
    border-top: 1px solid var(--border-color);
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 12px;
    color: var(--text-muted);
  }

  .status-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: #4ade80;
    font-size: 12px;
    font-weight: 500;
  }
  .status-dot {
    width: 7px;
    height: 7px;
    background: #4ade80;
    border-radius: 50%;
    box-shadow: 0 0 8px #4ade80;
  }

  /* ── Main Chat Column ── */
  #main {
    flex: 1;
    display: flex;
    flex-direction: column;
    position: relative;
    overflow: hidden;
  }

  /* Top Navigation */
  header {
    height: 52px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px;
    flex-shrink: 0;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .icon-btn {
    background: transparent;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    width: 36px;
    height: 36px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    transition: background 0.15s ease;
  }
  .icon-btn:hover {
    background: var(--bg-surface);
    color: var(--text-primary);
  }

  .brand-header-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 8px;
  }

  /* ── Conversation Stream ── */
  #chat-container {
    flex: 1;
    overflow-y: auto;
    padding: 0 16px 20px 16px;
    scroll-behavior: smooth;
  }

  .chat-inner {
    max-width: 768px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 24px;
    min-height: 100%;
    padding-top: 16px;
  }

  /* Empty Welcome Screen */
  #empty-screen {
    margin: auto;
    text-align: center;
    max-width: 600px;
    padding: 40px 0;
  }

  .empty-logo {
    width: 48px;
    height: 48px;
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    margin: 0 auto 18px auto;
  }

  .empty-title {
    font-size: 24px;
    font-weight: 600;
    margin-bottom: 24px;
    color: var(--text-primary);
  }

  .suggestion-chips {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
    text-align: left;
  }

  .suggestion-chip {
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-card);
    padding: 14px 16px;
    font-size: 13.5px;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.15s ease;
    line-height: 1.4;
  }
  .suggestion-chip:hover {
    background: var(--bg-surface-hover);
    color: var(--text-primary);
    border-color: rgba(255, 255, 255, 0.2);
  }
  .suggestion-chip strong {
    display: block;
    color: var(--text-primary);
    margin-bottom: 2px;
    font-size: 13.5px;
  }

  /* Message Rows */
  .message-row {
    display: flex;
    gap: 16px;
    width: 100%;
  }

  .message-row.user {
    justify-content: flex-end;
  }

  .message-bubble {
    font-size: 15px;
    line-height: 1.6;
    word-break: break-word;
  }

  .message-row.user .message-bubble {
    background: var(--bg-surface);
    color: var(--text-primary);
    padding: 10px 18px;
    border-radius: 20px;
    max-width: 80%;
    white-space: pre-wrap;
  }

  .message-row.assistant {
    justify-content: flex-start;
  }

  .assistant-avatar {
    width: 32px;
    height: 32px;
    background: var(--accent);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    flex-shrink: 0;
    margin-top: 2px;
  }

  .assistant-body {
    flex: 1;
    min-width: 0;
    color: var(--text-primary);
  }

  /* Subtle Thinking / Step pill */
  .status-step-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--border-color);
    padding: 3px 10px;
    border-radius: var(--radius-pill);
    font-size: 12px;
    color: var(--text-muted);
    margin-bottom: 8px;
    font-family: var(--font-mono);
  }

  /* Clean Deliverable Download Card (Inline) */
  .file-card-inline {
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 12px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin: 12px 0 6px 0;
    max-width: 480px;
  }
  .file-card-inline:hover {
    border-color: rgba(255, 255, 255, 0.25);
  }
  .file-card-left {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
  }
  .file-icon {
    font-size: 24px;
    flex-shrink: 0;
  }
  .file-text-name {
    font-size: 13.5px;
    font-weight: 600;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .file-text-meta {
    font-size: 11.5px;
    color: var(--text-muted);
  }
  .download-btn-pill {
    background: rgba(255, 255, 255, 0.1);
    color: #fff;
    padding: 6px 14px;
    border-radius: var(--radius-pill);
    font-size: 12.5px;
    font-weight: 500;
    text-decoration: none;
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
    transition: all 0.15s ease;
  }
  .download-btn-pill:hover {
    background: rgba(255, 255, 255, 0.2);
  }

  /* Markdown Content Styling */
  .assistant-body p { margin-bottom: 12px; }
  .assistant-body h1, .assistant-body h2, .assistant-body h3 {
    margin: 18px 0 8px 0;
    font-weight: 600;
  }
  .assistant-body h1 { font-size: 18px; }
  .assistant-body h2 { font-size: 16px; }
  .assistant-body h3 { font-size: 14.5px; }
  .assistant-body ul, .assistant-body ol { margin-left: 20px; margin-bottom: 12px; }
  .assistant-body li { margin-bottom: 4px; }
  
  .code-block {
    background: #141414;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    margin: 12px 0;
    overflow: hidden;
  }
  .code-top {
    background: #1c1c1c;
    padding: 6px 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 11.5px;
    color: var(--text-muted);
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }
  .copy-code-btn {
    background: transparent;
    border: none;
    color: var(--text-secondary);
    font-size: 11.5px;
    cursor: pointer;
  }
  .copy-code-btn:hover { color: #fff; }
  .code-content {
    padding: 12px;
    font-family: var(--font-mono);
    font-size: 13px;
    color: #e2e8f0;
    overflow-x: auto;
    line-height: 1.5;
  }

  /* ── Bottom Input Bar (ChatGPT pill) ── */
  #input-container {
    padding: 0 16px 20px 16px;
    flex-shrink: 0;
  }

  .input-inner {
    max-width: 768px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .attached-file-badge {
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-pill);
    padding: 4px 12px;
    display: none;
    align-items: center;
    gap: 8px;
    font-size: 12.5px;
    color: var(--text-secondary);
    align-self: flex-start;
  }
  .remove-file-btn {
    cursor: pointer;
    color: var(--text-muted);
  }
  .remove-file-btn:hover { color: #f87171; }

  .input-pill-wrapper {
    background: var(--bg-input);
    border: 1px solid var(--border-color);
    border-radius: 26px;
    padding: 8px 12px;
    display: flex;
    align-items: flex-end;
    gap: 8px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
    transition: border-color 0.15s ease;
  }
  .input-pill-wrapper:focus-within {
    border-color: rgba(255, 255, 255, 0.25);
  }

  #user-textarea {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    color: #fff;
    font-family: inherit;
    font-size: 15px;
    line-height: 1.5;
    resize: none;
    max-height: 160px;
    min-height: 24px;
    padding: 6px 6px;
  }
  #user-textarea::placeholder {
    color: var(--text-muted);
  }

  .attach-btn {
    background: transparent;
    border: none;
    color: var(--text-secondary);
    width: 34px;
    height: 34px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 18px;
    flex-shrink: 0;
    transition: background 0.15s ease;
  }
  .attach-btn:hover {
    background: rgba(255, 255, 255, 0.08);
    color: #fff;
  }

  #send-btn {
    background: #fff;
    color: #000;
    width: 34px;
    height: 34px;
    border-radius: 50%;
    border: none;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 15px;
    font-weight: bold;
    flex-shrink: 0;
    transition: opacity 0.15s ease, transform 0.1s ease;
  }
  #send-btn:hover:not(:disabled) {
    transform: scale(1.05);
  }
  #send-btn:disabled {
    background: #404040;
    color: #888;
    cursor: not-allowed;
  }

  .disclaimer {
    text-align: center;
    font-size: 11.5px;
    color: var(--text-muted);
  }

  /* Drag overlay */
  #drag-box {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.8);
    backdrop-filter: blur(4px);
    border: 2px dashed rgba(255, 255, 255, 0.3);
    z-index: 999;
    display: none;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    font-weight: 500;
    color: #fff;
  }

  /* Custom Scrollbar */
  ::-webkit-scrollbar { width: 5px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.15); border-radius: 3px; }
</style>
</head>
<body>

<div id="drag-box">Drop file to attach</div>

<div id="app">

  <!-- ── Left Sidebar (History & New Chat) ── -->
  <aside id="sidebar">
    <button class="new-chat-btn" onclick="startNewChat()">
      <span>+ New chat</span>
      <span style="color: var(--text-muted); font-size: 12px;">⌘K</span>
    </button>

    <div class="sidebar-section-title">Recent Tasks</div>
    <div class="sidebar-items" id="history-list">
      <div class="chat-history-item" onclick="usePrompt('Extract the table of thickness readings from inspection_report.jpg and save it to an Excel file.')">
        📄 Scan / P&ID to Excel
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

    <div class="sidebar-footer">
      <div class="status-badge">
        <span class="status-dot"></span>
        <span>100% Air-Gapped</span>
      </div>
      <span style="font-size: 11px;">Local GPU</span>
    </div>
  </aside>

  <!-- ── Main Area ── -->
  <main id="main">
    
    <!-- Header -->
    <header>
      <div class="header-left">
        <button class="icon-btn" title="Toggle Sidebar" onclick="toggleSidebar()">☰</button>
        <span class="brand-header-title">Sovereign AI</span>
      </div>
      <button class="icon-btn" title="New Chat" onclick="startNewChat()">✏️</button>
    </header>

    <!-- Chat Messages Container -->
    <div id="chat-container">
      <div class="chat-inner" id="chat-stream">

        <!-- Welcome Hero (Empty State) -->
        <div id="empty-screen">
          <div class="empty-logo">🛡️</div>
          <div class="empty-title">What can I help you with?</div>
          
          <div class="suggestion-chips">
            <div class="suggestion-chip" onclick="usePrompt('Extract the table of thickness readings from inspection_report.jpg and save it to an Excel file.')">
              <strong>Scan / P&ID to Excel</strong>
              Extract thickness data from inspection report
            </div>
            <div class="suggestion-chip" onclick="usePrompt('What is the maximum allowable pressure according to the SOPs? Give me the exact source citation.')">
              <strong>SOP Compliance</strong>
              Query internal refinery manuals & cite SOP
            </div>
            <div class="suggestion-chip" onclick="usePrompt('Write a python script that calculates the stress on a 10 inch carbon steel pipe with 500 psi internal pressure and prints it.')">
              <strong>Engineering Calculation</strong>
              Calculate pipe wall stress in sandbox
            </div>
            <div class="suggestion-chip" onclick="usePrompt('Draft a formal internal Approval Note for Sector 4 vessel maintenance based on recent ultrasonic inspection findings.')">
              <strong>Approval Note (.docx)</strong>
              Generate branded executive approval document
            </div>
          </div>
        </div>

      </div>
    </div>

    <!-- Bottom Input Dock -->
    <div id="input-container">
      <div class="input-inner">
        <!-- Attached file badge -->
        <div id="file-badge" class="attached-file-badge">
          <span>📎</span>
          <span id="file-badge-name">scan.jpg</span>
          <span class="remove-file-btn" onclick="clearAttachment()">✕</span>
        </div>

        <div class="input-pill-wrapper">
          <input type="file" id="hidden-file" style="display:none;" 
                 accept=".jpg,.jpeg,.png,.pdf,.docx,.xlsx,.txt,.csv" onchange="fileChosen(this)">
          <button class="attach-btn" title="Attach image or file" onclick="document.getElementById('hidden-file').click()">
            📎
          </button>

          <textarea id="user-textarea" rows="1" placeholder="Message Sovereign AI..."
                    oninput="autoExpand(this)" onkeydown="onKey(event)"></textarea>

          <button id="send-btn" title="Send (Enter)" onclick="sendChat()">
            ↑
          </button>
        </div>

        <div class="disclaimer">
          Sovereign AI runs 100% on-premises. No data leaves your secure server.
        </div>
      </div>
    </div>

  </main>
</div>

<script>
  let attachedFile = null;
  let isThinking = false;

  // ── Drag & drop ──
  window.addEventListener('dragover', (e) => { e.preventDefault(); document.getElementById('drag-box').style.display = 'flex'; });
  window.addEventListener('dragleave', (e) => { e.preventDefault(); document.getElementById('drag-box').style.display = 'none'; });
  window.addEventListener('drop', async (e) => {
    e.preventDefault();
    document.getElementById('drag-box').style.display = 'none';
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      await uploadFile(e.dataTransfer.files[0]);
    }
  });

  function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('closed');
  }

  function autoExpand(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 160) + 'px';
  }

  function onKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChat();
    }
  }

  function usePrompt(text) {
    const t = document.getElementById('user-textarea');
    t.value = text;
    autoExpand(t);
    t.focus();
  }

  async function startNewChat() {
    try {
      await fetch('/reset-session', { method: 'POST' });
    } catch(e){}
    const stream = document.getElementById('chat-stream');
    stream.innerHTML = `
      <div id="empty-screen">
        <div class="empty-logo">🛡️</div>
        <div class="empty-title">What can I help you with?</div>
        <div class="suggestion-chips">
          <div class="suggestion-chip" onclick="usePrompt('Extract the table of thickness readings from inspection_report.jpg and save it to an Excel file.')">
            <strong>Scan / P&ID to Excel</strong>
            Extract thickness data from inspection report
          </div>
          <div class="suggestion-chip" onclick="usePrompt('What is the maximum allowable pressure according to the SOPs? Give me the exact source citation.')">
            <strong>SOP Compliance</strong>
            Query internal refinery manuals & cite SOP
          </div>
          <div class="suggestion-chip" onclick="usePrompt('Write a python script that calculates the stress on a 10 inch carbon steel pipe with 500 psi internal pressure and prints it.')">
            <strong>Engineering Calculation</strong>
            Calculate pipe wall stress in sandbox
          </div>
          <div class="suggestion-chip" onclick="usePrompt('Draft a formal internal Approval Note for Sector 4 vessel maintenance based on recent ultrasonic inspection findings.')">
            <strong>Approval Note (.docx)</strong>
            Generate branded executive approval document
          </div>
        </div>
      </div>
    `;
  }

  async function fileChosen(input) {
    if (input.files && input.files[0]) {
      await uploadFile(input.files[0]);
    }
    input.value = '';
  }

  async function uploadFile(file) {
    const badge = document.getElementById('file-badge');
    const nameEl = document.getElementById('file-badge-name');
    nameEl.textContent = 'Uploading ' + file.name + '...';
    badge.style.display = 'inline-flex';

    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await fetch('/upload', { method: 'POST', body: fd });
      const data = await res.json();
      attachedFile = data.filename;
      nameEl.textContent = data.filename;
    } catch (e) {
      nameEl.textContent = 'Upload failed';
    }
  }

  function clearAttachment() {
    attachedFile = null;
    document.getElementById('file-badge').style.display = 'none';
  }

  function sendChat() {
    if (isThinking) return;
    const textarea = document.getElementById('user-textarea');
    let text = textarea.value.trim();
    if (!text && !attachedFile) return;

    if (attachedFile) {
      text = text ? `${text} (File: ${attachedFile})` : `Process file: ${attachedFile}`;
    }

    textarea.value = '';
    autoExpand(textarea);
    clearAttachment();

    // Hide empty hero
    const hero = document.getElementById('empty-screen');
    if (hero) hero.remove();

    // Append User Message
    appendMessage('user', text);

    // Stream Assistant Message
    streamAssistant(text);
  }

  function appendMessage(role, text) {
    const stream = document.getElementById('chat-stream');
    const row = document.createElement('div');
    row.className = `message-row ${role}`;
    
    if (role === 'user') {
      row.innerHTML = `<div class="message-bubble">${escapeHtml(text)}</div>`;
    }
    stream.appendChild(row);
    scrollDown();
    return row;
  }

  function streamAssistant(promptText) {
    isThinking = true;
    document.getElementById('send-btn').disabled = true;

    const stream = document.getElementById('chat-stream');
    
    const row = document.createElement('div');
    row.className = 'message-row assistant';
    
    row.innerHTML = `
      <div class="assistant-avatar">🛡️</div>
      <div class="assistant-body">
        <div class="status-step-pill">Thinking...</div>
        <div class="assistant-text"></div>
      </div>
    `;
    stream.appendChild(row);
    scrollDown();

    const statusPill = row.querySelector('.status-step-pill');
    const textContainer = row.querySelector('.assistant-text');

    const es = new EventSource('/chat?message=' + encodeURIComponent(promptText));

    es.onmessage = function(e) {
      if (e.data === '[DONE]') {
        es.close();
        isThinking = false;
        document.getElementById('send-btn').disabled = false;
        if (statusPill) statusPill.remove();
        return;
      }

      try {
        const d = JSON.parse(e.data);

        // Step updates (e.g. planner, rag, vision)
        if (d.type === 'step') {
          const stepNames = {
            planner: 'Planning...',
            rag: 'Searching SOPs & Knowledge Base...',
            vision: 'Analyzing document scan / drawing...',
            coding: 'Executing Python code in sandbox...',
            reasoning: 'Reasoning & drafting...',
            verification: 'Verifying technical accuracy...',
            tools: 'Creating document file...'
          };
          if (statusPill) statusPill.textContent = stepNames[d.node] || ('Executing ' + d.node + '...');
        }

        // Final result
        if (d.type === 'result') {
          if (statusPill) statusPill.remove();
          textContainer.innerHTML = parseMarkdown(d.text);

          // Check if any deliverable was created and render a simple clean card
          if (d.files && d.files.length > 0) {
            const recent = d.files[0];
            if (d.text.includes(recent.name) || recent.modified) {
              const fileCard = document.createElement('div');
              fileCard.className = 'file-card-inline';
              let icon = '📄';
              if (recent.name.endsWith('.docx')) icon = '📝';
              if (recent.name.endsWith('.xlsx')) icon = '📊';
              if (recent.name.endsWith('.pptx')) icon = '📈';

              fileCard.innerHTML = `
                <div class="file-card-left">
                  <div class="file-icon">${icon}</div>
                  <div style="min-width:0;">
                    <div class="file-text-name">${escapeHtml(recent.name)}</div>
                    <div class="file-text-meta">${recent.size_kb} KB &middot; Generated Deliverable</div>
                  </div>
                </div>
                <a href="/download/${encodeURIComponent(recent.name)}" download class="download-btn-pill">
                  ⬇ Download
                </a>
              `;
              textContainer.appendChild(fileCard);
            }
          }
          scrollDown();
        }

        if (d.type === 'error') {
          if (statusPill) statusPill.remove();
          textContainer.innerHTML = `<span style="color:#f87171;">⚠️ ${escapeHtml(d.text)}</span>`;
          es.close();
          isThinking = false;
          document.getElementById('send-btn').disabled = false;
        }

      } catch(err){}
    };

    es.onerror = function() {
      es.close();
      if (statusPill) statusPill.remove();
      isThinking = false;
      document.getElementById('send-btn').disabled = false;
    };
  }

  function scrollDown() {
    const c = document.getElementById('chat-container');
    c.scrollTop = c.scrollHeight;
  }

  // ── Clean Markdown Parser ──
  function parseMarkdown(raw) {
    if (!raw) return '';
    let out = escapeHtml(raw);

    // Code blocks with clean copy button
    out = out.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, function(match, lang, code) {
      const id = 'c_' + Math.random().toString(36).substr(2, 8);
      return `
        <div class="code-block">
          <div class="code-top">
            <span>${lang ? lang.toUpperCase() : 'CODE'}</span>
            <button class="copy-code-btn" onclick="copySnippet('${id}')">Copy</button>
          </div>
          <pre class="code-content" id="${id}">${code}</pre>
        </div>
      `;
    });

    // Inline code
    out = out.replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.08);padding:2px 5px;border-radius:4px;font-family:var(--font-mono);font-size:13px;color:#93c5fd;">$1</code>');

    // Headers
    out = out.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    out = out.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    out = out.replace(/^# (.*$)/gim, '<h1>$1</h1>');

    // Bold & italic
    out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    out = out.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Bullet list
    out = out.replace(/^\- (.*$)/gim, '<li>$1</li>');
    out = out.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

    // Paragraph breaks
    out = out.replace(/\n\n/g, '<br><br>');

    return out;
  }

  function copySnippet(id) {
    const el = document.getElementById(id);
    if (!el) return;
    navigator.clipboard.writeText(el.innerText).then(() => {
      alert('Copied to clipboard');
    });
  }

  function escapeHtml(text) {
    return (text || '').replace(/&/g, "&amp;")
                       .replace(/</g, "&lt;")
                       .replace(/>/g, "&gt;")
                       .replace(/"/g, "&quot;")
                       .replace(/'/g, "&#039;");
  }
</script>
</body>
</html>
"""

with open(r"d:\Sovereign_AI_Workbench\static\index.html", "w", encoding="utf-8") as f:
    f.write(code)
print("Ultra-clean ChatGPT UI written!")
