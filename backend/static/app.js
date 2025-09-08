// backend/static/app.js
let uploadedFile = null;

const $ = (sel) => document.querySelector(sel);
const statusEl = $("#uploadStatus");
const resultEl = $("#analysisResult");
const analyzeBtn = $("#analyzeBtn");

// Parse response as JSON if possible, otherwise return raw text
async function parseMaybeJSON(res) {
  const text = await res.text();
  try { return { data: JSON.parse(text), raw: text }; }
  catch { return { data: null, raw: text }; }
}

function showError(msg) {
  resultEl.innerHTML =
    `<pre style="background:#3a1f20;border:1px solid #6e2c2f;color:#ffb4b0;">Error: ${msg}</pre>`;
}

function showInfo(msg) {
  resultEl.innerHTML = `<pre>${msg}</pre>`;
}

// ---- Upload ----
$("#uploadForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const file = $("#fileInput").files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);

    const res = await fetch("/api/upload", { method: "POST", body: fd });
    const { data, raw } = await parseMaybeJSON(res);
    if (!res.ok) throw new Error((data && data.error) || raw || res.statusText);

    uploadedFile = data.filename;
    statusEl.textContent = `Uploaded: ${uploadedFile}`;
    analyzeBtn.disabled = false;
    showInfo("Ready to analyze.");
  } catch (err) {
    analyzeBtn.disabled = true;
    showError(err.message || String(err));
  }
});

// ---- Analyze ----
analyzeBtn.addEventListener("click", async () => {
  if (!uploadedFile) return;
  try {
    showInfo("Analyzing…");
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify({ filename: uploadedFile })
    });
    const { data, raw } = await parseMaybeJSON(res);
    if (!res.ok) throw new Error((data && data.error) || raw || res.statusText);

    const { rows, download_url_csv, download_url_xlsx } = data;
    resultEl.innerHTML = `
      <pre>Analysis complete. Rows: ${rows}</pre>
      <p>
        <a class="btn-link" href="${download_url_csv}">Download CSV</a>
        <a class="btn-link" href="${download_url_xlsx}">Download Excel</a>
      </p>`;
  } catch (err) {
    showError(err.message || String(err));
  }
});
