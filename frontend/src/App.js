import React, { useState } from "react";
import axios from "axios";

function App() {
  const [file, setFile] = useState(null);
  const [template, setTemplate] = useState("master");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("template", template);

    try {
      setLoading(true);
      const res = await axios.post("http://localhost:8080/analyze", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(res.data);
    } catch (err) {
      setResult({ error: err.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 800, margin: "2rem auto", fontFamily: "Arial" }}>
      <h1>ICM Automation Analyzer</h1>
      <form onSubmit={handleUpload}>
        <input
          type="file"
          onChange={(e) => setFile(e.target.files[0])}
          required
        />
        <br />
        <label>Template: </label>
        <select
          value={template}
          onChange={(e) => setTemplate(e.target.value)}
        >
          <option value="master">Master Analysis</option>
          <option value="automation_framework">Automation Framework</option>
          <option value="vendor_checklist">Vendor Checklist</option>
          <option value="side_by_side">Side-by-Side Mapping</option>
          <option value="side_by_side_vendor_compare">Oracle vs SF Compare</option>
        </select>
        <br />
        <button type="submit" disabled={loading}>
          {loading ? "Analyzing..." : "Upload & Analyze"}
        </button>
      </form>

      {result && (
        <div style={{ marginTop: "2rem" }}>
          <h2>Result</h2>
          <pre style={{ background: "#f5f5f5", padding: "1rem" }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export default App;
