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
    html, body {
      height: 100%;
      overflow: hidden;
    }
    body {
      margin: 0;
      font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
    }
    .app {
      display: grid;
      grid-template-columns: minmax(320px, 420px) 1fr;
      height: 100vh;
      overflow: hidden;
    }
    aside {
      border-right: 1px solid var(--line);
      background: var(--panel);
      display: flex;
      flex-direction: column;
      min-width: 0;
      min-height: 0;
      overflow: hidden;
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
    button.danger {
      background: #b43d35;
      border-color: #b43d35;
      color: #fff;
    }
    button:hover { background: var(--accent-dark); }
    button.secondary:hover { background: #f7fafc; }
    button.danger:hover { background: #8f2f29; }
    .docs {
      flex: 1;
      min-height: 0;
      overflow: auto;
      padding: 8px;
    }
    .doc {
      width: 100%;
      height: auto;
      min-height: 70px;
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
      min-height: 0;
      overflow: hidden;
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
    .version-select {
      min-width: 190px;
      max-width: 260px;
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
      min-height: 0;
      overflow: hidden;
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
      aside { height: 45vh; border-right: 0; border-bottom: 1px solid var(--line); }
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
          <select id="versionSelect" class="version-select" disabled>
            <option value="current">Current</option>
          </select>
          <label class="toggle"><input id="live" type="checkbox" checked> Live</label>
          <button class="secondary" id="refresh">Refresh</button>
          <button id="svg">SVG</button>
          <button id="png">PNG</button>
          <button id="jpg">JPG</button>
          <button id="pdf">PDF</button>
          <button class="danger" id="deleteDoc">Delete</button>
        </div>
      </div>
      <div class="canvas-wrap">
        <div id="frame" class="frame"><div class="empty">Select a document to preview.</div></div>
      </div>
    </main>
  </div>
  <script>
    const state = {
      docs: [],
      selected: null,
      timer: null,
      version: null,
      versions: [],
      selectedVersion: "current"
    };
    const $ = (id) => document.getElementById(id);

    function docIdFromRoute() {
      const parts = window.location.pathname.split("/").filter(Boolean);
      if (parts[0] === "viewer" && parts[1]) return decodeURIComponent(parts[1]);
      return new URLSearchParams(window.location.search).get("doc");
    }

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
        const name = docName(doc);
        const btn = document.createElement("button");
        btn.className = "doc" + (state.selected === doc.id ? " active" : "");
        btn.innerHTML = `
          <div class="doc-title">${escapeHtml(name)}</div>
          <div class="doc-meta">
            <span>ID ${escapeHtml(doc.id)}</span>
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

    function docName(doc) {
      const name = String((doc && doc.name) || "").trim();
      return name || "Untitled document";
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
      if (!state.selected && state.docs.length) {
        const routed = docIdFromRoute();
        const target = routed && state.docs.some((doc) => doc.id === routed) ? routed : state.docs[0].id;
        selectDoc(target, false);
      }
    }

    function updateRoute(id) {
      const nextPath = `/viewer/${encodeURIComponent(id)}`;
      if (window.location.pathname !== nextPath) {
        history.pushState({ documentId: id }, "", nextPath);
      }
    }

    function selectDoc(id, pushRoute = true) {
      state.selected = id;
      const doc = state.docs.find((d) => d.id === id);
      state.version = doc ? doc.version : null;
      state.versions = [];
      state.selectedVersion = "current";
      $("selectedName").textContent = doc ? docName(doc) : "No document selected";
      $("selectedId").textContent = doc ? `${doc.id} - ${doc.region_count} regions - v${doc.version}` : "";
      renderVersions();
      if (pushRoute) updateRoute(id);
      renderList();
      loadVersions().then(() => refreshPreview(true));
    }

    function renderVersions() {
      const select = $("versionSelect");
      select.innerHTML = "";
      const versions = state.versions.length ? state.versions : [{ id: "current", label: "Current" }];
      for (const version of versions) {
        const option = document.createElement("option");
        option.value = version.id;
        option.textContent = version.label || version.name || version.id;
        select.appendChild(option);
      }
      select.disabled = !state.selected;
      select.value = versions.some((v) => v.id === state.selectedVersion) ? state.selectedVersion : "current";
      state.selectedVersion = select.value;
    }

    async function loadVersions() {
      if (!state.selected) return;
      try {
        const res = await fetch(`/viewer/${state.selected}/versions`);
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        state.versions = data.versions || [];
      } catch (err) {
        state.versions = [{ id: "current", label: `Current - ${err.message}` }];
      }
      renderVersions();
    }

    function previewPath() {
      if (!state.selected) return "";
      if (state.selectedVersion && state.selectedVersion !== "current") {
        return `/preview/${state.selected}/versions/${encodeURIComponent(state.selectedVersion)}.svg`;
      }
      return `/preview/${state.selected}.svg`;
    }

    async function deleteSelectedDocument() {
      if (!state.selected) return;
      const doc = selectedDoc();
      const label = `${docName(doc)} (${doc.id})`;
      if (!confirm(`Delete document ${label}? This cannot be undone.`)) return;

      const res = await fetch("/tools/delete_document", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: [state.selected], confirm: true })
      });
      if (!res.ok) {
        $("frame").innerHTML = `<div class="status error">${escapeHtml(await res.text())}</div>`;
        return;
      }

      const deleted = state.selected;
      state.selected = null;
      state.version = null;
      state.versions = [];
      state.selectedVersion = "current";
      $("selectedName").textContent = "No document selected";
      $("selectedId").textContent = "";
      renderVersions();
      $("frame").innerHTML = `<div class="empty">Deleted ${escapeHtml(deleted)}.</div>`;
      history.pushState({}, "", "/viewer");
      await loadDocs();
    }

    async function refreshPreview(force = false) {
      if (!state.selected) return;
      try {
        if (state.selectedVersion !== "current") {
          if (!force) return;
          const stamp = Date.now();
          $("frame").innerHTML = `<object data="${previewPath()}?t=${stamp}" type="image/svg+xml"></object>`;
          return;
        }
        if (!force) {
          const res = await fetch(`/documents/${state.selected}`);
          if (res.ok) {
            const data = await res.json();
            const version = data.document && data.document.version;
            if (version === state.version) return;
            state.version = version;
            await loadVersions();
          }
        }
        const stamp = Date.now();
        $("frame").innerHTML = `<object data="${previewPath()}?t=${stamp}" type="image/svg+xml"></object>`;
      } catch (err) {
        $("frame").innerHTML = `<div class="status error">${escapeHtml(err.message)}</div>`;
      }
    }

    function selectedDoc() {
      return state.docs.find((d) => d.id === state.selected) || { id: state.selected, name: state.selected };
    }

    function fileBaseName() {
      const doc = selectedDoc();
      let base = String(doc.name || doc.id || "avge-document");
      if (state.selectedVersion && state.selectedVersion !== "current") {
        base += `-${state.selectedVersion}`;
      }
      return base
        .trim()
        .replace(/[^A-Za-z0-9._-]+/g, "-")
        .replace(/^[.-]+|[.-]+$/g, "")
        .slice(0, 80) || "avge-document";
    }

    function saveBlob(blob, filename) {
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    async function fetchSvgText() {
      if (!state.selected) throw new Error("No document selected");
      const params = new URLSearchParams({ t: Date.now() });
      const res = await fetch(`${previewPath()}?${params}`);
      if (!res.ok) throw new Error(await res.text());
      return await res.text();
    }

    function blobToDataUrl(blob) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(reader.error || new Error("Image read failed"));
        reader.readAsDataURL(blob);
      });
    }

    async function fetchImageForRasterExport(href) {
      try {
        const direct = await fetch(href, { mode: "cors", credentials: "omit" });
        if (direct.ok) return await direct.blob();
      } catch (err) {
        // Fall back to same-origin proxy below for hosts that block CORS.
      }

      const proxied = await fetch(`/viewer/image-proxy?url=${encodeURIComponent(href)}`);
      if (!proxied.ok) {
        throw new Error(await proxied.text());
      }
      return await proxied.blob();
    }

    async function inlineSvgImagesInBrowser(svgText) {
      const parser = new DOMParser();
      const doc = parser.parseFromString(svgText, "image/svg+xml");
      const parseError = doc.querySelector("parsererror");
      if (parseError) throw new Error("SVG parse failed before raster export");

      const imageNodes = Array.from(doc.querySelectorAll("image"));
      for (const image of imageNodes) {
        const href = image.getAttribute("href") || image.getAttribute("xlink:href");
        if (!href || href.startsWith("data:") || href.startsWith("blob:")) continue;

        const dataUrl = await blobToDataUrl(await fetchImageForRasterExport(href));
        image.setAttribute("href", dataUrl);
        image.setAttribute("xlink:href", dataUrl);
      }

      return new XMLSerializer().serializeToString(doc);
    }

    function svgSize(svgText) {
      const doc = new DOMParser().parseFromString(svgText, "image/svg+xml");
      const svg = doc.documentElement;
      const viewBox = (svg.getAttribute("viewBox") || "").trim().split(/[ ,]+/).map(Number);
      if (viewBox.length === 4 && viewBox.every(Number.isFinite)) {
        return { width: Math.max(1, Math.round(viewBox[2])), height: Math.max(1, Math.round(viewBox[3])) };
      }
      const width = parseFloat(svg.getAttribute("width")) || 1000;
      const height = parseFloat(svg.getAttribute("height")) || 1000;
      return { width: Math.max(1, Math.round(width)), height: Math.max(1, Math.round(height)) };
    }

    async function rasterizeSvg(svgText, background = "#ffffff") {
      const { width, height } = svgSize(svgText);
      const blob = new Blob([svgText], { type: "image/svg+xml" });
      const url = URL.createObjectURL(blob);
      try {
        const img = new Image();
        img.decoding = "async";
        const loaded = new Promise((resolve, reject) => {
          img.onload = resolve;
          img.onerror = () => reject(new Error("Browser could not rasterize SVG"));
        });
        img.src = url;
        await loaded;

        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        ctx.fillStyle = background;
        ctx.fillRect(0, 0, width, height);
        ctx.drawImage(img, 0, 0, width, height);
        return canvas;
      } finally {
        URL.revokeObjectURL(url);
      }
    }

    function canvasToBlob(canvas, type, quality) {
      return new Promise((resolve, reject) => {
        canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error("Canvas export failed")), type, quality);
      });
    }

    async function download(fmt) {
      if (!state.selected) return;
      try {
        let svgText = await fetchSvgText();
        const name = fileBaseName();
        if (fmt === "svg") {
          saveBlob(new Blob([svgText], { type: "image/svg+xml" }), `${name}.svg`);
          return;
        }
        svgText = await inlineSvgImagesInBrowser(svgText);
        const canvas = await rasterizeSvg(svgText);
        if (fmt === "png") {
          saveBlob(await canvasToBlob(canvas, "image/png"), `${name}.png`);
        } else if (fmt === "jpg") {
          saveBlob(await canvasToBlob(canvas, "image/jpeg", 0.92), `${name}.jpg`);
        } else if (fmt === "pdf") {
          const jpg = await canvasToBlob(canvas, "image/jpeg", 0.92);
          const pdf = await imageBlobToPdf(jpg, canvas.width, canvas.height);
          saveBlob(pdf, `${name}.pdf`);
        }
      } catch (err) {
        $("frame").innerHTML = `<div class="status error">${escapeHtml(err.message)}</div>`;
      }
    }

    async function imageBlobToPdf(imageBlob, width, height) {
      const imageBytes = new Uint8Array(await imageBlob.arrayBuffer());
      const encoder = new TextEncoder();
      const content = `q ${width} 0 0 ${height} 0 0 cm /Im0 Do Q`;
      const objects = [
        [`1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n`],
        [`2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n`],
        [`3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${width} ${height}] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>\nendobj\n`],
        [
          `4 0 obj\n<< /Type /XObject /Subtype /Image /Width ${width} /Height ${height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${imageBytes.length} >>\nstream\n`,
          imageBytes,
          `\nendstream\nendobj\n`
        ],
        [`5 0 obj\n<< /Length ${content.length} >>\nstream\n${content}\nendstream\nendobj\n`]
      ];
      const parts = [encoder.encode(`%PDF-1.4
`)];
      const offsets = [0];
      let length = parts[0].length;
      for (const obj of objects) {
        offsets.push(length);
        for (const part of obj) {
          const bytes = typeof part === "string" ? encoder.encode(part) : part;
          parts.push(bytes);
          length += bytes.length;
        }
      }
      const xrefOffset = length;
      let xref = `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
      for (const offset of offsets.slice(1)) {
        xref += `${String(offset).padStart(10, "0")} 00000 n \n`;
      }
      xref += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`;
      parts.push(encoder.encode(xref));
      return new Blob(parts, { type: "application/pdf" });
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
    $("versionSelect").addEventListener("change", () => {
      state.selectedVersion = $("versionSelect").value;
      refreshPreview(true);
    });
    $("refresh").onclick = async () => { await loadDocs(); await loadVersions(); refreshPreview(true); };
    $("live").onchange = configureLive;
    $("svg").onclick = () => download("svg");
    $("png").onclick = () => download("png");
    $("jpg").onclick = () => download("jpg");
    $("pdf").onclick = () => download("pdf");
    $("deleteDoc").onclick = deleteSelectedDocument;
    window.addEventListener("popstate", () => {
      const routed = docIdFromRoute();
      if (routed && state.docs.some((doc) => doc.id === routed)) {
        selectDoc(routed, false);
      }
    });

    loadDocs();
    configureLive();
  </script>
</body>
</html>
"""
