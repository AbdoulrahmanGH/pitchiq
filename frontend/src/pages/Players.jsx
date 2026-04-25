import { useState, useEffect, useMemo, useRef } from 'react';
import { getPlayerPerformance, getFatigueRisk } from '../services/api';
import { PLAYER_NAMES, PLAYER_POSITIONS, POS_ABBREV, POS_COLORS } from '../constants';

const ACC = '#FF6B35';
const POS_MAP = { GK: 'Goalkeeper', DEF: 'Defender', MID: 'Midfielder', FWD: 'Forward' };

const COLUMNS = [
  { key: 'name',                   label: 'Player',    w: 180, center: false },
  { key: 'pos',                    label: 'Pos',       w: 60,  center: true  },
  { key: 'matches_played',         label: 'MP',        w: 50,  center: true  },
  { key: 'total_minutes',          label: 'Mins',      w: 60,  center: true,  hideMobile: true },
  { key: 'total_goals',            label: 'Goals',     w: 60,  center: true  },
  { key: 'total_assists',          label: 'Assists',   w: 70,  center: true  },
  { key: 'total_shots',            label: 'Shots',     w: 60,  center: true,  hideMobile: true },
  { key: 'total_passes',           label: 'Passes',    w: 70,  center: true,  hideMobile: true },
  { key: 'avg_distance',           label: 'Avg Dist',  w: 80,  center: true,  hideMobile: true },
  { key: 'total_sprints',          label: 'Sprints',   w: 75,  center: true,  hideMobile: true },
  { key: 'total_expected_goals',   label: 'xG',        w: 55,  center: true  },
  { key: 'total_expected_assists', label: 'xA',        w: 55,  center: true,  hideMobile: true },
  { key: 'total_key_passes',       label: 'Key Pass',  w: 75,  center: true,  hideMobile: true },
  { key: 'total_tackles',          label: 'Tackles',   w: 70,  center: true,  hideMobile: true },
  { key: 'dribble_success_rate',   label: 'Dribble %', w: 80,  center: true,  hideMobile: true },
  { key: 'status',                 label: 'Status',    w: 80,  center: true  },
];

const TABLE_MIN_W = COLUMNS.reduce((s, c) => s + c.w, 0) + 32;

function PosBadge({ pos }) {
  const m = POS_COLORS[pos] || { color: 'var(--text-muted)', bg: 'rgba(255,255,255,0.06)' };
  return (
    <span style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: '0.08em', padding: '2px 7px', borderRadius: 4, background: m.bg, color: m.color }}>
      {pos}
    </span>
  );
}

function MiniBar({ value, max, color }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
      <span style={{ fontFamily: 'Space Grotesk', fontWeight: 600, fontSize: 12, color: 'var(--text-primary)', minWidth: 24, textAlign: 'right' }}>{value}</span>
      <div style={{ width: 28, height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 2, flexShrink: 0 }}>
        <div style={{ width: `${Math.min((value / max) * 100, 100)}%`, height: '100%', background: color, borderRadius: 2 }} />
      </div>
    </div>
  );
}

function SortIcon({ dir }) {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" fill="none" style={{ marginLeft: 4, flexShrink: 0 }}>
      {dir === 'asc'
        ? <path d="M5 2L8.5 7H1.5L5 2Z" fill="currentColor" opacity="0.9" />
        : dir === 'desc'
        ? <path d="M5 8L1.5 3H8.5L5 8Z" fill="currentColor" opacity="0.9" />
        : <><path d="M5 1.5L7.5 4.5H2.5L5 1.5Z" fill="currentColor" opacity="0.25"/><path d="M5 8.5L2.5 5.5H7.5L5 8.5Z" fill="currentColor" opacity="0.25"/></>
      }
    </svg>
  );
}

const NUM = { fontFamily: 'Space Grotesk', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' };

function TableRow({ player, acc, maxShots, maxPasses }) {
  const [hov, setHov] = useState(false);
  const statusIsRisk = player.status === 'AT RISK';

  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: 'flex', alignItems: 'center',
        padding: '0 16px', minHeight: 48,
        borderBottom: '1px solid rgba(255,255,255,0.04)',
        background: hov ? 'rgba(255,255,255,0.03)' : 'transparent',
        transition: 'background 0.15s', cursor: 'default',
      }}
    >
      <div style={{ width: 180, flexShrink: 0, display: 'flex', alignItems: 'center', gap: 10, paddingRight: 8 }}>
        <div style={{ width: 28, height: 28, borderRadius: 7, background: 'linear-gradient(135deg, #252D3A, #1A2030)', border: '1px solid rgba(255,255,255,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontFamily: 'Space Grotesk', fontWeight: 700, color: '#8B949E', flexShrink: 0 }}>
          {player.player_id.replace('player-', '')}
        </div>
        <span style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{player.name}</span>
      </div>

      <div style={{ width: 60, flexShrink: 0, display: 'flex', justifyContent: 'center' }}>
        <PosBadge pos={player.pos} />
      </div>

      <div style={{ width: 50, flexShrink: 0, textAlign: 'center', ...NUM }}>{player.matches_played}</div>

      <div className="col-hide-mobile" style={{ width: 60, flexShrink: 0, textAlign: 'center', ...NUM }}>{player.total_minutes}</div>

      <div style={{ width: 60, flexShrink: 0, textAlign: 'center' }}>
        <span style={{ fontFamily: 'Space Grotesk', fontSize: 13, fontWeight: 700, color: player.total_goals > 0 ? acc : 'var(--text-muted)' }}>{player.total_goals}</span>
      </div>

      <div style={{ width: 70, flexShrink: 0, textAlign: 'center' }}>
        <span style={{ fontFamily: 'Space Grotesk', fontSize: 13, fontWeight: 700, color: player.total_assists > 0 ? 'var(--blue)' : 'var(--text-muted)' }}>{player.total_assists}</span>
      </div>

      <div className="col-hide-mobile" style={{ width: 60, flexShrink: 0, display: 'flex', justifyContent: 'center' }}>
        <MiniBar value={player.total_shots} max={maxShots} color={acc} />
      </div>

      <div className="col-hide-mobile" style={{ width: 70, flexShrink: 0, display: 'flex', justifyContent: 'center' }}>
        <MiniBar value={player.total_passes} max={maxPasses} color="var(--purple)" />
      </div>

      <div className="col-hide-mobile" style={{ width: 80, flexShrink: 0, textAlign: 'center', ...NUM }}>{player.avg_distance}km</div>

      <div className="col-hide-mobile" style={{ width: 75, flexShrink: 0, textAlign: 'center', ...NUM }}>{player.total_sprints}</div>

      <div style={{ width: 55, flexShrink: 0, textAlign: 'center' }}>
        <span style={{ fontFamily: 'Space Grotesk', fontSize: 12, fontWeight: 600, color: player.total_expected_goals > 0.3 ? '#58A6FF' : 'var(--text-secondary)' }}>{player.total_expected_goals}</span>
      </div>

      <div className="col-hide-mobile" style={{ width: 55, flexShrink: 0, textAlign: 'center' }}>
        <span style={{ fontFamily: 'Space Grotesk', fontSize: 12, fontWeight: 600, color: player.total_expected_assists > 0.2 ? 'var(--purple)' : 'var(--text-secondary)' }}>{player.total_expected_assists}</span>
      </div>

      <div className="col-hide-mobile" style={{ width: 75, flexShrink: 0, textAlign: 'center', ...NUM }}>{player.total_key_passes}</div>

      <div className="col-hide-mobile" style={{ width: 70, flexShrink: 0, textAlign: 'center' }}>
        <span style={{ fontFamily: 'Space Grotesk', fontSize: 12, fontWeight: 600, color: player.total_tackles > 15 ? 'var(--green)' : 'var(--text-secondary)' }}>{player.total_tackles}</span>
      </div>

      <div className="col-hide-mobile" style={{ width: 80, flexShrink: 0, textAlign: 'center' }}>
        <span style={{ fontFamily: 'Space Grotesk', fontSize: 12, fontWeight: 600, color: player.dribble_success_rate >= 70 ? 'var(--green)' : player.dribble_success_rate >= 50 ? acc : 'var(--text-muted)' }}>
          {player.dribble_success_rate > 0 ? `${player.dribble_success_rate}%` : '—'}
        </span>
      </div>

      <div style={{ width: 80, flexShrink: 0, display: 'flex', justifyContent: 'center' }}>
        <span style={{
          fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', padding: '3px 8px', borderRadius: 5,
          background: statusIsRisk ? 'var(--red-dim)' : 'var(--green-dim)',
          color: statusIsRisk ? 'var(--red)' : 'var(--green)',
          border: `1px solid ${statusIsRisk ? 'rgba(248,81,73,0.2)' : 'rgba(63,185,80,0.2)'}`,
          whiteSpace: 'nowrap',
        }}>
          {player.status}
        </span>
      </div>
    </div>
  );
}

export default function Players() {
  const [performance, setPerformance] = useState([]);
  const [fatigueRisk, setFatigueRisk] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [filterPos, setFilterPos] = useState('ALL');
  const [sortKey,   setSortKey]   = useState('total_goals');
  const [sortDir,   setSortDir]   = useState('desc');

  useEffect(() => {
    Promise.all([getPlayerPerformance(), getFatigueRisk()])
      .then(([perf, risk]) => { setPerformance(perf); setFatigueRisk(risk); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const atRiskIds = useMemo(() => new Set(fatigueRisk.map(p => p.player_id)), [fatigueRisk]);

  const players = useMemo(() => performance.map(p => ({
    ...p,
    name: PLAYER_NAMES[p.player_id] || p.player_id,
    pos:  POS_ABBREV[PLAYER_POSITIONS[p.player_id]] || '???',
    status: atRiskIds.has(p.player_id) ? 'AT RISK' : 'FIT',
  })), [performance, atRiskIds]);

  const filtered = useMemo(() =>
    filterPos === 'ALL' ? players : players.filter(p => PLAYER_POSITIONS[p.player_id] === POS_MAP[filterPos]),
    [players, filterPos]
  );

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey];
      if (typeof av === 'string') return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
      return sortDir === 'asc' ? av - bv : bv - av;
    });
  }, [filtered, sortKey, sortDir]);

  const handleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('desc'); }
  };

  const maxShots  = Math.max(1, ...players.map(p => p.total_shots));
  const maxPasses = Math.max(1, ...players.map(p => p.total_passes));

  const scrollRef  = useRef(null);
  const hintShown  = useRef(false);
  const [showFade,    setShowFade]    = useState(false);
  const [hintOpacity, setHintOpacity] = useState(0);

  useEffect(() => {
    if (loading) return;
    const raf = requestAnimationFrame(() => {
      const el = scrollRef.current;
      if (!el) return;

      const check = () => {
        const scrollable = el.scrollWidth > el.clientWidth + 4;
        const atEnd      = el.scrollLeft + el.clientWidth >= el.scrollWidth - 4;
        setShowFade(scrollable && !atEnd);
      };

      check();

      if (!hintShown.current && el.scrollWidth > el.clientWidth + 4) {
        hintShown.current = true;
        setHintOpacity(1);
        setTimeout(() => setHintOpacity(0), 3000);
      }

      el.addEventListener('scroll', check, { passive: true });
      window.addEventListener('resize', check, { passive: true });
    });

    return () => {
      cancelAnimationFrame(raf);
      const el = scrollRef.current;
      if (!el) return;
      const check = () => {};
      el.removeEventListener('scroll', check);
      window.removeEventListener('resize', check);
    };
  }, [loading]);

  const totalGoals   = players.reduce((s, p) => s + p.total_goals, 0);
  const totalAssists = players.reduce((s, p) => s + p.total_assists, 0);
  const avgDist = players.length ? (players.reduce((s, p) => s + p.avg_distance, 0) / players.length).toFixed(1) : 0;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, padding: '0 20px', minHeight: 60, borderBottom: '1px solid rgba(255,255,255,0.05)', background: 'rgba(13,17,23,0.7)', backdropFilter: 'blur(12px)', flexShrink: 0 }}>
        <div style={{ padding: '8px 0' }}>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: 18, fontWeight: 600 }}>Player Performance</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>Saudi Pro League 2025/26 · {players.length} Players</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', padding: '8px 0' }}>
          {['ALL', 'GK', 'DEF', 'MID', 'FWD'].map(p => {
            const m = POS_COLORS[p] || {};
            const isActive = filterPos === p;
            return (
              <div key={p} onClick={() => setFilterPos(p)} style={{
                padding: '5px 12px', borderRadius: 7, fontSize: 11, fontWeight: 600,
                cursor: 'pointer', letterSpacing: '0.08em',
                background: isActive ? (p === 'ALL' ? 'rgba(255,107,53,0.12)' : m.bg) : 'rgba(255,255,255,0.04)',
                color: isActive ? (p === 'ALL' ? ACC : m.color) : 'var(--text-secondary)',
                border: `1px solid ${isActive ? (p === 'ALL' ? 'rgba(255,107,53,0.25)' : m.color + '44') : 'rgba(255,255,255,0.07)'}`,
                transition: 'all 0.15s',
              }}>{p}</div>
            );
          })}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', overflowX: 'visible', padding: '20px 20px 40px', minWidth: 0 }}>
        {loading && <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, color: 'var(--text-secondary)', fontSize: 14 }}>Loading...</div>}
        {error   && <div style={{ padding: '16px 20px', background: 'var(--red-dim)', border: '1px solid rgba(248,81,73,0.2)', borderRadius: 12, color: 'var(--red)', fontSize: 13 }}>Failed to load: {error}</div>}

        {!loading && !error && (
          <>
            <div style={{ display: 'flex', gap: 16, marginBottom: 20, flexWrap: 'wrap' }}>
              {[
                { label: 'Total Goals',         value: totalGoals,     color: ACC            },
                { label: 'Total Assists',        value: totalAssists,   color: 'var(--blue)'  },
                { label: 'Avg Distance / Match', value: `${avgDist}km`, color: 'var(--green)' },
              ].map(({ label, value, color }) => (
                <div key={label} style={{ flex: '1 1 160px', background: 'linear-gradient(145deg, #1C2333 0%, #161B22 100%)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 14, padding: '18px 22px', position: 'relative', overflow: 'hidden', boxShadow: '0 4px 20px rgba(0,0,0,0.3)' }}>
                  <div style={{ position: 'absolute', top: -20, right: -20, width: 70, height: 70, borderRadius: '50%', background: `radial-gradient(circle, ${color}18 0%, transparent 70%)`, pointerEvents: 'none' }} />
                  <div style={{ fontSize: 10.5, fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 8 }}>{label}</div>
                  <div style={{ fontFamily: 'Space Grotesk', fontSize: 36, fontWeight: 700, lineHeight: 1, color: 'var(--text-primary)', letterSpacing: '-1px' }}>{value}</div>
                  <div style={{ marginTop: 10, height: 2, background: 'rgba(255,255,255,0.05)', borderRadius: 1 }}>
                    <div style={{ height: '100%', width: '60%', background: `linear-gradient(90deg, transparent, ${color})`, borderRadius: 1 }} />
                  </div>
                </div>
              ))}
            </div>

            {/* scaleY(-1) double-flip: moves horizontal scrollbar from bottom to top, no JS sync needed */}
            <div style={{ position: 'relative' }}>
              {showFade && (
                <div style={{
                  position: 'absolute',
                  top: 8, right: 0, bottom: 0, width: 80,
                  background: 'linear-gradient(to left, #161B22 0%, transparent 100%)',
                  borderRadius: '0 16px 16px 0',
                  pointerEvents: 'none',
                  zIndex: 2,
                }} />
              )}

              <div style={{ transform: 'scaleY(-1)' }}>
                <div
                  ref={scrollRef}
                  className="table-scroll"
                  style={{
                    overflowX: 'auto',
                    width: '100%',
                    WebkitOverflowScrolling: 'touch',
                    borderRadius: 16,
                    border: '1px solid rgba(255,255,255,0.07)',
                    background: 'linear-gradient(145deg, #1C2333 0%, #161B22 100%)',
                  }}
                >
                  <div style={{ minWidth: TABLE_MIN_W, width: 'max-content', transform: 'scaleY(-1)' }}>

                    <div style={{ display: 'flex', alignItems: 'center', padding: '0 16px', borderBottom: '1px solid rgba(255,255,255,0.06)', background: 'rgba(0,0,0,0.15)' }}>
                      {COLUMNS.map(col => (
                        <div
                          key={col.key}
                          className={col.hideMobile ? 'col-hide-mobile' : undefined}
                          onClick={() => col.key !== 'status' && col.key !== 'pos' && handleSort(col.key)}
                          style={{
                            width: col.w, flexShrink: 0,
                            padding: '11px 4px',
                            fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase',
                            color: sortKey === col.key ? ACC : '#8B949E',
                            cursor: col.key !== 'status' && col.key !== 'pos' ? 'pointer' : 'default',
                            display: 'flex', alignItems: 'center',
                            justifyContent: col.center ? 'center' : 'flex-start',
                            userSelect: 'none', transition: 'color 0.15s',
                          }}
                        >
                          {col.label}
                          {col.key !== 'status' && col.key !== 'pos' && (
                            <SortIcon dir={sortKey === col.key ? sortDir : null} />
                          )}
                        </div>
                      ))}
                    </div>

                    {sorted.map(p => (
                      <TableRow key={p.player_id} player={p} acc={ACC} maxShots={maxShots} maxPasses={maxPasses} />
                    ))}

                  </div>
                </div>
              </div>
            </div>

            <div style={{
              marginTop: 8, textAlign: 'center',
              fontSize: 11, color: '#8B949E',
              opacity: hintOpacity,
              transition: 'opacity 0.8s ease',
              pointerEvents: 'none',
              minHeight: 18,
            }}>
              {hintOpacity > 0 && '← Scroll to see more →'}
            </div>

            <div style={{ marginTop: 4, fontSize: 11, color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 4 }}>
              <span>{sorted.length} players shown · Click column headers to sort</span>
              <span>Saudi Pro League 2025/26</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
