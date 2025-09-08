import React, { useState } from 'react'

export default function MiniChat() {
  const [messages, setMessages] = useState<{ sender: string; text: string }[]>([])
  const [input, setInput] = useState('')
  const [disabled, setDisabled] = useState(false)

  async function send() {
    const question = input.trim()
    if (!question) return
    setMessages(m => [...m, { sender: 'You', text: question }])
    setInput('')
    try {
      const res = await fetch('/api/homechat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
      if (res.status === 429) {
        const data = await res.json()
        setMessages(m => [...m, { sender: 'System', text: data.detail || 'Limit reached' }])
        setDisabled(true)
        return
      }
      const data = await res.json()
      setMessages(m => [...m, { sender: 'Bot', text: data.answer }])
      if (data.remaining <= 0) setDisabled(true)
    } catch (err) {
      setMessages(m => [...m, { sender: 'System', text: 'Error connecting to server' }])
    }
  }

  return (
    <div style={{ border: '1px solid #ccc', padding: 16, marginTop: 24 }}>
      <h3>Mini Chat</h3>
      <div style={{ minHeight: 80 }}>
        {messages.map((m, i) => (
          <div key={i}>
            <strong>{m.sender}:</strong> {m.text}
          </div>
        ))}
      </div>
      <input
        value={input}
        onChange={e => setInput(e.target.value)}
        disabled={disabled}
        style={{ marginRight: 8 }}
      />
      <button onClick={send} disabled={disabled || !input.trim()}>
        Send
      </button>
    </div>
  )
}
