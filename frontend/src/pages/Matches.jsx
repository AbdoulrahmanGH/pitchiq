import { useState, useEffect } from 'react';
import { getMatchesSummary } from '../services/api';

const ACC = '#FF6B35';

const RES_MAP = {
  win:  { label: 'WIN',  color: 'var(--green)',  bg: 'var(--green-dim)',  border: 'rgba(63,185,80,0.2)',   dot: '#3FB950' },
  draw: { label: 'DRAW', color: 'var(--yellow)', bg: 'var(--yellow-dim)', border: 'rgba(210,153,34,0.2)', dot: '#D29922' },
  loss: { label: 'LOSS', color: 'var(--red)',    bg: 'var(--red-dim)',    border: 'rgba(248,81,73,0.2)',  dot: '#F85149' },
};

function formatDate(dateStr) {
  const [year, month, day] = dateStr.split('-');
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${months[parseInt(month, 10) - 1]} ${day}`;
}

function PossessionBar({ pct, color }) {
  const opp = (100 - pct).toFixed(1);
  return (
    <div style={{ width: 160, flexShrink: 0 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
        <span style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.06em' }}>POSSESSION</span>
        <span style={{ fontFamily: 'Space Grotesk', fontSize: 13, fontWeight: 700, color }}>{pct}%</span>
      </div>
      <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden', display: 'flex' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: '2px 0 0 2px', transition: 'width 0.8s ease' }} />
        <div style={{ flex: 1, background: 'rgba(255,255,255,0.04)' }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 3 }}>
        <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>AQF</span>
        <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>OPP {opp}%</span>
      </div>
    </div>
  );
}

function MatchCard({ match }) {
  const [hov, setHov] = useState(false);
  const res = RES_MAP[match.result] || RES_MAP.draw;
  const isHome = match.home_away_neutral === 'home';
  const venue = isHome ? (match.venue || 'Home') : 'Away';

  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        background: hov ? 'linear-gradient(145deg, #20293A 0%, #1A2230 100%)' : 'linear-gradient(145deg, #1C2333 0%, #161B22 100%)',
        border: hov ? '1px solid rgba(255,107,53,0.18)' : '1px solid rgba(255,255,255,0.07)',
        borderRadius: 16, padding: '22px 28px',
        display: 'flex', alignItems: 'center',
        transition: 'background 0.2s, border 0.2s, box-shadow 0.2s',
        boxShadow: hov ? '0 8px 32px rgba(0,0,0,0.4)' : '0 4px 16px rgba(0,0,0,0.25)',
        position: 'relative', overflow: 'hidden', cursor: 'default',
      }}
    >
      {/* Left result accent */}
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 3, background: res.color, borderRadius: '3px 0 0 3px' }} />

      {/* Date + location */}
      <div style={{ width: 88, flexShrink: 0, paddingLeft: 8 }}>
        <div style={{ fontFamily: 'Space Grotesk', fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', letterSpacing: '0.02em' }}>{formatDate(match.date)}</div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3 }}>{isHome ? 'Home' : 'Away'}</div>
        <div style={{ marginTop: 6, display: 'inline-block', fontSize: 8.5, fontWeight: 700, letterSpacing: '0.08em', padding: '2px 7px', borderRadius: 4, background: isHome ? 'rgba(88,166,255,0.1)' : 'rgba(255,255,255,0.06)', color: isHome ? '#58A6FF' : 'var(--text-muted)', border: `1px solid ${isHome ? 'rgba(88,166,255,0.2)' : 'rgba(255,255,255,0.07)'}` }}>
          {isHome ? 'HOME' : 'AWAY'}
        </div>
      </div>

      {/* Divider */}
      <div style={{ width: 1, height: 56, background: 'rgba(255,255,255,0.05)', margin: '0 24px', flexShrink: 0 }} />

      {/* Teams & score */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center' }}>
        {/* AQ side */}
        <div style={{ flex: 1, textAlign: 'right', paddingRight: 20 }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>Al Qadsiah</div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.04em' }}>Al Qadsiah FC</div>
        </div>

        {/* Score box */}
        <div style={{ flexShrink: 0, textAlign: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ fontFamily: 'Space Grotesk', fontSize: 38, fontWeight: 700, lineHeight: 1, letterSpacing: '-1px', color: match.result !== 'loss' ? 'var(--text-primary)' : 'rgba(230,237,243,0.5)' }}>
              {match.goals_scored}
            </div>
            <div style={{ fontFamily: 'Space Grotesk', fontSize: 22, fontWeight: 300, color: 'var(--text-muted)', lineHeight: 1 }}>—</div>
            <div style={{ fontFamily: 'Space Grotesk', fontSize: 38, fontWeight: 700, lineHeight: 1, letterSpacing: '-1px', color: match.result === 'loss' ? 'rgba(248,81,73,0.7)' : 'rgba(230,237,243,0.35)' }}>
              {match.goals_conceded}
            </div>
          </div>
          <div style={{ marginTop: 6, display: 'flex', justifyContent: 'center' }}>
            <div style={{ fontSize: 9, fontWeight: 700, padding: '3px 10px', borderRadius: 5, background: res.bg, color: res.color, border: `1px solid ${res.border}`, letterSpacing: '0.1em' }}>
              {res.label}
            </div>
          </div>
        </div>

        {/* Opponent side */}
        <div style={{ flex: 1, textAlign: 'left', paddingLeft: 20 }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 2 }}>{match.opponent}</div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.04em' }}>{venue}</div>
        </div>
      </div>

      {/* Divider */}
      <div style={{ width: 1, height: 56, background: 'rgba(255,255,255,0.05)', margin: '0 24px', flexShrink: 0 }} />

      {/* Possession */}
      {match.possession != null
        ? <PossessionBar pct={match.possession} color={res.color} />
        : <div style={{ width: 160, flexShrink: 0, textAlign: 'center', fontSize: 11, color: '#8B949E' }}>No data</div>
      }
    </div>
  );
}

export default function Matches() {
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  useEffect(() => {
    getMatchesSummary()
      .then(setMatches)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const sorted = [...matches].sort((a, b) => new Date(b.date) - new Date(a.date));
  const wins   = matches.filter(m => m.result === 'win').length;
  const draws  = matches.filter(m => m.result === 'draw').length;
  const losses = matches.filter(m => m.result === 'loss').length;
  const gf = matches.reduce((s, m) => s + m.goals_scored, 0);
  const ga = matches.reduce((s, m) => s + m.goals_conceded, 0);

  const summaryCards = [
    { label: 'Matches Played', value: String(matches.length), color: ACC,             sub: 'SPL 2025/26' },
    { label: 'Wins',           value: String(wins),           color: 'var(--green)',  sub: `${wins * 3} points` },
    { label: 'Draws',          value: String(draws),          color: 'var(--yellow)', sub: `${draws} point${draws !== 1 ? 's' : ''}` },
    { label: 'Losses',         value: String(losses),         color: 'var(--red)',    sub: `Goals ${gf}–${ga}` },
  ];

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Top bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 32px', height: 60, borderBottom: '1px solid rgba(255,255,255,0.05)', background: 'rgba(13,17,23,0.7)', backdropFilter: 'blur(12px)', flexShrink: 0 }}>
        <div>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: 18, fontWeight: 600 }}>Match History</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>Saudi Pro League 2025/26</div>
        </div>
        {/* Form pills */}
        {matches.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 10, color: 'var(--text-muted)', marginRight: 4, letterSpacing: '0.08em' }}>FORM</span>
            {[...matches].sort((a, b) => new Date(a.date) - new Date(b.date)).map((m, i) => {
              const c  = m.result === 'win' ? 'var(--green)' : m.result === 'draw' ? 'var(--yellow)' : 'var(--red)';
              const bg = m.result === 'win' ? 'var(--green-dim)' : m.result === 'draw' ? 'var(--yellow-dim)' : 'var(--red-dim)';
              const l  = m.result === 'win' ? 'W' : m.result === 'draw' ? 'D' : 'L';
              return <div key={i} style={{ width: 26, height: 26, borderRadius: 6, background: bg, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10.5, fontWeight: 700, color: c }}>{l}</div>;
            })}
          </div>
        )}
      </div>

      {/* Scroll area */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '28px 32px 48px' }}>
        {loading && <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, color: 'var(--text-secondary)', fontSize: 14 }}>Loading...</div>}
        {error   && <div style={{ padding: '16px 20px', background: 'var(--red-dim)', border: '1px solid rgba(248,81,73,0.2)', borderRadius: 12, color: 'var(--red)', fontSize: 13 }}>Failed to load: {error}</div>}

        {!loading && !error && (
          <>
            {/* Summary cards */}
            <div style={{ display: 'flex', gap: 16, marginBottom: 28 }}>
              {summaryCards.map(({ label, value, color, sub }) => (
                <div key={label} style={{ flex: 1, background: 'linear-gradient(145deg, #1C2333 0%, #161B22 100%)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 14, padding: '20px 24px', position: 'relative', overflow: 'hidden', boxShadow: '0 4px 20px rgba(0,0,0,0.3)' }}>
                  <div style={{ position: 'absolute', top: -20, right: -20, width: 72, height: 72, background: `radial-gradient(circle, ${color}1A 0%, transparent 70%)`, pointerEvents: 'none' }} />
                  <div style={{ fontSize: 10.5, fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 12 }}>{label}</div>
                  <div style={{ fontFamily: 'Space Grotesk', fontSize: 44, fontWeight: 700, lineHeight: 1, letterSpacing: '-2px', color }}>{value}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>{sub}</div>
                </div>
              ))}
            </div>

            {/* Section header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <div style={{ width: 3, height: 18, background: ACC, borderRadius: 2 }} />
              <div style={{ fontFamily: 'Space Grotesk', fontSize: 15, fontWeight: 600 }}>All Matches</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{sorted.length} results</div>
            </div>

            {/* Match cards */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {sorted.map(m => <MatchCard key={m.id} match={m} />)}
            </div>

            <div style={{ marginTop: 20, fontSize: 11, color: 'var(--text-muted)', textAlign: 'right' }}>
              Saudi Pro League 2025/26
            </div>
          </>
        )}
      </div>
    </div>
  );
}
