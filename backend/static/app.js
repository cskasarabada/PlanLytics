// backend/static/app.js

// Grab elements
const uploadForm = document.getElementById("uploadForm");
const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadBtn");
const uploadStatus = document.getElementById("uploadStatus");
const analyzeBtn = document.getElementById("analyzeBtn");
const analysisResult = document.getElementById("analysisResult");
const aiAgentBtn = document.getElementById("aiAgentBtn");
const aiResult = document.getElementById("aiResult");

let uploadedFile = null;

function setBusy(btn, busy, busyText, idleText) {
  if (!btn) return;
  btn.disabled = !!busy;
  if (busy && busyText) btn.textContent = busyText;
  if (!busy && idleText) btn.textContent = idleText;
}

function showError(container, message) {
  container.innerHTML = `<pre style="color:#ffb4b4;background:#2a0f14;border:1px solid #5b1f25;border-radius:8px;padding:10px;">Error: ${message}</pre>`;
}

// Helper to safely parse JSON responses. If the response isn't valid JSON,
// the raw text is surfaced instead of triggering a "Unexpected token" error.
async function fetchJSON(url, options = {}) {
  const res = await fetch(url, options);
  const text = await res.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(text || res.statusText);
  }
  if (!res.ok) {
    throw new Error(data.error || res.statusText);
  }
  return data;
}

// Handle upload submit
uploadForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  if (!fileInput.files.length) {
    alert("Choose a file first");
    return;
  }

  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append("file", file);

  setBusy(uploadBtn, true, "Uploading...", "Upload");
  analyzeBtn.disabled = true;
  uploadStatus.textContent = "Uploading…";

  try {
    const data = await fetchJSON("/api/upload", { method: "POST", body: formData });

    uploadedFile = data.filename;
    uploadStatus.textContent = `Uploaded: ${uploadedFile}`;
    analyzeBtn.disabled = false;
    aiAgentBtn.disabled = false;

    // Reset preview
    analysisResult.innerHTML = `<pre>Ready to analyze: ${uploadedFile}</pre>`;
    aiResult.innerHTML = `<pre>Ready to run AI Agent on: ${uploadedFile}</pre>`;
  } catch (err) {
    uploadedFile = null;
    analyzeBtn.disabled = true;
    aiAgentBtn.disabled = true;
    showError(analysisResult, err.message || "Upload failed");
    uploadStatus.textContent = "Upload failed";
  } finally {
    setBusy(uploadBtn, false, "", "Upload");
  }
});

// Handle analyze click
analyzeBtn.addEventListener("click", async () => {
  if (!uploadedFile) {
    alert("Upload a file first");
    return;
  }

  setBusy(analyzeBtn, true, "Analyzing...", "Analyze");
  analysisResult.innerHTML = `<pre>Analyzing ${uploadedFile}…</pre>`;

  try {
    const data = await fetchJSON("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: uploadedFile })
    });

    const csvUrl = data.download_url_csv + `?t=${Date.now()}`;
    const rows = typeof data.rows === "number" ? data.rows : "—";
    let links = `<a class="btn-link" href="${csvUrl}" download>Download CSV</a>`;
    if (data.download_url_xlsx) {
      const xlsxUrl = data.download_url_xlsx + `?t=${Date.now()}`;
      links += `<a class="btn-link" href="${xlsxUrl}" download>Download Excel</a>`;
    }

    analysisResult.innerHTML = `
      <h3>Analysis complete</h3>
      <p>Rows extracted: <strong>${rows}</strong></p>
      <div>${links}</div>
    `;
  } catch (err) {
    showError(analysisResult, err.message || "Analysis failed");
  } finally {
    setBusy(analyzeBtn, false, "", "Analyze");
  }
});

// Handle AI agent analysis
aiAgentBtn.addEventListener("click", async () => {
  if (!uploadedFile) {
    alert("Upload a file first");
    return;
  }

  setBusy(aiAgentBtn, true, "Running AI...", "Run AI Agent");
  aiResult.innerHTML = `<pre>Running AI Agent on ${uploadedFile}…</pre>`;

  try {
    const data = await fetchJSON("/api/agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: uploadedFile })
    });

    aiResult.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
  } catch (err) {
    showError(aiResult, err.message || "AI Agent failed");
  } finally {
    setBusy(aiAgentBtn, false, "", "Run AI Agent");
  }
});
