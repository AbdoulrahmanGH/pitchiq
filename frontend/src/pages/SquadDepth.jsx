import { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { getSquadDepth, getFatigueRisk, getTeamReadiness, getPlayerStatuses, postPlayerStatus } from '../services/api';
import { useAuth } from '../services/AuthProvider';
import { initials } from '../constants';
import CircularProgress from '../components/CircularProgress';
import Skeleton from '../components/Skeleton';

const ACC = '#FF5A1F';

const POSITIONS = [
  { key: 'Goalkeeper', abbr: 'GK',  plural: 'Goalkeepers', colorHex: '#58A6FF', color: 'var(--blue)',   dim: 'var(--blue-dim)'   },
  { key: 'Defender',   abbr: 'DEF', plural: 'Defenders',   colorHex: '#10B981', color: 'var(--green)',  dim: 'var(--green-dim)'  },
  { key: 'Midfielder', abbr: 'MID', plural: 'Midfielders', colorHex: '#A78BFA', color: 'var(--purple)', dim: 'var(--purple-dim)' },
  { key: 'Forward',    abbr: 'FWD', plural: 'Forwards',    colorHex: '#FF5A1F', color: 'var(--orange)', dim: 'var(--orange-dim)' },
];

const STATUS_META = {
  available:   { label: 'AVAILABLE',   color: 'var(--green)',  bg: 'var(--green-dim)'  },
  doubtful:    { label: 'DOUBTFUL',    color: 'var(--yellow)', bg: 'var(--yellow-dim)' },
  unavailable: { label: 'UNAVAILABLE', color: 'var(--red)',    bg: 'var(--red-dim)'    },
};

function StatusBadge({ status }) {
  const meta = STATUS_META[status];
  if (!meta) return null;
  return (
    <span style={{ fontSize: 8.5, fontWeight: 700, letterSpacing: '0.06em', padding: '2px 6px', borderRadius: 5, background: meta.bg, color: meta.color, whiteSpace: 'nowrap' }}>
      {meta.label}
    </span>
  );
}

function StatusSelect({ playerId, status, onSaved }) {
  const [saving, setSaving] = useState(false);
  const handle = async (e) => {
    const next = e.target.value;
    setSaving(true);
    try {
      await postPlayerStatus(playerId, next);
      onSaved(playerId, next);
    } catch {
      // best-effort UI -- a failed save just leaves the dropdown at its
      // current value, no destructive local state change to undo
    } finally {
      setSaving(false);
    }
  };
  return (
    <select
      value={status || 'available'}
      onChange={handle}
      disabled={saving}
      style={{
        fontSize: 10, fontWeight: 600, padding: '3px 5px', borderRadius: 5,
        background: 'rgba(255,255,255,0.05)', color: 'var(--text-primary)',
        border: '1px solid rgba(255,255,255,0.12)', outline: 'none',
        cursor: saving ? 'default' : 'pointer', flexShrink: 0,
      }}
    >
      <option value="available" style={{ background: 'var(--surface2)', color: 'var(--text-primary)' }}>Available</option>
      <option value="doubtful" style={{ background: 'var(--surface2)', color: 'var(--text-primary)' }}>Doubtful</option>
      <option value="unavailable" style={{ background: 'var(--surface2)', color: 'var(--text-primary)' }}>Unavailable</option>
    </select>
  );
}

function ReadinessCard({ readiness }) {
  const score = readiness?.readiness_score ?? 0;
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 22,
      background: 'linear-gradient(145deg, var(--surface2) 0%, var(--bg-surface) 100%)',
      border: '1px solid rgba(255,255,255,0.07)', borderRadius: 16,
      padding: '20px 24px', marginBottom: 24, boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
    }}>
      <CircularProgress value={score} />
      <div>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
          Squad Readiness
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 5 }}>
          {readiness?.at_risk_players?.length ?? 0} fatigue-flagged · {readiness?.unavailable_players?.length ?? 0} unavailable · {readiness?.doubtful_players?.length ?? 0} doubtful
        </div>
      </div>
    </div>
  );
}

function DepthCard({ pos, players, atRiskIds, statusByPlayerId, isCoach, onStatusSaved }) {
  const [hov, setHov] = useState(false);
  const count = players.length;
  const lowDepth = count < 3;

  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        flex: 1,
        background: hov ? 'linear-gradient(145deg, var(--surface3) 0%, var(--surface2) 100%)' : 'linear-gradient(145deg, var(--surface2) 0%, var(--bg-surface) 100%)',
        border: hov ? `1px solid ${pos.colorHex}30` : '1px solid rgba(255,255,255,0.07)',
        borderRadius: 16, overflow: 'hidden',
        transition: 'background 0.2s, border 0.2s, box-shadow 0.2s',
        boxShadow: hov ? `0 8px 32px rgba(0,0,0,0.4), 0 0 20px ${pos.colorHex}0A` : '0 4px 16px rgba(0,0,0,0.25)',
      }}
    >
      <div style={{ height: 3, background: `linear-gradient(90deg, transparent, ${pos.colorHex}88, ${pos.colorHex}, ${pos.colorHex}88, transparent)` }} />
      <div style={{ padding: '18px 20px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', padding: '2px 8px', borderRadius: 4, background: pos.dim, color: pos.color }}>{pos.abbr}</div>
              {lowDepth && (
                <div style={{ fontSize: 9, fontWeight: 600, padding: '2px 7px', borderRadius: 4, background: 'rgba(248,81,73,0.1)', color: 'var(--red)', border: '1px solid rgba(248,81,73,0.2)' }}>⚠ LOW</div>
              )}
            </div>
            <div style={{ fontFamily: 'Space Grotesk', fontSize: 28, fontWeight: 700, lineHeight: 1, color: pos.color, letterSpacing: '-0.5px', fontVariantNumeric: 'tabular-nums' }}>{count}</div>
            <div style={{ fontSize: 10.5, color: 'var(--text-secondary)', marginTop: 2 }}>{pos.plural.toLowerCase()} in squad</div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5, alignItems: 'flex-end' }}>
            {(() => {
              const atRisk = players.filter(p => atRiskIds.has(p.id)).length;
              const fit    = count - atRisk;
              return (
                <>
                  {fit > 0    && <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10, color: 'var(--text-secondary)' }}><div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--green)' }}/>{fit} fit</div>}
                  {atRisk > 0 && <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10, color: 'var(--text-secondary)' }}><div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--yellow)' }}/>{atRisk} at risk</div>}
                </>
              );
            })()}
          </div>
        </div>

        <div style={{ height: 1, background: 'rgba(255,255,255,0.05)', marginBottom: 14 }} />

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {players.map(p => {
            const isRisk = atRiskIds.has(p.id);
            const status = statusByPlayerId[p.id];
            return (
              <div key={p.id} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 22, height: 22, borderRadius: 6, background: 'var(--surface2)', border: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9.5, fontFamily: 'Space Grotesk', fontWeight: 700, color: 'var(--text-secondary)', flexShrink: 0 }}>
                  {initials(p.name)}
                </div>
                <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.name}</span>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: isRisk ? 'var(--yellow)' : 'var(--green)', flexShrink: 0, boxShadow: `0 0 4px ${isRisk ? 'var(--yellow)' : 'var(--green)'}` }} />
                {isCoach ? (
                  <StatusSelect playerId={p.id} status={status} onSaved={onStatusSaved} />
                ) : (
                  status && status !== 'available' && <StatusBadge status={status} />
                )}
              </div>
            );
          })}
        </div>

        {lowDepth && (
          <div style={{ marginTop: 14, padding: '9px 12px', borderRadius: 8, background: 'rgba(248,81,73,0.08)', border: '1px solid rgba(248,81,73,0.18)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 1L11 10H1L6 1Z" stroke="var(--red)" strokeWidth="1.2" strokeLinejoin="round"/><line x1="6" y1="5" x2="6" y2="7.5" stroke="var(--red)" strokeWidth="1.2" strokeLinecap="round"/><circle cx="6" cy="9" r=".6" fill="var(--red)"/></svg>
            <span style={{ fontSize: 10.5, color: 'var(--red)', fontWeight: 500 }}>Low depth — rotation risk</span>
          </div>
        )}
      </div>
    </div>
  );
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: 'var(--surface2)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, padding: '8px 14px' }}>
      <div style={{ fontFamily: 'Space Grotesk', fontWeight: 700, color: 'var(--text-primary)', fontSize: 13 }}>{payload[0].value} players</div>
    </div>
  );
};

export default function SquadDepth() {
  const { role } = useAuth();
  const isCoach = role === 'coach';
  const [depth,     setDepth]     = useState(null);
  const [fatigue,   setFatigue]   = useState([]);
  const [readiness, setReadiness] = useState(null);
  const [statusByPlayerId, setStatusByPlayerId] = useState({});
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState(null);

  useEffect(() => {
    Promise.all([getSquadDepth(), getFatigueRisk(), getTeamReadiness(), getPlayerStatuses()])
      .then(([d, f, r, statuses]) => {
        setDepth(d);
        setFatigue(f);
        setReadiness(r);
        setStatusByPlayerId(Object.fromEntries(statuses.map(s => [s.player_id, s.status])));
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleStatusSaved = (playerId, status) => {
    setStatusByPlayerId(prev => ({ ...prev, [playerId]: status }));
    getTeamReadiness().then(setReadiness).catch(() => {});
  };

  const atRiskIds = new Set(fatigue.map(p => p.player_id));

  const chartData = depth ? POSITIONS.map(p => ({
    position: p.plural,
    count:    (depth[p.key] || []).length,
    colorHex: p.colorHex,
  })) : [];
  const chartMax = Math.max(12, ...chartData.map(d => d.count)) + 2;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, padding: '0 20px', minHeight: 60, borderBottom: '1px solid rgba(255,255,255,0.05)', background: 'rgba(13,17,23,0.7)', backdropFilter: 'blur(12px)', flexShrink: 0 }}>
        <div>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: 18, fontWeight: 600 }}>Squad Depth</div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 1 }}>
            {isCoach ? 'Position availability — set player status inline' : 'Position availability across the squad'}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          {[['var(--green)', 'FIT'], ['var(--yellow)', 'AT RISK']].map(([c, l]) => (
            <div key={l} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 7, height: 7, borderRadius: '50%', background: c }} />
              <span style={{ fontSize: 10.5, color: 'var(--text-secondary)', letterSpacing: '0.06em' }}>{l}</span>
            </div>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 20px 48px', minWidth: 0 }}>
        {loading && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 22, background: 'linear-gradient(145deg, var(--surface2) 0%, var(--bg-surface) 100%)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 16, padding: '20px 24px', marginBottom: 24 }}>
              <Skeleton width={64} height={64} radius={'50%'} />
              <div style={{ flex: 1 }}>
                <Skeleton width={130} height={11} style={{ marginBottom: 10 }} />
                <Skeleton width={220} height={12} />
              </div>
            </div>

            <div style={{ display: 'flex', gap: 16, marginBottom: 28, flexWrap: 'wrap' }}>
              {[0, 1, 2, 3].map(i => (
                <div key={i} style={{ flex: 1, minWidth: 140, background: 'linear-gradient(145deg, var(--surface2) 0%, var(--bg-surface) 100%)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 14, padding: '18px 22px' }}>
                  <Skeleton width={40} height={10} style={{ marginBottom: 12 }} />
                  <Skeleton width={50} height={38} style={{ marginBottom: 8 }} />
                  <Skeleton width={90} height={11} />
                </div>
              ))}
            </div>

            <div style={{ background: 'linear-gradient(145deg, var(--surface2) 0%, var(--bg-surface) 100%)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 16, padding: '28px 32px', marginBottom: 24 }}>
              <Skeleton width={180} height={13} style={{ marginBottom: 24 }} />
              {[0, 1, 2, 3].map(i => <Skeleton key={i} height={22} style={{ marginBottom: 14 }} />)}
            </div>

            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              {[0, 1, 2, 3].map(i => (
                <div key={i} style={{ flex: 1, minWidth: 220, background: 'linear-gradient(145deg, var(--surface2) 0%, var(--bg-surface) 100%)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 16, padding: '18px 20px 20px' }}>
                  <Skeleton width={60} height={38} style={{ marginBottom: 16 }} />
                  {[0, 1, 2].map(j => <Skeleton key={j} height={22} style={{ marginBottom: 8 }} />)}
                </div>
              ))}
            </div>
          </>
        )}
        {error   && <div style={{ padding: '16px 20px', background: 'var(--red-dim)', border: '1px solid rgba(248,81,73,0.2)', borderRadius: 12, color: 'var(--red)', fontSize: 13 }}>Failed to load: {error}</div>}

        {!loading && !error && depth && (
          <>
            <ReadinessCard readiness={readiness} />

            <div style={{ display: 'flex', gap: 16, marginBottom: 28, flexWrap: 'wrap' }}>
              {POSITIONS.map(pos => {
                const ids = depth[pos.key] || [];
                return (
                  <div key={pos.key} style={{ flex: 1, background: 'linear-gradient(145deg, var(--surface2) 0%, var(--bg-surface) 100%)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 14, padding: '18px 22px', position: 'relative', overflow: 'hidden', boxShadow: '0 4px 20px rgba(0,0,0,0.3)' }}>
                    <div style={{ position: 'absolute', top: -24, right: -24, width: 80, height: 80, background: `radial-gradient(circle, ${pos.colorHex}18 0%, transparent 70%)` }} />
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                      <div style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: '0.1em', padding: '2px 7px', borderRadius: 4, background: pos.dim, color: pos.color }}>{pos.abbr}</div>
                    </div>
                    <div style={{ fontFamily: 'Space Grotesk', fontSize: 38, fontWeight: 700, lineHeight: 1, color: pos.color, letterSpacing: '-1px', fontVariantNumeric: 'tabular-nums' }}>{ids.length}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 6 }}>{pos.plural} available</div>
                  </div>
                );
              })}
            </div>

            <div style={{ background: 'linear-gradient(145deg, var(--surface2) 0%, var(--bg-surface) 100%)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 16, padding: '28px 32px', marginBottom: 24, boxShadow: '0 4px 24px rgba(0,0,0,0.3)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24 }}>
                <div style={{ width: 3, height: 18, background: ACC, borderRadius: 2 }} />
                <div style={{ fontFamily: 'Space Grotesk', fontSize: 15, fontWeight: 600 }}>Availability by Position</div>
                <div style={{ fontSize: 10.5, color: 'var(--text-secondary)' }}>
                  {depth.total_players} players appeared in at least one match
                </div>
              </div>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={chartData} layout="vertical" margin={{ left: 10, right: 60, top: 0, bottom: 0 }} barCategoryGap={16} defaultIndex={undefined}>
                  <XAxis
                    type="number" domain={[0, chartMax]}
                    tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
                    axisLine={false} tickLine={false}
                  />
                  <YAxis
                    type="category" dataKey="position"
                    tick={{ fill: 'var(--text-secondary)', fontSize: 12, fontWeight: 500 }}
                    axisLine={false} tickLine={false} width={90}
                  />
                  <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} trigger="hover" />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={22}>
                    {chartData.map((entry, idx) => (
                      <Cell key={idx} fill={entry.colorHex} fillOpacity={0.85} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <div style={{ width: 3, height: 18, background: ACC, borderRadius: 2 }} />
              <div style={{ fontFamily: 'Space Grotesk', fontSize: 15, fontWeight: 600 }}>Position Breakdown</div>
            </div>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              {POSITIONS.map(pos => (
                <DepthCard
                  key={pos.key}
                  pos={pos}
                  players={depth[pos.key] || []}
                  atRiskIds={atRiskIds}
                  statusByPlayerId={statusByPlayerId}
                  isCoach={isCoach}
                  onStatusSaved={handleStatusSaved}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
