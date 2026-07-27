import { useState, useRef, useEffect } from 'react';
import { askAssistant } from '../services/api';

const ACC = '#FF6B35';

export default function Assistant() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const sendMessage = async () => {
    const question = input.trim();
    if (!question || loading) return;

    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: question }]);
    setLoading(true);

    try {
      const data = await askAssistant(question);
      setMessages(prev => [...prev, { role: 'assistant', content: data.answer }]);
    } catch {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Something went wrong reaching the assistant. Please try again.',
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 20px', minHeight: 60, borderBottom: '1px solid rgba(255,255,255,0.05)', background: 'rgba(13,17,23,0.7)', backdropFilter: 'blur(12px)', flexShrink: 0 }}>
        <div>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: 18, fontWeight: 600 }}>Assistant</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>Ask about squad readiness, availability, and fatigue risk</div>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 20px 12px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {messages.length === 0 && !loading && (
          <div style={{ color: 'var(--text-muted)', fontSize: 13, margin: 'auto', textAlign: 'center', maxWidth: 340 }}>
            Ask something like &ldquo;Who&apos;s at risk of fatigue right now?&rdquo; or &ldquo;Is the squad ready for the next match?&rdquo;
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
            <div style={{
              maxWidth: '72%',
              padding: '10px 14px',
              borderRadius: 14,
              fontSize: 13,
              lineHeight: 1.5,
              whiteSpace: 'pre-wrap',
              background: m.role === 'user' ? ACC : 'rgba(255,255,255,0.05)',
              color: m.role === 'user' ? '#fff' : 'var(--text-primary)',
              border: m.role === 'user' ? 'none' : '1px solid rgba(255,255,255,0.07)',
            }}>
              {m.content}
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
            <div style={{ padding: '10px 14px', borderRadius: 14, fontSize: 13, color: 'var(--text-muted)', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.07)' }}>
              Thinking…
            </div>
          </div>
        )}

        <div ref={endRef} />
      </div>

      <div style={{ padding: '12px 20px 20px', flexShrink: 0, display: 'flex', gap: 10 }}>
        <input
          className="search-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about squad readiness…"
          disabled={loading}
          style={{
            flex: 1,
            padding: '11px 14px',
            borderRadius: 10,
            border: '1px solid rgba(255,255,255,0.1)',
            background: 'rgba(255,255,255,0.03)',
            color: 'var(--text-primary)',
            fontSize: 13,
            outline: 'none',
          }}
        />
        <button
          onClick={sendMessage}
          disabled={!input.trim() || loading}
          style={{
            padding: '0 18px',
            borderRadius: 10,
            border: 'none',
            background: (!input.trim() || loading) ? 'rgba(255,107,53,0.3)' : ACC,
            color: '#fff',
            fontSize: 13,
            fontWeight: 600,
            cursor: (!input.trim() || loading) ? 'default' : 'pointer',
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}
