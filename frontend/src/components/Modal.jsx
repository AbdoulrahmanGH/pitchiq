import { useEffect, useState } from 'react';

// Generic animated modal: fades/scales in on open, animates back out on close
// rather than unmounting instantly, and closes on Escape or backdrop click.
export default function Modal({ open, onClose, children, maxWidth = 480 }) {
  const [rendered, setRendered] = useState(open);
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (open) {
      setRendered(true);
      const raf = requestAnimationFrame(() => setShow(true));
      return () => cancelAnimationFrame(raf);
    }
    setShow(false);
    const timeout = setTimeout(() => setRendered(false), 220);
    return () => clearTimeout(timeout);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!rendered) return null;

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 100,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 20,
        background: show ? 'rgba(0,0,0,0.6)' : 'rgba(0,0,0,0)',
        backdropFilter: show ? 'blur(3px)' : 'blur(0px)',
        transition: 'background 0.2s ease, backdrop-filter 0.2s ease',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth, width: '100%', maxHeight: '86vh', overflow: 'auto',
          background: 'linear-gradient(145deg, var(--surface2) 0%, var(--bg-surface) 100%)',
          border: '1px solid rgba(255,255,255,0.08)', borderRadius: 18,
          boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
          opacity: show ? 1 : 0,
          transform: show ? 'scale(1) translateY(0)' : 'scale(0.96) translateY(8px)',
          transition: 'opacity 0.2s ease, transform 0.24s cubic-bezier(0.16,1,0.3,1)',
        }}
      >
        {children}
      </div>
    </div>
  );
}

export function ModalCloseButton({ onClick }) {
  const [hov, setHov] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      aria-label="Close"
      style={{
        width: 28, height: 28, borderRadius: 8, flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: hov ? 'rgba(255,255,255,0.08)' : 'transparent',
        border: 'none', color: 'var(--text-secondary)', cursor: 'pointer',
        transition: 'background 0.15s ease',
      }}
    >
      <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
        <path d="M1.5 1.5L11.5 11.5M11.5 1.5L1.5 11.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      </svg>
    </button>
  );
}
