import { useState, useEffect, useMemo } from 'react';
import { PitchMarkings } from './ShotMap';
import TeamToggle from './TeamToggle';
import Skeleton from './Skeleton';
import { getPassNetwork } from '../services/api';

const ACC = '#FF5A1F';

// Node radius in pitch units, gently scaled by completed-pass volume so the
// hub players read as hubs without swallowing the pitch.
function nodeRadius(passes) {
  return 1.6 + 1.4 * Math.sqrt(passes / 60);
}

// Edge width in pitch units: 3 passes (the threshold) draws thin, the
// biggest combinations cap out before they occlude their neighbors.
function edgeWidth(count) {
  return Math.min(0.4 + 0.22 * (count - 3), 2.4);
}

function shortName(node) {
  if (node.nickname) return node.nickname;
  const parts = (node.name || '').split(' ');
  return parts.length > 1 ? parts[1] : parts[0] || node.player_id;
}

export default function PassNetwork({ matchId, homeTeam, awayTeam }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [teamId, setTeamId] = useState(homeTeam.id);
  const [hover, setHover] = useState(null);

  useEffect(() => {
    if (matchId == null) return;
    setData(null);
    setLoading(true);
    getPassNetwork(matchId)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [matchId]);

  const team = useMemo(
    () => data?.teams?.find(t => t.team_id === teamId),
    [data, teamId],
  );
  const nodesById = useMemo(() => {
    const m = {};
    for (const n of team?.nodes || []) m[n.player_id] = n;
    return m;
  }, [team]);

  if (loading) return <Skeleton height={260} style={{ borderRadius: 10 }} />;
  if (!data || data.teams.length === 0) return null;

  const teamName = (id) => (id === homeTeam.id ? homeTeam.name : awayTeam.name);

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8, gap: 10, flexWrap: 'wrap' }}>
        <TeamToggle
          teams={[{ id: homeTeam.id, name: homeTeam.name }, { id: awayTeam.id, name: awayTeam.name }]}
          value={teamId}
          onChange={setTeamId}
        />
        <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
          attacking &rarr; · line = 3+ completed passes · thickness = volume
        </span>
      </div>
      {!team ? (
        <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '14px 0' }}>
          No completed passes recorded for {teamName(teamId)} in this match.
        </div>
      ) : (
        <div style={{ position: 'relative' }}>
          <svg
            viewBox="-2 -2 124 84"
            role="img"
            aria-label={`Pass network for ${teamName(teamId)}, attacking right`}
            style={{ display: 'block', width: '100%', background: 'rgba(255,255,255,0.02)', borderRadius: 10 }}
          >
            <PitchMarkings />
            {team.edges.map((e, i) => {
              const a = nodesById[e.a], b = nodesById[e.b];
              if (!a || !b) return null;
              return (
                <line
                  key={i}
                  x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                  stroke={hover?.type === 'edge' && hover.i === i ? ACC : 'rgba(230,237,243,0.28)'}
                  strokeWidth={edgeWidth(e.count)}
                  strokeLinecap="round"
                  onMouseEnter={ev => setHover({ type: 'edge', i, e, cx: ev.clientX, cy: ev.clientY })}
                  onMouseLeave={() => setHover(null)}
                />
              );
            })}
            {team.nodes.map(n => (
              <g key={n.player_id}
                 onMouseEnter={ev => setHover({ type: 'node', n, cx: ev.clientX, cy: ev.clientY })}
                 onMouseLeave={() => setHover(null)}>
                <circle cx={n.x} cy={n.y} r={Math.max(nodeRadius(n.passes), 2.6)} fill="transparent" />
                <circle
                  cx={n.x} cy={n.y} r={nodeRadius(n.passes)}
                  fill={ACC} fillOpacity={0.92}
                  stroke="rgba(13,17,23,0.7)" strokeWidth={0.35}
                />
                <text
                  x={n.x} y={n.y + nodeRadius(n.passes) + 2.6}
                  textAnchor="middle"
                  style={{ fontSize: 2.6, fill: 'rgba(230,237,243,0.75)', fontWeight: 600 }}
                >
                  {shortName(n)}
                </text>
              </g>
            ))}
          </svg>
          {hover && (
            <HoverTip hover={hover} nodesById={nodesById} />
          )}
        </div>
      )}
    </div>
  );
}

function HoverTip({ hover, nodesById }) {
  // position relative to the svg wrapper using the last mouse event coords
  const wrapper = { position: 'absolute', top: 6, left: 6, pointerEvents: 'none' };
  const box = {
    display: 'inline-block', background: 'var(--surface3)',
    border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8,
    padding: '6px 10px', boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
  };
  if (hover.type === 'node') {
    return (
      <div style={wrapper}>
        <div style={box}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{hover.n.name}</span>
          <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}> · {hover.n.passes} completed passes</span>
        </div>
      </div>
    );
  }
  const a = nodesById[hover.e.a], b = nodesById[hover.e.b];
  return (
    <div style={wrapper}>
      <div style={box}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
          {a ? shortName(a) : hover.e.a} &harr; {b ? shortName(b) : hover.e.b}
        </span>
        <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}> · {hover.e.count} passes</span>
      </div>
    </div>
  );
}
