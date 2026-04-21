import { useState, useEffect, useMemo } from 'react';
import { getPlayerPerformance, getFatigueRisk } from '../services/api';
import { PLAYER_NAMES, PLAYER_POSITIONS, POS_ABBREV, POS_COLORS } from '../constants';

const ACC = '#FF6B35';

const POS_MAP = { GK: 'Goalkeeper', DEF: 'Defender', MID: 'Midfielder', FWD: 'Forward' };

const COLUMNS = [
  { key: 'name',           label: 'Player',   flex: '1 1 160px', center: false },
  { key: 'pos',            label: 'Pos',      flex: '0 0 58px',  center: true  },
  { key: 'matches_played', label: 'MP',       flex: '0 0 48px',  center: true  },
  { key: 'total_minutes',  label: 'Mins',     flex: '0 0 62px',  center: true  },
  { key: 'total_goals',    label: 'Goals',    flex: '0 0 68px',  center: true  },
  { key: 'total_assists',  label: 'Assists',  flex: '0 0 72px',  center: true  },
  { key: 'total_shots',    label: 'Shots',    flex: '0 0 100px', center: false },
  { key: 'total_passes',   label: 'Passes',   flex: '0 0 106px', center: false },
  { key: 'avg_distance',   label: 'Avg Dist', flex: '0 0 88px',  center: true  },
  { key: 'total_sprints',  label: 'Sprints',  flex: '0 0 76px',  center: true  },
  { key: 'status',         label: 'Status',   flex: '0 0 90px',  center: true  },
];

function PosBadge({ pos }) {
  const m = POS_COLORS[pos] || { color: 'var(--text-muted)', bg: 'rgba(255,255,255,0.06)' };
  return (
    <span style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: '0.08em', padding: '2px 7px', borderRadius: 4, background: m.bg, color: m.color }}>
      {pos}
    </span>
  );
}

function MiniPill({ value, max, color }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{ fontFamily: 'Space Grotesk', fontWeight: 600, fontSize: 12, color: 'var(--text-primary)', minWidth: 28 }}>{value}</span>
      <div style={{ width: 36, height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 2 }}>
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

function TableRow({ player, acc, maxShots, maxPasses }) {
  const [hov, setHov] = useState(false);
  const statusIsRisk = player.status === 'AT RISK';
  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: 'flex', alignItems: 'center', padding: '0 16px',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
        background: hov ? 'rgba(255,255,255,0.03)' : 'transparent',
        transition: 'background 0.15s', cursor: 'default',
      }}
    >
      {/* Player */}
      <div style={{ flex: '1 1 160px', display: 'flex', alignItems: 'center', gap: 10, padding: '13px 8px' }}>
        <div style={{ width: 30, height: 30, borderRadius: 8, background: 'linear-gradient(135deg, #252D3A, #1A2030)', border: '1px solid rgba(255,255,255,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10.5, fontFamily: 'Space Grotesk', fontWeight: 700, color: '#8B949E', flexShrink: 0 }}>
          {player.player_id.replace('player-', '')}
        </div>
        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{player.name}</span>
      </div>
      {/* Pos */}
      <div style={{ flex: '0 0 58px', display: 'flex', justifyContent: 'center', padding: '13px 4px' }}>
        <PosBadge pos={player.pos} />
      </div>
      {/* MP */}
      <div style={{ flex: '0 0 48px', textAlign: 'center', padding: '13px 4px', fontFamily: 'Space Grotesk', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>{player.matches_played}</div>
      {/* Mins */}
      <div style={{ flex: '0 0 62px', textAlign: 'center', padding: '13px 4px', fontFamily: 'Space Grotesk', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>{player.total_minutes}</div>
      {/* Goals */}
      <div style={{ flex: '0 0 68px', textAlign: 'center', padding: '13px 4px' }}>
        <span style={{ fontFamily: 'Space Grotesk', fontSize: 13, fontWeight: 700, color: player.total_goals > 0 ? acc : 'var(--text-muted)' }}>{player.total_goals}</span>
      </div>
      {/* Assists */}
      <div style={{ flex: '0 0 72px', textAlign: 'center', padding: '13px 4px' }}>
        <span style={{ fontFamily: 'Space Grotesk', fontSize: 13, fontWeight: 700, color: player.total_assists > 0 ? 'var(--blue)' : 'var(--text-muted)' }}>{player.total_assists}</span>
      </div>
      {/* Shots */}
      <div style={{ flex: '0 0 100px', padding: '13px 8px' }}>
        <MiniPill value={player.total_shots} max={maxShots} color={acc} />
      </div>
      {/* Passes */}
      <div style={{ flex: '0 0 106px', padding: '13px 8px' }}>
        <MiniPill value={player.total_passes} max={maxPasses} color="var(--purple)" />
      </div>
      {/* Avg Dist */}
      <div style={{ flex: '0 0 88px', textAlign: 'center', padding: '13px 4px', fontFamily: 'Space Grotesk', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>{player.avg_distance}km</div>
      {/* Sprints */}
      <div style={{ flex: '0 0 76px', textAlign: 'center', padding: '13px 4px', fontFamily: 'Space Grotesk', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>{player.total_sprints}</div>
      {/* Status */}
      <div style={{ flex: '0 0 90px', display: 'flex', justifyContent: 'center', padding: '13px 4px' }}>
        <span style={{
          fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', padding: '3px 8px', borderRadius: 5,
          background: statusIsRisk ? 'var(--red-dim)' : 'var(--green-dim)',
          color: statusIsRisk ? 'var(--red)' : 'var(--green)',
          border: `1px solid ${statusIsRisk ? 'rgba(248,81,73,0.2)' : 'rgba(63,185,80,0.2)'}`,
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
  const [loading, setLoading]   = useState(true);
  const [error,   setError]     = useState(null);
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

  const totalGoals   = players.reduce((s, p) => s + p.total_goals, 0);
  const totalAssists = players.reduce((s, p) => s + p.total_assists, 0);
  const avgDist = players.length ? (players.reduce((s, p) => s + p.avg_distance, 0) / players.length).toFixed(1) : 0;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Top bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 32px', height: 60, borderBottom: '1px solid rgba(255,255,255,0.05)', background: 'rgba(13,17,23,0.7)', backdropFilter: 'blur(12px)', flexShrink: 0 }}>
        <div>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: 18, fontWeight: 600 }}>Player Performance</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>Saudi Pro League 2025/26 · {players.length} Players</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
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

      <div style={{ flex: 1, overflowY: 'auto', padding: '24px 32px 40px' }}>
        {loading && <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, color: 'var(--text-secondary)', fontSize: 14 }}>Loading...</div>}
        {error   && <div style={{ padding: '16px 20px', background: 'var(--red-dim)', border: '1px solid rgba(248,81,73,0.2)', borderRadius: 12, color: 'var(--red)', fontSize: 13 }}>Failed to load: {error}</div>}

        {!loading && !error && (
          <>
            {/* Summary stat cards */}
            <div style={{ display: 'flex', gap: 16, marginBottom: 24 }}>
              {[
                { label: 'Total Goals',          value: totalGoals,    color: ACC             },
                { label: 'Total Assists',         value: totalAssists,  color: 'var(--blue)'  },
                { label: 'Avg Distance / Match',  value: `${avgDist}km`, color: 'var(--green)' },
              ].map(({ label, value, color }) => (
                <div key={label} style={{ flex: 1, background: 'linear-gradient(145deg, #1C2333 0%, #161B22 100%)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 14, padding: '20px 24px', position: 'relative', overflow: 'hidden', boxShadow: '0 4px 20px rgba(0,0,0,0.3)' }}>
                  <div style={{ position: 'absolute', top: -20, right: -20, width: 70, height: 70, borderRadius: '50%', background: `radial-gradient(circle, ${color}18 0%, transparent 70%)`, pointerEvents: 'none' }} />
                  <div style={{ fontSize: 10.5, fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 10 }}>{label}</div>
                  <div style={{ fontFamily: 'Space Grotesk', fontSize: 40, fontWeight: 700, lineHeight: 1, color: 'var(--text-primary)', letterSpacing: '-1px' }}>{value}</div>
                  <div style={{ marginTop: 10, height: 2, background: 'rgba(255,255,255,0.05)', borderRadius: 1 }}>
                    <div style={{ height: '100%', width: '60%', background: `linear-gradient(90deg, transparent, ${color})`, borderRadius: 1 }} />
                  </div>
                </div>
              ))}
            </div>

            {/* Table */}
            <div style={{ background: 'linear-gradient(145deg, #1C2333 0%, #161B22 100%)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 16, overflow: 'hidden' }}>
              {/* Header */}
              <div style={{ display: 'flex', alignItems: 'center', padding: '0 16px', borderBottom: '1px solid rgba(255,255,255,0.06)', background: 'rgba(0,0,0,0.15)' }}>
                {COLUMNS.map(col => (
                  <div
                    key={col.key}
                    onClick={() => col.key !== 'status' && col.key !== 'pos' && handleSort(col.key)}
                    style={{
                      flex: col.flex, padding: '12px 8px',
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

              {/* Rows */}
              {sorted.map(p => (
                <TableRow key={p.player_id} player={p} acc={ACC} maxShots={maxShots} maxPasses={maxPasses} />
              ))}
            </div>

            <div style={{ marginTop: 14, fontSize: 11, color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between' }}>
              <span>{sorted.length} players shown · Click column headers to sort</span>
              <span>Saudi Pro League 2025/26</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
