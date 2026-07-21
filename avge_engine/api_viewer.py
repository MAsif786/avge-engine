"""Built-in browser viewer for AVGE documents."""

from __future__ import annotations


def viewer_html() -> str:
    """Return the self-contained document browser HTML."""
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AVGE Documents</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #eef2f5;
      --panel: #ffffff;
      --ink: #1d252c;
      --muted: #64707d;
      --line: #cbd5df;
      --accent: #1b7f8c;
      --accent-dark: #145f69;
      --warn: #9f5b00;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
    }
    .app {
      display: grid;
      grid-template-columns: minmax(320px, 420px) 1fr;
      min-height: 100vh;
    }
    aside {
      border-right: 1px solid var(--line);
      background: var(--panel);
      display: flex;
      flex-direction: column;
      min-width: 0;
    }
    header {
      padding: 16px;
      border-bottom: 1px solid var(--line);
      display: grid;
      gap: 12px;
    }
    h1 {
      font-size: 18px;
      margin: 0;
      letter-spacing: 0;
    }
    .toolbar {
      display: grid;
      grid-template-columns: 1fr 118px 86px;
      gap: 8px;
    }
    input, select, button {
      height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      font: inherit;
      padding: 0 10px;
      min-width: 0;
    }
    button {
      cursor: pointer;
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
      font-weight: 600;
    }
    button.secondary {
      background: #fff;
      border-color: var(--line);
      color: var(--ink);
    }
    button:hover { background: var(--accent-dark); }
    button.secondary:hover { background: #f7fafc; }
    .docs {
      overflow: auto;
      padding: 8px;
    }
    .doc {
      width: 100%;
      border: 1px solid transparent;
      border-radius: 6px;
      padding: 10px;
      background: transparent;
      color: var(--ink);
      text-align: left;
      display: grid;
      gap: 4px;
    }
    .doc:hover { background: #f4f8fa; }
    .doc.active {
      border-color: #84c5ce;
      background: #e9f7f9;
    }
    .doc-title {
      font-weight: 700;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .doc-meta {
      color: var(--muted);
      font-size: 12px;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    main {
      display: grid;
      grid-template-rows: auto 1fr;
      min-width: 0;
    }
    .preview-bar {
      min-height: 64px;
      border-bottom: 1px solid var(--line);
      background: #fbfcfd;
      padding: 12px 16px;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      align-items: center;
    }
    .selected-name {
      font-size: 16px;
      font-weight: 700;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .selected-id {
      color: var(--muted);
      font-size: 12px;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }
    .actions {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    label.toggle {
      display: inline-flex;
      gap: 8px;
      align-items: center;
      color: var(--muted);
      white-space: nowrap;
    }
    label.toggle input { width: 16px; height: 16px; }
    .canvas-wrap {
      overflow: auto;
      padding: 18px;
      background:
        linear-gradient(45deg, #dfe6ec 25%, transparent 25%),
        linear-gradient(-45deg, #dfe6ec 25%, transparent 25%),
        linear-gradient(45deg, transparent 75%, #dfe6ec 75%),
        linear-gradient(-45deg, transparent 75%, #dfe6ec 75%);
      background-size: 28px 28px;
      background-position: 0 0, 0 14px, 14px -14px, -14px 0;
    }
    .frame {
      width: min(100%, 1180px);
      min-height: calc(100vh - 104px);
      margin: 0 auto;
      display: grid;
      place-items: center;
    }
    object {
      max-width: 100%;
      max-height: calc(100vh - 140px);
      background: #fff;
      box-shadow: 0 12px 32px rgba(24, 36, 48, 0.22);
    }
    .empty, .status {
      color: var(--muted);
      background: rgba(255,255,255,0.9);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }
    .error { color: var(--warn); }
    @media (max-width: 820px) {
      .app { grid-template-columns: 1fr; }
      aside { max-height: 45vh; border-right: 0; border-bottom: 1px solid var(--line); }
      .preview-bar { grid-template-columns: 1fr; }
      .actions { justify-content: flex-start; }
      .toolbar { grid-template-columns: 1fr 1fr; }
      .toolbar input { grid-column: 1 / -1; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside>
      <header>
        <h1>AVGE Documents</h1>
        <div class="toolbar">
          <input id="search" type="search" placeholder="Search documents">
          <select id="sort">
            <option value="updated">Updated</option>
            <option value="name">Name</option>
            <option value="regions">Regions</option>
            <option value="version">Version</option>
          </select>
          <select id="order">
            <option value="desc">Desc</option>
            <option value="asc">Asc</option>
          </select>
        </div>
      </header>
      <div id="docs" class="docs"><div class="status">Loading documents...</div></div>
    </aside>
    <main>
      <div class="preview-bar">
        <div>
          <div id="selectedName" class="selected-name">No document selected</div>
          <div id="selectedId" class="selected-id"></div>
        </div>
        <div class="actions">
          <label class="toggle"><input id="live" type="checkbox" checked> Live</label>
          <button class="secondary" id="refresh">Refresh</button>
          <button id="svg">SVG</button>
          <button id="png">PNG</button>
          <button id="jpg">JPG</button>
          <button id="pdf">PDF</button>
        </div>
      </div>
      <div class="canvas-wrap">
        <div id="frame" class="frame"><div class="empty">Select a document to preview.</div></div>
      </div>
    </main>
  </div>
  <script>
    const state = { docs: [], selected: null, timer: null, version: null };
    const $ = (id) => document.getElementById(id);

    function fmtDate(value) {
      if (!value) return "unknown";
      const d = new Date(value);
      return Number.isNaN(d.getTime()) ? value : d.toLocaleString();
    }

    function filteredDocs() {
      const q = $("search").value.trim().toLowerCase();
      const sort = $("sort").value;
      const order = $("order").value === "asc" ? 1 : -1;
      return state.docs
        .filter((d) => `${d.name || ""} ${d.id}`.toLowerCase().includes(q))
        .sort((a, b) => {
          let av = sort === "regions" ? a.region_count : a[sort];
          let bv = sort === "regions" ? b.region_count : b[sort];
          if (sort === "updated") {
            av = Date.parse(av || "") || 0;
            bv = Date.parse(bv || "") || 0;
          }
          if (typeof av === "string") av = av.toLowerCase();
          if (typeof bv === "string") bv = bv.toLowerCase();
          return av > bv ? order : av < bv ? -order : 0;
        });
    }

    function renderList() {
      const docs = filteredDocs();
      $("docs").innerHTML = "";
      if (!docs.length) {
        $("docs").innerHTML = '<div class="status">No matching documents.</div>';
        return;
      }
      for (const doc of docs) {
        const btn = document.createElement("button");
        btn.className = "doc" + (state.selected === doc.id ? " active" : "");
        btn.innerHTML = `
          <div class="doc-title">${escapeHtml(doc.name || "(unnamed)")}</div>
          <div class="doc-meta">
            <span>${escapeHtml(doc.id)}</span>
            <span>${doc.region_count} regions</span>
            <span>v${doc.version}</span>
          </div>
          <div class="doc-meta">${escapeHtml(fmtDate(doc.updated))}</div>`;
        btn.onclick = () => selectDoc(doc.id);
        $("docs").appendChild(btn);
      }
    }

    function escapeHtml(text) {
      return String(text).replace(/[&<>"']/g, (m) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
      }[m]));
    }

    async function loadDocs() {
      const params = new URLSearchParams({
        search: $("search").value,
        sort: $("sort").value,
        order: $("order").value
      });
      const res = await fetch(`/viewer/documents?${params}`);
      const data = await res.json();
      state.docs = data.documents || [];
      renderList();
      if (!state.selected && state.docs.length) selectDoc(state.docs[0].id);
    }

    function selectDoc(id) {
      state.selected = id;
      const doc = state.docs.find((d) => d.id === id);
      state.version = doc ? doc.version : null;
      $("selectedName").textContent = doc ? (doc.name || "(unnamed)") : "No document selected";
      $("selectedId").textContent = doc ? `${doc.id} - ${doc.region_count} regions - v${doc.version}` : "";
      renderList();
      refreshPreview(true);
    }

    async function refreshPreview(force = false) {
      if (!state.selected) return;
      try {
        if (!force) {
          const res = await fetch(`/documents/${state.selected}`);
          if (res.ok) {
            const data = await res.json();
            const version = data.document && data.document.version;
            if (version === state.version) return;
            state.version = version;
          }
        }
        const stamp = Date.now();
        $("frame").innerHTML = `<object data="/preview/${state.selected}.svg?t=${stamp}" type="image/svg+xml"></object>`;
      } catch (err) {
        $("frame").innerHTML = `<div class="status error">${escapeHtml(err.message)}</div>`;
      }
    }

    function download(fmt) {
      if (!state.selected) return;
      window.location.href = `/download/${state.selected}.${fmt}`;
    }

    function configureLive() {
      if (state.timer) clearInterval(state.timer);
      state.timer = null;
      if ($("live").checked) {
        state.timer = setInterval(() => refreshPreview(false), 1500);
      }
    }

    $("search").addEventListener("input", () => { renderList(); });
    $("sort").addEventListener("change", loadDocs);
    $("order").addEventListener("change", loadDocs);
    $("refresh").onclick = () => { loadDocs(); refreshPreview(true); };
    $("live").onchange = configureLive;
    $("svg").onclick = () => download("svg");
    $("png").onclick = () => download("png");
    $("jpg").onclick = () => download("jpg");
    $("pdf").onclick = () => download("pdf");

    loadDocs();
    configureLive();
  </script>
</body>
</html>
"""
