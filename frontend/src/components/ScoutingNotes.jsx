import { useState, useEffect } from 'react';
import { useAuth } from '../services/AuthProvider';
import { getScoutingNotes, postScoutingNote } from '../services/api';
import { SCOUTING_RATING_LABELS } from '../constants';

const ACC = '#FF6B35';

function RatingPicker({ value, onChange }) {
  return (
    <div style={{ display: 'flex', gap: 6 }}>
      {[1, 2, 3, 4, 5].map(n => (
        <button
          key={n}
          type="button"
          onClick={() => onChange(n)}
          style={{
            width: 28, height: 28, borderRadius: 7, border: '1px solid rgba(255,255,255,0.1)',
            background: value === n ? ACC : 'rgba(255,255,255,0.04)',
            color: value === n ? '#1a0f08' : 'var(--text-secondary)',
            fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: 12,
            cursor: 'pointer', transition: 'background 0.15s, color 0.15s',
          }}
        >
          {n}
        </button>
      ))}
    </div>
  );
}

function RatingScaleLegend() {
  return (
    <div style={{ fontSize: 10, color: 'var(--text-muted)', lineHeight: 1.7 }}>
      {[1, 2, 3, 4, 5].map(n => (
        <div key={n}>{n} = {SCOUTING_RATING_LABELS[n]}</div>
      ))}
    </div>
  );
}

function NoteCard({ note }) {
  const dateStr = new Date(note.created_at).toLocaleDateString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
  });
  return (
    <div style={{
      padding: '12px 14px', background: 'rgba(255,255,255,0.03)',
      border: '1px solid rgba(255,255,255,0.06)', borderRadius: 10,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: '0.08em', color: 'var(--text-muted)' }}>SCOUT</span>
        <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{dateStr}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 6 }}>
        <span style={{ fontFamily: 'Space Grotesk', fontSize: 12, fontWeight: 700, color: ACC }}>{note.rating}/5</span>
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)' }}>{SCOUTING_RATING_LABELS[note.rating]}</span>
      </div>
      <div style={{ fontSize: 12.5, color: 'var(--text-primary)', lineHeight: 1.5 }}>{note.note}</div>
    </div>
  );
}

export default function ScoutingNotes({ playerId }) {
  const { role } = useAuth();
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [draft, setDraft] = useState('');
  const [rating, setRating] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  const visible = role === 'scout' || role === 'analyst';

  useEffect(() => {
    if (!visible) return;
    setLoading(true);
    getScoutingNotes(playerId)
      .then(setNotes)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [playerId, visible]);

  if (!visible) return null;

  const handleSubmit = async () => {
    if (!draft.trim() || !rating) return;
    setSubmitting(true);
    setError(null);
    try {
      const created = await postScoutingNote(playerId, draft.trim(), rating);
      setNotes(prev => [created, ...prev]);
      setDraft('');
      setRating(0);
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ padding: '0 22px 22px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <div style={{ width: 3, height: 16, background: ACC, borderRadius: 2 }} />
        <div style={{ fontFamily: 'Space Grotesk', fontSize: 13.5, fontWeight: 600 }}>Scouting Notes</div>
      </div>

      {role === 'scout' && (
        <div style={{
          marginBottom: 14, padding: 14, background: 'rgba(255,255,255,0.02)',
          border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12,
        }}>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Write a note on this player..."
            rows={3}
            style={{
              width: '100%', resize: 'vertical', padding: '9px 11px', fontSize: 12.5,
              fontFamily: 'inherit', background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8,
              color: 'var(--text-primary)', outline: 'none', marginBottom: 10, boxSizing: 'border-box',
            }}
          />
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 14 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14, flexWrap: 'wrap' }}>
              <RatingPicker value={rating} onChange={setRating} />
              <RatingScaleLegend />
            </div>
            <button
              onClick={handleSubmit}
              disabled={submitting || !draft.trim() || !rating}
              style={{
                padding: '7px 16px', borderRadius: 8, border: 'none',
                background: (!draft.trim() || !rating) ? 'rgba(255,107,53,0.3)' : ACC,
                color: '#1a0f08', fontSize: 12, fontWeight: 700,
                cursor: (!draft.trim() || !rating) ? 'default' : 'pointer',
                transition: 'background 0.15s',
              }}
            >
              {submitting ? 'Saving...' : 'Save Note'}
            </button>
          </div>
        </div>
      )}

      {loading && <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Loading notes...</div>}
      {error && <div style={{ fontSize: 12, color: 'var(--red)' }}>{error}</div>}
      {!loading && notes.length === 0 && (
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No scouting notes yet.</div>
      )}
      {!loading && notes.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {notes.map(n => <NoteCard key={n.id} note={n} />)}
        </div>
      )}
    </div>
  );
}
