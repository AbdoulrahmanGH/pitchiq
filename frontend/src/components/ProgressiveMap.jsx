import { useState, useEffect, useMemo } from 'react';
import { PitchMarkings } from './ShotMap';
import TeamToggle from './TeamToggle';
import Skeleton from './Skeleton';
import { getProgressiveActions } from '../services/api';

// Two-color scheme from the app's validated dark-surface chart palette
// (see ShotMap): passes blue, carries purple -- identity is also carried by
// line style (carries are dashed), so color is never the only signal.
const COLORS = { Pass: '#4E95E8', Carry: '#8E70EA' };

export default function ProgressiveMap({ matchId, homeTeam, awayTeam }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [teamId, setTeamId] = useState(homeTeam.id);
  const [hover, setHover] = useState(null);

  useEffect(() => {
    if (matchId == null) return;
    setData(null);
    setLoading(true);
    getProgressiveActions(matchId)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [matchId]);

  const actions = useMemo(
    () => (data?.actions || []).filter(a => a.team_id === teamId),
    [data, teamId],
  );
  const passCount = actions.filter(a => a.event_type === 'Pass').length;
  const carryCount = actions.filter(a => a.event_type === 'Carry').length;

  if (loading) return <Skeleton height={260} style={{ borderRadius: 10 }} />;
  if (!data || data.actions.length === 0) return null;

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8, gap: 10, flexWrap: 'wrap' }}>
        <TeamToggle
          teams={[{ id: homeTeam.id, name: homeTeam.name }, { id: awayTeam.id, name: awayTeam.name }]}
          value={teamId}
          onChange={setTeamId}
        />
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <svg width={16} height={8} aria-hidden><line x1={0} y1={4} x2={16} y2={4} stroke={COLORS.Pass} strokeWidth={2} /></svg>
            <span style={{ fontSize: 10.5, color: 'var(--text-secondary)' }}>Prog. passes ({passCount})</span>
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <svg width={16} height={8} aria-hidden><line x1={0} y1={4} x2={16} y2={4} stroke={COLORS.Carry} strokeWidth={2} strokeDasharray="3 2" /></svg>
            <span style={{ fontSize: 10.5, color: 'var(--text-secondary)' }}>Prog. carries ({carryCount})</span>
          </span>
        </div>
      </div>
      <div style={{ position: 'relative' }}>
        <svg
          viewBox="-2 -2 124 84"
          role="img"
          aria-label={`Progressive passes and carries, attacking right`}
          style={{ display: 'block', width: '100%', background: 'rgba(255,255,255,0.02)', borderRadius: 10 }}
        >
          <defs>
            <marker id="arrow-pass" viewBox="0 0 6 6" refX={5} refY={3} markerWidth={4.5} markerHeight={4.5} orient="auto-start-reverse">
              <path d="M0,0 L6,3 L0,6 Z" fill={COLORS.Pass} />
            </marker>
            <marker id="arrow-carry" viewBox="0 0 6 6" refX={5} refY={3} markerWidth={4.5} markerHeight={4.5} orient="auto-start-reverse">
              <path d="M0,0 L6,3 L0,6 Z" fill={COLORS.Carry} />
            </marker>
          </defs>
          <PitchMarkings />
          {actions.map((a, i) => {
            const isPass = a.event_type === 'Pass';
            const color = COLORS[a.event_type];
            const hovered = hover === i;
            return (
              <g key={i}
                 onMouseEnter={() => setHover(i)}
                 onMouseLeave={() => setHover(null)}>
                <line x1={a.x} y1={a.y} x2={a.end_x} y2={a.end_y}
                      stroke="transparent" strokeWidth={2.4} />
                <line
                  x1={a.x} y1={a.y} x2={a.end_x} y2={a.end_y}
                  stroke={color}
                  strokeWidth={hovered ? 0.9 : 0.5}
                  strokeOpacity={hovered ? 1 : a.completed ? 0.75 : 0.35}
                  strokeDasharray={isPass ? undefined : '2.2 1.4'}
                  markerEnd={`url(#arrow-${isPass ? 'pass' : 'carry'})`}
                />
              </g>
            );
          })}
        </svg>
        {hover != null && actions[hover] && (
          <div style={{
            position: 'absolute', top: 6, left: 6, pointerEvents: 'none',
            background: 'var(--surface3, #1C2333)', border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 8, padding: '6px 10px', boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
          }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
              {actions[hover].player_name}
            </span>
            <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
              {' '}· {actions[hover].minute + 1}&prime; · progressive {actions[hover].event_type.toLowerCase()}
              {actions[hover].event_type === 'Pass' && !actions[hover].completed ? ' (incomplete)' : ''}
            </span>
          </div>
        )}
      </div>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 6 }}>
        attacking &rarr; · same Wyscout rule as the season progressive counts · faded = incomplete
      </div>
    </div>
  );
}
