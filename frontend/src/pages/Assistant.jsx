import { useState, useRef, useEffect } from 'react';
// Deep import, not the package root: lottie-react's package.json "browser"
// field points at its UMD build, which Vite's dep pre-bundler wraps as
// `export default require_index_umd()` -- that hands back the whole CJS
// exports object (default/useLottie/__esModule) instead of unwrapping to
// the Lottie component itself, so `import Lottie from 'lottie-react'`
// silently resolves to an object and React throws "invalid element type".
// The ESM build doesn't have this problem.
import Lottie from 'lottie-react/build/index.es.js';
import { askAssistant } from '../services/api';
import robotAnimation from '../assets/robot-assistant.json';

const ACC = '#FF5A1F';

const PROMPT_CHIPS = [
  'Rank Barcelona players by Xg this season',
  'Show me all available midfielders',
];

// Reveals assistant replies character-by-character (ChatGPT/Claude-style)
// instead of pasting the full response in on one render. Self-contained --
// the reveal state lives here, keyed to this component instance, so a
// message that has already finished animating won't restart just because
// the parent re-rendered (new messages appended, etc. don't remount it,
// since Assistant.jsx keys message components by stable index).
function TypewriterText({ text, speedMs = 16, charsPerTick = 2 }) {
  const [count, setCount] = useState(0);
  const nodeRef = useRef(null);
  const done = count >= text.length;

  useEffect(() => {
    if (done) return;
    const id = setTimeout(() => setCount(c => Math.min(text.length, c + charsPerTick)), speedMs);
    return () => clearTimeout(id);
  }, [count, done, text, speedMs, charsPerTick]);

  useEffect(() => {
    nodeRef.current?.scrollIntoView({ block: 'nearest' });
  }, [count]);

  return (
    <span ref={nodeRef}>
      {text.slice(0, count)}
      {!done && (
        <span style={{
          display: 'inline-block', width: 2, height: '1em', marginLeft: 1,
          background: ACC, verticalAlign: 'text-bottom',
          animation: 'assistant-caret 0.8s step-end infinite',
        }} />
      )}
    </span>
  );
}

function WelcomeScreen({ onPick }) {
  return (
    <div style={{ margin: 'auto', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20, maxWidth: 560, padding: '0 20px', textAlign: 'center' }}>
      <div style={{ width: 128, height: 128 }}>
        <Lottie animationData={robotAnimation} loop autoplay />
      </div>
      <div style={{ fontSize: 13, color: 'var(--text-secondary)', maxWidth: 380 }}>
        I'm here to help with squad availability and fatigue decisions.
      </div>
      <div style={{ fontFamily: 'Space Grotesk', fontSize: 26, fontWeight: 700, color: 'var(--text-primary)' }}>
        Squad Intelligence Assistant
      </div>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
        {PROMPT_CHIPS.map(q => (
          <button
            key={q}
            onClick={() => onPick(q)}
            style={{
              background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.09)',
              borderRadius: 10, padding: '12px 16px', fontSize: 12.5, color: 'var(--text-secondary)',
              maxWidth: 220, cursor: 'pointer', textAlign: 'left', lineHeight: 1.4,
              transition: 'background 0.15s, border-color 0.15s, color 0.15s',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,90,31,0.08)'; e.currentTarget.style.borderColor = 'rgba(255,90,31,0.25)'; e.currentTarget.style.color = 'var(--text-primary)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.09)'; e.currentTarget.style.color = 'var(--text-secondary)'; }}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function Assistant() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const sendMessage = async (overrideText) => {
    const question = (overrideText ?? input).trim();
    if (!question || loading) return;

    // Messages always alternate user/assistant, so the last message (if
    // any) before this new one is the previous assistant reply, and the
    // one before that is the question it answered.
    const previousAnswer = messages.length > 0 ? messages[messages.length - 1].content : undefined;
    const previousQuestion = messages.length > 1 ? messages[messages.length - 2].content : undefined;

    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: question }]);
    setLoading(true);

    try {
      const data = await askAssistant(question, previousQuestion, previousAnswer);
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
      <style>{`@keyframes assistant-caret { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }`}</style>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 20px', minHeight: 60, borderBottom: '1px solid rgba(255,255,255,0.05)', background: 'rgba(13,17,23,0.7)', backdropFilter: 'blur(12px)', flexShrink: 0 }}>
        <div>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: 18, fontWeight: 600 }}>Assistant</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>Ask about squad readiness, availability, and fatigue risk</div>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 20px 12px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {messages.length === 0 && !loading && (
          <WelcomeScreen onPick={(q) => sendMessage(q)} />
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
              {m.role === 'assistant' ? <TypewriterText text={m.content} /> : m.content}
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
          onClick={() => sendMessage()}
          disabled={!input.trim() || loading}
          style={{
            padding: '0 18px',
            borderRadius: 10,
            border: 'none',
            background: (!input.trim() || loading) ? 'rgba(255,90,31,0.3)' : ACC,
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
