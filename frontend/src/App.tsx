
import React, { useState } from 'react'

export default function App() {
  const [file, setFile] = useState<File | null>(null)
  const [message, setMessage] = useState<string>('')

  const upload = async () => {
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    const res = await fetch('/api/upload', { method: 'POST', body: form })
    const json = await res.json()
    setMessage(`Uploaded ${json.filename} (${json.size} bytes)`)
  }

  return (
    <div style={{ maxWidth: 720, margin: '4rem auto', fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif' }}>
      <h1>PlanLytics</h1>
      <p>Upload a file (PDF, DOCX, TXT, CSV, XLSX up to 100MB) to test the API.</p>
      <input type="file" onChange={e => setFile(e.target.files?.[0] || null)} />
      <button onClick={upload} disabled={!file} style={{ marginLeft: 12 }}>Upload</button>
      <p>{message}</p>
      <p><a href="/health" target="_blank" rel="noreferrer">Health check</a></p>
    </div>
  )
}
