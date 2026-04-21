import { useState, useEffect } from 'react';
import { getTeamReadiness, getMatchesSummary } from '../services/api';
import { PLAYER_NAMES, PLAYER_POSITIONS, POS_ABBREV, POS_COLORS } from '../constants';

const ACC = '#FF6B35';

function CircularProgress({ value, size = 72, stroke = 5 }) {
  const r = (size - stroke * 2) / 2;
  const circ = 2 * Math.PI * r;
  const [animPct, setAnimPct] = useState(0);
  useEffect(() => { const t = setTimeout(() => setAnimPct(value / 100), 100); return () => clearTimeout(t); }, [value]);
  const dash = animPct * circ;
  return (
    <div style={{ position: 'relative', flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={ACC}
          strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={`${dash} ${circ}`}
          style={{ transition: 'stroke-dasharray 1.2s cubic-bezier(0.4,0,0.2,1)', filter: `drop-shadow(0 0 6px ${ACC}88)` }} />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'Space Grotesk', fontSize: 12, fontWeight: 700, color: ACC }}>
        {value}%
      </div>
    </div>
  );
}

function StatCard({ title, value, sub, children }) {
  return (
    <div style={{
      background: 'linear-gradient(145deg, #1C2333 0%, #161B22 100%)',
      border: '1px solid rgba(255,255,255,0.07)', borderRadius: 16,
      padding: '24px 26px', flex: 1, position: 'relative', overflow: 'hidden',
      boxShadow: '0 4px 24px rgba(0,0,0,0.3)',
    }}>
      <div style={{ position: 'absolute', top: -30, right: -30, width: 80, height: 80, background: 'radial-gradient(circle, rgba(255,107,53,0.12) 0%, transparent 70%)', pointerEvents: 'none' }} />
      <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 14 }}>{title}</div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 16, justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: 42, fontWeight: 700, fontFamily: 'Space Grotesk', lineHeight: 1, color: 'var(--text-primary)', letterSpacing: '-1px' }}>{value}</div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 6 }}>{sub}</div>
        </div>
        {children}
      </div>
    </div>
  );
}

function FatigueCard({ player }) {
  const [hov, setHov] = useState(false);
  const name = PLAYER_NAMES[player.player_id] || player.player_id;
  const posLabel = POS_ABBREV[PLAYER_POSITIONS[player.player_id]] || '???';
  const posStyle = POS_COLORS[posLabel] || { color: 'var(--text-muted)', bg: 'rgba(255,255,255,0.06)' };
  const num = player.player_id.replace('player-', '');

  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        background: hov ? 'linear-gradient(145deg, #202736 0%, #1C2333 100%)' : 'linear-gradient(145deg, #1C2333 0%, #161B22 100%)',
        border: hov ? '1px solid rgba(255,107,53,0.2)' : '1px solid rgba(255,255,255,0.07)',
        borderRadius: 16, padding: '22px 22px 20px', flex: 1,
        transition: 'background 0.2s, border 0.2s, box-shadow 0.2s',
        boxShadow: hov ? '0 8px 32px rgba(0,0,0,0.4)' : '0 4px 16px rgba(0,0,0,0.3)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
        <div style={{ width: 42, height: 42, borderRadius: 10, background: 'linear-gradient(135deg, #252D3A, #1A2030)', border: '1px solid rgba(255,255,255,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontFamily: 'Space Grotesk', fontWeight: 700, color: 'var(--text-secondary)', flexShrink: 0 }}>
          {num}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{name}</div>
          <span style={{ display: 'inline-block', marginTop: 3, fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', padding: '2px 7px', borderRadius: 4, background: posStyle.bg, color: posStyle.color }}>{posLabel}</span>
        </div>
        <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.12em', padding: '3px 8px', borderRadius: 5, background: 'var(--red-dim)', color: 'var(--red)', flexShrink: 0 }}>
          AT RISK
        </div>
      </div>
      <div style={{ fontSize: 12, color: '#E6EDF3', lineHeight: 1.55, padding: '10px 12px', background: 'rgba(0,0,0,0.2)', borderRadius: 8, borderLeft: '3px solid var(--red)', marginBottom: 14 }}>
        {player.reason}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <div style={{ display: 'flex', gap: 16 }}>
          <div>
            <div style={{ fontSize: 9.5, color: '#8B949E', letterSpacing: '0.08em', marginBottom: 2 }}>TOTAL MINS</div>
            <div style={{ fontFamily: 'Space Grotesk', fontSize: 13, fontWeight: 700, color: '#C9D1D9' }}>{player.total_minutes}</div>
          </div>
          <div>
            <div style={{ fontSize: 9.5, color: '#8B949E', letterSpacing: '0.08em', marginBottom: 2 }}>AVG SPRINTS</div>
            <div style={{ fontFamily: 'Space Grotesk', fontSize: 13, fontWeight: 700, color: '#C9D1D9' }}>{player.avg_sprints}</div>
          </div>
        </div>
      </div>
      <div style={{ height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${Math.min((player.total_minutes / 450) * 100, 100)}%`, background: 'linear-gradient(90deg, var(--red), var(--red))', borderRadius: 2 }} />
      </div>
    </div>
  );
}

function LastMatchCard({ match }) {
  const isHome = match.home_away_neutral === 'home';
  const resMap = {
    win:  { label: 'WIN',  color: 'var(--green)',  bg: 'var(--green-dim)',  border: 'rgba(63,185,80,0.2)' },
    draw: { label: 'DRAW', color: 'var(--yellow)', bg: 'var(--yellow-dim)', border: 'rgba(210,153,34,0.2)' },
    loss: { label: 'LOSS', color: 'var(--red)',    bg: 'var(--red-dim)',    border: 'rgba(248,81,73,0.2)' },
  };
  const res = resMap[match.result] || resMap.draw;
  const dateStr = new Date(match.date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });

  return (
    <div style={{ background: 'linear-gradient(145deg, #1C2333 0%, #161B22 100%)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 16, overflow: 'hidden', flex: '0 0 340px' }}>
      <div style={{ height: 6, background: `linear-gradient(90deg, transparent, ${ACC}44, ${ACC}, ${ACC}44, transparent)` }} />
      <div style={{ padding: '20px 24px 22px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>Last Match</div>
          <div style={{ fontSize: 9.5, padding: '3px 9px', borderRadius: 5, background: res.bg, color: res.color, fontWeight: 700, letterSpacing: '0.1em', border: `1px solid ${res.border}` }}>{res.label}</div>
        </div>
        <div style={{ textAlign: 'center', marginBottom: 20 }}>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 10 }}>
            Al Qadsiah <span style={{ color: 'var(--text-muted)', fontWeight: 400, margin: '0 6px' }}>vs</span> {match.opponent}
          </div>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: 52, fontWeight: 700, letterSpacing: '-2px', lineHeight: 1 }}>
            <span style={{ color: match.result !== 'loss' ? 'var(--text-primary)' : 'rgba(230,237,243,0.5)' }}>{match.goals_scored}</span>
            <span style={{ color: 'var(--text-muted)', margin: '0 10px', fontWeight: 300, fontSize: 36 }}>–</span>
            <span style={{ color: match.result === 'loss' ? 'rgba(248,81,73,0.7)' : 'rgba(230,237,243,0.35)' }}>{match.goals_conceded}</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 10, letterSpacing: '0.06em' }}>
            {dateStr} · {isHome ? match.venue || 'Home' : 'Away'} · {isHome ? 'HOME' : 'AWAY'}
          </div>
        </div>
        {match.possession != null && (
          <div style={{ padding: '12px 16px', background: 'rgba(0,0,0,0.2)', borderRadius: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: 9.5, color: 'var(--text-muted)', letterSpacing: '0.08em' }}>POSSESSION</span>
              <span style={{ fontFamily: 'Space Grotesk', fontSize: 14, fontWeight: 700, color: ACC }}>{match.possession}%</span>
            </div>
            <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{ width: `${match.possession}%`, height: '100%', background: ACC, borderRadius: 2 }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
              <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>AQF</span>
              <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>OPP {(100 - match.possession).toFixed(1)}%</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function RecordDisplay({ matches }) {
  const wins   = matches.filter(m => m.result === 'win').length;
  const draws  = matches.filter(m => m.result === 'draw').length;
  const losses = matches.filter(m => m.result === 'loss').length;
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
      {[['W', wins, 'var(--green)'], ['D', draws, 'var(--yellow)'], ['L', losses, 'var(--red)']].map(([l, v, c]) => (
        <div key={l} style={{ textAlign: 'center', padding: '8px 10px', background: 'rgba(255,255,255,0.03)', borderRadius: 8, border: '1px solid rgba(255,255,255,0.05)', minWidth: 36 }}>
          <div style={{ fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: 18, color: c }}>{v}</div>
          <div style={{ fontSize: 9, color: 'var(--text-muted)', letterSpacing: '0.1em' }}>{l}</div>
        </div>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const [readiness, setReadiness] = useState(null);
  const [matches,   setMatches]   = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState(null);

  useEffect(() => {
    Promise.all([getTeamReadiness(), getMatchesSummary()])
      .then(([r, m]) => { setReadiness(r); setMatches(m); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const lastMatch = matches.length
    ? [...matches].sort((a, b) => new Date(b.date) - new Date(a.date))[0]
    : null;

  const wins   = matches.filter(m => m.result === 'win').length;
  const draws  = matches.filter(m => m.result === 'draw').length;
  const losses = matches.filter(m => m.result === 'loss').length;
  const gf = matches.reduce((s, m) => s + m.goals_scored, 0);
  const ga = matches.reduce((s, m) => s + m.goals_conceded, 0);

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Top bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 32px', height: 60, borderBottom: '1px solid rgba(255,255,255,0.05)', background: 'rgba(13,17,23,0.7)', backdropFilter: 'blur(12px)', flexShrink: 0 }}>
        <div>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: 18, fontWeight: 600 }}>Squad Dashboard</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>Saudi Pro League 2025/26</div>
        </div>
      </div>

      {/* Scroll area */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '28px 32px 40px' }}>
        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, color: 'var(--text-secondary)', fontSize: 14 }}>Loading...</div>
        )}
        {error && (
          <div style={{ padding: '16px 20px', background: 'var(--red-dim)', border: '1px solid rgba(248,81,73,0.2)', borderRadius: 12, color: 'var(--red)', fontSize: 13 }}>
            Failed to load data: {error}
          </div>
        )}
        {!loading && !error && (
          <>
            {/* Stat cards */}
            <div style={{ display: 'flex', gap: 18, marginBottom: 24 }}>
              <StatCard title="Squad Readiness" value={readiness?.readiness_score ?? '—'} sub="Overall squad fitness index">
                <CircularProgress value={readiness?.readiness_score ?? 0} />
              </StatCard>
              <StatCard title="Players Available" value="18/26" sub="8 unavailable — 2 injured, 6 rotation" />
              <StatCard title="Saudi Pro League" value={`${wins}W · ${draws}D · ${losses}L`} sub={`Last ${matches.length} matches · GF ${gf}  GA ${ga}`}>
                <RecordDisplay matches={matches} />
              </StatCard>
            </div>

            {/* Fatigue Risk */}
            {readiness?.at_risk_players?.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                  <div style={{ width: 3, height: 18, background: ACC, borderRadius: 2 }} />
                  <div style={{ fontFamily: 'Space Grotesk', fontSize: 15, fontWeight: 600 }}>Fatigue Risk Players</div>
                  <div style={{ fontSize: 11, padding: '2px 9px', borderRadius: 5, background: 'var(--red-dim)', color: 'var(--red)', fontWeight: 600, letterSpacing: '0.06em' }}>
                    {readiness.at_risk_players.length} flagged
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap' }}>
                  {readiness.at_risk_players.map(p => (
                    <FatigueCard key={p.player_id} player={p} />
                  ))}
                </div>
              </div>
            )}

            {/* Bottom row */}
            <div style={{ display: 'flex', gap: 18 }}>
              {lastMatch && <LastMatchCard match={lastMatch} />}

              {/* Recent form */}
              <div style={{ flex: 1, background: 'linear-gradient(145deg, #1C2333 0%, #161B22 100%)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 16, overflow: 'hidden' }}>
                <div style={{ padding: '20px 20px 0' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <div style={{ width: 3, height: 18, background: ACC, borderRadius: 2 }} />
                    <div style={{ fontFamily: 'Space Grotesk', fontSize: 15, fontWeight: 600 }}>Recent Form</div>
                    <div style={{ display: 'flex', gap: 5, marginLeft: 'auto' }}>
                      {[...matches].sort((a, b) => new Date(a.date) - new Date(b.date)).map((m, i) => {
                        const c  = m.result === 'win' ? 'var(--green)' : m.result === 'draw' ? 'var(--yellow)' : 'var(--red)';
                        const bg = m.result === 'win' ? 'var(--green-dim)' : m.result === 'draw' ? 'var(--yellow-dim)' : 'var(--red-dim)';
                        const lbl = m.result === 'win' ? 'W' : m.result === 'draw' ? 'D' : 'L';
                        return <div key={i} style={{ width: 22, height: 22, borderRadius: 5, background: bg, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700, color: c }}>{lbl}</div>;
                      })}
                    </div>
                  </div>
                </div>
                <div style={{ padding: '4px 4px 8px' }}>
                  {[...matches].sort((a, b) => new Date(b.date) - new Date(a.date)).map((m, i, arr) => {
                    const resColor = m.result === 'win' ? 'var(--green)' : m.result === 'draw' ? 'var(--yellow)' : 'var(--red)';
                    const resBg   = m.result === 'win' ? 'var(--green-dim)' : m.result === 'draw' ? 'var(--yellow-dim)' : 'var(--red-dim)';
                    const resLbl  = m.result === 'win' ? 'WIN' : m.result === 'draw' ? 'DRAW' : 'LOSS';
                    const icon    = m.result === 'win' ? '✓' : m.result === 'draw' ? '—' : '✗';
                    const isHome  = m.home_away_neutral === 'home';
                    const dateStr = new Date(m.date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
                    return (
                      <div key={m.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '11px 16px', borderBottom: i < arr.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none' }}>
                        <div style={{ fontSize: 10, color: resColor, width: 14, textAlign: 'center' }}>{icon}</div>
                        <div style={{ flex: 1, fontSize: 13, fontWeight: 500 }}>
                          <span style={{ opacity: isHome ? 1 : 0.6 }}>Al Qadsiah</span>
                          <span style={{ margin: '0 8px', color: 'var(--text-muted)', fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: 12 }}>{m.goals_scored}–{m.goals_conceded}</span>
                          <span style={{ opacity: !isHome ? 1 : 0.6 }}>{m.opponent}</span>
                        </div>
                        <div style={{ fontSize: 10, color: 'var(--text-muted)', minWidth: 48, textAlign: 'right' }}>{dateStr}</div>
                        <div style={{ fontSize: 9, fontWeight: 700, padding: '3px 8px', borderRadius: 5, background: resBg, color: resColor, letterSpacing: '0.1em', minWidth: 38, textAlign: 'center' }}>{resLbl}</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
