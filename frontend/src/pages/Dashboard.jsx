import { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, ReferenceLine, Tooltip, ResponsiveContainer } from 'recharts';
import { getTeamReadiness, getMatchesSummary, getSquadDepth, getTeamInfo, getPlayerPerformance } from '../services/api';
import { POS_ABBREV, POS_COLORS } from '../constants';
import Skeleton from '../components/Skeleton';
import Avatar from '../components/Avatar';
import CircularProgress from '../components/CircularProgress';

const RECENT_MINUTES_MAX = 270; // 3 full 90-minute matches -- matches the "last 3 fixtures" workload window

const ACC = '#FF6B35';

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
          <div style={{ fontSize: 42, fontWeight: 700, fontFamily: 'Space Grotesk', lineHeight: 1, color: 'var(--text-primary)', letterSpacing: '-1px', fontVariantNumeric: 'tabular-nums' }}>{value}</div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 6 }}>{sub}</div>
        </div>
        {children}
      </div>
    </div>
  );
}

function FatigueCard({ player, positionByPlayerId }) {
  const [hov, setHov] = useState(false);
  const name = player.name || player.player_id;
  const posLabel = POS_ABBREV[positionByPlayerId[player.player_id]] || '???';
  const posStyle = POS_COLORS[posLabel] || { color: 'var(--text-muted)', bg: 'rgba(255,255,255,0.06)' };
  const num = player.player_id;

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
            <div style={{ fontSize: 9.5, color: '#8B949E', letterSpacing: '0.08em', marginBottom: 2 }}>REST DAYS</div>
            <div style={{ fontFamily: 'Space Grotesk', fontSize: 13, fontWeight: 700, color: '#C9D1D9', fontVariantNumeric: 'tabular-nums' }}>{player.rest_days}</div>
          </div>
          <div>
            <div style={{ fontSize: 9.5, color: '#8B949E', letterSpacing: '0.08em', marginBottom: 2 }}>RECENT MINS</div>
            <div style={{ fontFamily: 'Space Grotesk', fontSize: 13, fontWeight: 700, color: '#C9D1D9', fontVariantNumeric: 'tabular-nums' }}>{player.recent_minutes}</div>
          </div>
        </div>
      </div>
      <div style={{ height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${Math.min((player.recent_minutes / RECENT_MINUTES_MAX) * 100, 100)}%`, background: 'linear-gradient(90deg, var(--red), var(--red))', borderRadius: 2 }} />
      </div>
    </div>
  );
}

function LastMatchCard({ match, teamName }) {
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
            {teamName} <span style={{ color: 'var(--text-muted)', fontWeight: 400, margin: '0 6px' }}>vs</span> {match.opponent}
          </div>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: 52, fontWeight: 700, letterSpacing: '-2px', lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
            <span style={{ color: match.result !== 'loss' ? 'var(--text-primary)' : 'rgba(230,237,243,0.5)' }}>{match.goals_scored}</span>
            <span style={{ color: 'var(--text-muted)', margin: '0 10px', fontWeight: 300, fontSize: 36 }}>–</span>
            <span style={{ color: match.result === 'loss' ? 'rgba(248,81,73,0.7)' : 'rgba(230,237,243,0.35)' }}>{match.goals_conceded}</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 10, letterSpacing: '0.06em' }}>
            {dateStr} · {match.stadium || (isHome ? 'Home' : 'Away')} · {isHome ? 'HOME' : 'AWAY'}
          </div>
        </div>
        {match.possession_pct != null && (
          <div style={{ padding: '12px 16px', background: 'rgba(0,0,0,0.2)', borderRadius: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: 9.5, color: 'var(--text-muted)', letterSpacing: '0.08em' }}>POSSESSION</span>
              <span style={{ fontFamily: 'Space Grotesk', fontSize: 14, fontWeight: 700, color: ACC, fontVariantNumeric: 'tabular-nums' }}>{match.possession_pct.toFixed(1)}%</span>
            </div>
            <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{ width: `${match.possession_pct}%`, height: '100%', background: ACC, borderRadius: 2 }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
              <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>{teamName}</span>
              <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>OPP {(100 - match.possession_pct).toFixed(1)}%</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function PpdaTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const m = payload[0].payload;
  return (
    <div style={{ background: '#1C2333', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, padding: '7px 10px', boxShadow: '0 4px 16px rgba(0,0,0,0.4)' }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>vs {m.opponent}</div>
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2, fontVariantNumeric: 'tabular-nums' }}>
        PPDA {m.ppda.toFixed(1)} · {new Date(m.date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })}
      </div>
    </div>
  );
}

// Pressing intensity across the season: one point per match, ordered by
// date. PPDA is opponent passes allowed per defensive action -- LOWER means
// a more aggressive press, so dips in this line are the high-press matches.
function PpdaTimeline({ matches, seasonAvg }) {
  const data = [...matches]
    .filter(m => m.ppda != null)
    .sort((a, b) => new Date(a.date) - new Date(b.date))
    .map((m, i) => ({ n: i + 1, date: m.date, opponent: m.opponent, ppda: m.ppda }));
  if (data.length === 0) return null;

  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
        <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
          Pressing Intensity · PPDA by match
        </div>
        <div style={{ fontSize: 9.5, color: 'var(--text-muted)' }}>lower = stronger press</div>
      </div>
      <ResponsiveContainer width="100%" height={120}>
        <LineChart data={data} margin={{ top: 4, right: 6, bottom: 0, left: -26 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
          <XAxis
            dataKey="n"
            tick={{ fill: 'var(--text-muted)', fontSize: 9 }}
            tickLine={false} axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
            ticks={[1, 10, 19, 28, data.length]}
          />
          <YAxis
            tick={{ fill: 'var(--text-muted)', fontSize: 9 }}
            tickLine={false} axisLine={false} width={54}
            domain={['auto', 'auto']} tickCount={4}
          />
          {seasonAvg != null && (
            <ReferenceLine y={seasonAvg} stroke="rgba(255,255,255,0.22)" strokeDasharray="4 3" />
          )}
          <Tooltip content={<PpdaTooltip />} cursor={{ stroke: 'rgba(255,255,255,0.15)' }} />
          <Line
            type="monotone" dataKey="ppda"
            stroke={ACC} strokeWidth={2} dot={false}
            activeDot={{ r: 3.5, fill: ACC, strokeWidth: 0 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
      <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 2, textAlign: 'right' }}>
        match number · dashed line = season avg
      </div>
    </div>
  );
}

function SeasonSnapshotCard({ teamInfo, topPerformers, positionByPlayerId, matches }) {
  const ppda = teamInfo?.season_ppda_avg;
  const tilt = teamInfo?.season_field_tilt_avg;
  return (
    <div style={{ background: 'linear-gradient(145deg, #1C2333 0%, #161B22 100%)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 16, padding: '20px 22px 22px', flex: '0 0 340px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <div style={{ width: 3, height: 18, background: ACC, borderRadius: 2 }} />
        <div style={{ fontFamily: 'Space Grotesk', fontSize: 15, fontWeight: 600 }}>Season Snapshot</div>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
        <div style={{ flex: 1, background: 'rgba(0,0,0,0.2)', borderRadius: 10, padding: '12px 14px' }}>
          <div style={{ fontSize: 9, color: 'var(--text-muted)', letterSpacing: '0.08em', marginBottom: 5 }}>PPDA · SEASON AVG</div>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: 21, fontWeight: 700, color: ACC, fontVariantNumeric: 'tabular-nums' }}>
            {ppda != null ? ppda.toFixed(1) : '—'}
          </div>
        </div>
        <div style={{ flex: 1, background: 'rgba(0,0,0,0.2)', borderRadius: 10, padding: '12px 14px' }}>
          <div style={{ fontSize: 9, color: 'var(--text-muted)', letterSpacing: '0.08em', marginBottom: 5 }}>FIELD TILT · SEASON AVG</div>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: 21, fontWeight: 700, color: ACC, fontVariantNumeric: 'tabular-nums' }}>
            {tilt != null ? `${tilt.toFixed(1)}%` : '—'}
          </div>
        </div>
      </div>

      <PpdaTimeline matches={matches} seasonAvg={ppda} />

      {topPerformers.length > 0 && (
        <>
          <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 10 }}>
            Top Performers · xG
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {topPerformers.map((p, i) => (
              <div key={p.player_id} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ width: 14, fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textAlign: 'center', flexShrink: 0 }}>{i + 1}</div>
                <Avatar name={p.name} pos={POS_ABBREV[positionByPlayerId[p.player_id]]} size={28} />
                <div style={{ flex: 1, minWidth: 0, fontSize: 12.5, fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {p.name}
                </div>
                <div style={{ fontFamily: 'Space Grotesk', fontSize: 13, fontWeight: 700, color: 'var(--green)', fontVariantNumeric: 'tabular-nums', flexShrink: 0 }}>
                  {p.xg.toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
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
          <div style={{ fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: 18, color: c, fontVariantNumeric: 'tabular-nums' }}>{v}</div>
          <div style={{ fontSize: 9, color: 'var(--text-muted)', letterSpacing: '0.1em' }}>{l}</div>
        </div>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const [readiness,   setReadiness]   = useState(null);
  const [matches,     setMatches]     = useState([]);
  const [depth,       setDepth]       = useState(null);
  const [teamInfo,    setTeamInfo]    = useState(null);
  const [performance, setPerformance] = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState(null);

  useEffect(() => {
    Promise.all([getTeamReadiness(), getMatchesSummary(), getSquadDepth(), getTeamInfo(), getPlayerPerformance()])
      .then(([r, m, d, t, perf]) => { setReadiness(r); setMatches(m); setDepth(d); setTeamInfo(t); setPerformance(perf); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  // Real position per player, from /api/players/depth's buckets -- same fix
  // as Players.jsx; the old PLAYER_POSITIONS map used v1 string ids and
  // never matched real StatsBomb integer ids, so every fatigue-risk badge
  // silently showed "???".
  const positionByPlayerId = {};
  if (depth) {
    for (const bucket of ['Goalkeeper', 'Defender', 'Midfielder', 'Forward']) {
      for (const p of depth[bucket] || []) positionByPlayerId[p.id] = bucket;
    }
  }

  const teamName = teamInfo?.team_name ?? '—';
  const leagueLabel = teamInfo ? `${teamInfo.competition_name} ${teamInfo.season_name}` : '';

  const lastMatch = matches.length
    ? [...matches].sort((a, b) => new Date(b.date) - new Date(a.date))[0]
    : null;

  const topPerformers = [...performance]
    .filter(p => p.team_name === teamInfo?.team_name && (p.xg || 0) > 0)
    .sort((a, b) => (b.xg || 0) - (a.xg || 0))
    .slice(0, 3);

  const wins   = matches.filter(m => m.result === 'win').length;
  const draws  = matches.filter(m => m.result === 'draw').length;
  const losses = matches.filter(m => m.result === 'loss').length;
  const gf = matches.reduce((s, m) => s + m.goals_scored, 0);
  const ga = matches.reduce((s, m) => s + m.goals_conceded, 0);

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 20px', minHeight: 60, borderBottom: '1px solid rgba(255,255,255,0.05)', background: 'rgba(13,17,23,0.7)', backdropFilter: 'blur(12px)', flexShrink: 0, flexWrap: 'wrap', gap: 8 }}>
        <div>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: 18, fontWeight: 600 }}>Squad Dashboard</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>{leagueLabel}</div>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 20px 40px', minWidth: 0 }}>
        {loading && (
          <>
            <div style={{ display: 'flex', gap: 18, marginBottom: 24, flexWrap: 'wrap' }}>
              {[0, 1, 2].map(i => (
                <div key={i} style={{ background: 'linear-gradient(145deg, #1C2333 0%, #161B22 100%)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 16, padding: '24px 26px', flex: 1, minWidth: 220 }}>
                  <Skeleton width={100} height={11} style={{ marginBottom: 14 }} />
                  <Skeleton width={140} height={42} style={{ marginBottom: 8 }} />
                  <Skeleton width={180} height={12} />
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap' }}>
              <div style={{ background: 'linear-gradient(145deg, #1C2333 0%, #161B22 100%)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 16, padding: '20px 24px', flex: '0 0 340px' }}>
                <Skeleton width={90} height={11} style={{ marginBottom: 18 }} />
                <Skeleton width={160} height={16} style={{ margin: '0 auto 14px' }} />
                <Skeleton width={120} height={44} style={{ margin: '0 auto' }} />
              </div>
              <div style={{ flex: 1, background: 'linear-gradient(145deg, #1C2333 0%, #161B22 100%)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 16, padding: 20 }}>
                {[0, 1, 2, 3, 4].map(i => <Skeleton key={i} height={38} style={{ marginBottom: 10 }} />)}
              </div>
            </div>
          </>
        )}
        {error && (
          <div style={{ padding: '16px 20px', background: 'var(--red-dim)', border: '1px solid rgba(248,81,73,0.2)', borderRadius: 12, color: 'var(--red)', fontSize: 13 }}>
            Failed to load data: {error}
          </div>
        )}
        {!loading && !error && (
          <>
            <div style={{ display: 'flex', gap: 18, marginBottom: 24, flexWrap: 'wrap' }}>
              <StatCard title="Squad Readiness" value={readiness?.readiness_score ?? '—'} sub="Overall squad fitness index">
                <CircularProgress value={readiness?.readiness_score ?? 0} />
              </StatCard>
              <StatCard
                title="Players Available"
                value={depth ? `${depth.total_players - (readiness?.at_risk_players?.length ?? 0)}/${depth.total_players}` : '—'}
                sub="Squad total minus flagged fatigue risk"
              />
              <StatCard title={teamInfo?.competition_name ?? 'League'} value={`${wins}W · ${draws}D · ${losses}L`} sub={`Last ${matches.length} matches · GF ${gf}  GA ${ga}`}>
                <RecordDisplay matches={matches} />
              </StatCard>
            </div>

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
                    <FatigueCard key={p.player_id} player={p} positionByPlayerId={positionByPlayerId} />
                  ))}
                </div>
              </div>
            )}

            {/* alignItems: flex-start -- without it the flex row stretches this
                column to match Recent Form's height (the full un-scrolled
                match list), leaving a large blank rectangle below whatever
                short content sits in this column. Season Snapshot fills that
                space with real content; flex-start keeps both columns at
                their own natural height instead of one stretching to match
                the other. */}
            <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', alignItems: 'flex-start' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 18, flex: '0 0 340px' }}>
                {lastMatch && <LastMatchCard match={lastMatch} teamName={teamName} />}
                <SeasonSnapshotCard teamInfo={teamInfo} topPerformers={topPerformers} positionByPlayerId={positionByPlayerId} matches={matches} />
              </div>

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
                          <span style={{ opacity: isHome ? 1 : 0.6 }}>{teamName}</span>
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
