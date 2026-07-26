import { useState } from 'react';

// StatsBomb pitch: 120x80 yards. Raw event coordinates are always in the
// acting team's own attacking frame -- every shot, either team, either half,
// points toward x=120 (verified empirically: both teams' raw shot x >= 86
// across full matches). So there is no period-based flipping to do; for a
// shared two-team display we keep the home team as-is (attacking the right
// goal) and mirror the away team (attacking the left goal).
export function displayPosition(shot, homeTeamId) {
  if (shot.team_id === homeTeamId) return { x: shot.x, y: shot.y };
  return { x: 120 - shot.x, y: 80 - shot.y };
}

// Raw StatsBomb shot outcomes collapsed to the four visual categories.
export function outcomeCategory(outcome) {
  if (outcome === 'Goal') return 'goal';
  if (outcome === 'Blocked') return 'blocked';
  if (outcome === 'Saved' || outcome === 'Saved to Post') return 'saved';
  return 'off'; // Off T, Wayward, Post, Saved Off Target
}

// Validated against the app's dark surface (#161B22) with the dataviz
// six-checks palette validator: lightness band, chroma floor, CVD
// separation, normal-vision floor, contrast all pass. Identity is not
// color-alone: goals get a white ring, off-target markers are hollow.
const OUTCOMES = {
  goal:    { color: '#E85D2E', label: 'Goal' },
  saved:   { color: '#4E95E8', label: 'Saved' },
  blocked: { color: '#BE8A18', label: 'Blocked' },
  off:     { color: '#8E70EA', label: 'Off target' },
};

// Marker radius in pitch units, scaled by xG (area ~ xG).
function radiusFor(xg) {
  return 1.2 + 2.4 * Math.sqrt(Math.max(0, xg || 0));
}

function PitchMarkings() {
  const line = { fill: 'none', stroke: 'rgba(255,255,255,0.14)', strokeWidth: 0.35 };
  return (
    <g>
      <rect x={0} y={0} width={120} height={80} {...line} />
      <line x1={60} y1={0} x2={60} y2={80} {...line} />
      <circle cx={60} cy={40} r={10} {...line} />
      {/* penalty areas, six-yard boxes, spots, goals -- both ends */}
      <rect x={0} y={18} width={18} height={44} {...line} />
      <rect x={102} y={18} width={18} height={44} {...line} />
      <rect x={0} y={30} width={6} height={20} {...line} />
      <rect x={114} y={30} width={6} height={20} {...line} />
      <circle cx={12} cy={40} r={0.5} fill="rgba(255,255,255,0.25)" stroke="none" />
      <circle cx={108} cy={40} r={0.5} fill="rgba(255,255,255,0.25)" stroke="none" />
      <rect x={-1.2} y={36} width={1.2} height={8} {...line} />
      <rect x={120} y={36} width={1.2} height={8} {...line} />
    </g>
  );
}

function ShotMarker({ shot, pos, onHover, onLeave }) {
  const cat = outcomeCategory(shot.outcome);
  const { color } = OUTCOMES[cat];
  const r = radiusFor(shot.xg);
  const isGoal = cat === 'goal';
  const isOff = cat === 'off';
  return (
    <g
      onMouseEnter={e => onHover(shot, e)}
      onMouseLeave={onLeave}
      style={{ cursor: 'default' }}
    >
      {/* invisible enlarged hit target behind the visible mark */}
      <circle cx={pos.x} cy={pos.y} r={Math.max(r, 2.4)} fill="transparent" stroke="none" />
      <circle
        cx={pos.x}
        cy={pos.y}
        r={r}
        fill={isOff ? 'none' : color}
        fillOpacity={isGoal ? 1 : 0.85}
        stroke={isOff ? color : isGoal ? '#FFFFFF' : 'rgba(13,17,23,0.6)'}
        strokeWidth={isOff ? 0.55 : isGoal ? 0.5 : 0.3}
      />
    </g>
  );
}

function Legend() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 14, marginTop: 10 }}>
      {Object.entries(OUTCOMES).map(([key, { color, label }]) => (
        <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <svg width={12} height={12} viewBox="0 0 12 12" aria-hidden>
            <circle
              cx={6} cy={6} r={4.2}
              fill={key === 'off' ? 'none' : color}
              stroke={key === 'off' ? color : key === 'goal' ? '#FFFFFF' : 'none'}
              strokeWidth={key === 'off' ? 1.4 : 1}
            />
          </svg>
          <span style={{ fontSize: 10.5, color: 'var(--text-secondary)' }}>{label}</span>
        </div>
      ))}
      <span style={{ fontSize: 10.5, color: 'var(--text-muted)', marginLeft: 'auto' }}>
        Marker size = xG
      </span>
    </div>
  );
}

export default function ShotMap({ shots, homeTeam, awayTeam }) {
  const [hover, setHover] = useState(null);

  if (!shots || shots.length === 0) return null;

  const onHover = (shot, e) => {
    const box = e.currentTarget.closest('svg').getBoundingClientRect();
    setHover({
      shot,
      left: e.clientX - box.left,
      top: e.clientY - box.top,
      flip: e.clientX - box.left > box.width / 2,
    });
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)' }}>
          &larr; {awayTeam.name} shots
        </span>
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)' }}>
          {homeTeam.name} shots &rarr;
        </span>
      </div>
      <div style={{ position: 'relative' }}>
        <svg
          viewBox="-2 -2 124 84"
          role="img"
          aria-label={`Shot map: ${homeTeam.name} attacking right, ${awayTeam.name} attacking left`}
          style={{ display: 'block', width: '100%', background: 'rgba(255,255,255,0.02)', borderRadius: 10 }}
        >
          <PitchMarkings />
          {shots.map((shot, i) => (
            <ShotMarker
              key={i}
              shot={shot}
              pos={displayPosition(shot, homeTeam.id)}
              onHover={onHover}
              onLeave={() => setHover(null)}
            />
          ))}
        </svg>
        {hover && (
          <div
            style={{
              position: 'absolute',
              left: hover.left,
              top: hover.top - 10,
              transform: `translate(${hover.flip ? '-100%' : '8px'}, -100%)`,
              background: 'var(--surface3)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '7px 10px',
              pointerEvents: 'none',
              whiteSpace: 'nowrap',
              boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
              zIndex: 5,
            }}
          >
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
              {hover.shot.player_name}
              <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}> · {hover.shot.minute + 1}&prime;</span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
              {OUTCOMES[outcomeCategory(hover.shot.outcome)].label}
              {' · '}xG {(hover.shot.xg ?? 0).toFixed(2)}
              {' · '}{hover.shot.team_id === homeTeam.id ? homeTeam.name : awayTeam.name}
            </div>
          </div>
        )}
      </div>
      <Legend />
    </div>
  );
}
