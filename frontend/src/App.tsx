import React, { useState } from 'react'
import MiniChat from './MiniChat'

export default function App() {
  const [file, setFile] = useState<File | null>(null)
  const [msg, setMsg] = useState<string>('')

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault()
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    const res = await fetch('/api/upload', { method: 'POST', body: form })
    const json = await res.json()
    setMsg(`Uploaded ${json.filename} (${json.size} bytes)`)
  }

  return (
    <div style={{ maxWidth: 720, margin: '4rem auto', fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif' }}>
      <h1>ICM Automation Analyzer</h1>
      <form onSubmit={handleUpload}>
        <input type="file" onChange={e => setFile(e.target.files?.[0] || null)} />
        <button type="submit" disabled={!file} style={{ marginLeft: 12 }}>Upload</button>
      </form>
      <p>{msg}</p>
      <p><a href="/health" target="_blank" rel="noreferrer">Health check</a></p>
      <MiniChat />
    </div>
  )
}
