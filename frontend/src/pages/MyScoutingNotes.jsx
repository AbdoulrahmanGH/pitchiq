import { useState, useEffect, useMemo } from 'react';
import { useAuth } from '../services/AuthProvider';
import { getScoutingNotes } from '../services/api';
import { SCOUTING_RATING_LABELS } from '../constants';

const ACC = '#FF6B35';

export default function MyScoutingNotes() {
  const { role } = useAuth();
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sortDir, setSortDir] = useState('desc');

  useEffect(() => {
    if (role !== 'scout') { setLoading(false); return; }
    getScoutingNotes()
      .then(setNotes)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [role]);

  const sorted = useMemo(() => {
    return [...notes].sort((a, b) => sortDir === 'asc' ? a.rating - b.rating : b.rating - a.rating);
  }, [notes, sortDir]);

  const toggleSort = () => setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 20px', minHeight: 60, borderBottom: '1px solid rgba(255,255,255,0.05)', background: 'rgba(13,17,23,0.7)', backdropFilter: 'blur(12px)', flexShrink: 0 }}>
        <div>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: 18, fontWeight: 600 }}>My Scouting Notes</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>Every note you've written, across all players</div>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 20px 40px' }}>
        {role !== 'scout' && (
          <div style={{ padding: '20px 24px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 12, color: 'var(--text-secondary)', fontSize: 13.5 }}>
            This page is only available to Scout accounts.
          </div>
        )}

        {role === 'scout' && loading && (
          <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>Loading your notes...</div>
        )}

        {role === 'scout' && error && (
          <div style={{ padding: '16px 20px', background: 'var(--red-dim)', border: '1px solid rgba(248,81,73,0.2)', borderRadius: 12, color: 'var(--red)', fontSize: 13 }}>
            Failed to load: {error}
          </div>
        )}

        {role === 'scout' && !loading && !error && notes.length === 0 && (
          <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>You haven't written any scouting notes yet.</div>
        )}

        {role === 'scout' && !loading && !error && notes.length > 0 && (
          <div style={{ borderRadius: 16, border: '1px solid rgba(255,255,255,0.07)', background: 'linear-gradient(145deg, #1C2333 0%, #161B22 100%)', overflow: 'hidden' }}>
            <div style={{ display: 'flex', alignItems: 'center', padding: '11px 16px', borderBottom: '1px solid rgba(255,255,255,0.06)', background: 'rgba(0,0,0,0.15)' }}>
              <div style={{ flex: '1 1 160px', fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#8B949E' }}>Player</div>
              <div style={{ width: 130, flexShrink: 0, fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#8B949E' }}>Team</div>
              <div
                onClick={toggleSort}
                style={{ width: 90, flexShrink: 0, fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: ACC, cursor: 'pointer', userSelect: 'none' }}
              >
                Rating {sortDir === 'asc' ? '↑' : '↓'}
              </div>
              <div style={{ flex: '2 1 260px', fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#8B949E' }}>Note</div>
              <div style={{ width: 100, flexShrink: 0, fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#8B949E', textAlign: 'right' }}>Date</div>
            </div>

            {sorted.map(n => {
              const dateStr = new Date(n.created_at).toLocaleDateString('en-GB', {
                day: '2-digit', month: 'short', year: 'numeric',
              });
              return (
                <div key={n.id} style={{ display: 'flex', alignItems: 'center', padding: '12px 16px', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                  <div style={{ flex: '1 1 160px', fontSize: 12.5, fontWeight: 500, color: 'var(--text-primary)', paddingRight: 8 }}>
                    {n.player_nickname || n.player_name || `Player ${n.player_id}`}
                  </div>
                  <div style={{ width: 130, flexShrink: 0, fontSize: 11.5, color: 'var(--text-secondary)' }}>
                    {n.team_name || '—'}
                  </div>
                  <div style={{ width: 90, flexShrink: 0 }}>
                    <span style={{ fontFamily: 'Space Grotesk', fontSize: 12, fontWeight: 700, color: ACC }}>{n.rating}/5</span>
                    <div style={{ fontSize: 9.5, color: 'var(--text-muted)', marginTop: 2 }}>{SCOUTING_RATING_LABELS[n.rating]}</div>
                  </div>
                  <div style={{ flex: '2 1 260px', fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.4, paddingRight: 12 }}>
                    {n.note}
                  </div>
                  <div style={{ width: 100, flexShrink: 0, fontSize: 11, color: 'var(--text-muted)', textAlign: 'right' }}>
                    {dateStr}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
