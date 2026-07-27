import { useState, useEffect } from 'react';
import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  ResponsiveContainer, Tooltip,
} from 'recharts';
import Skeleton from './Skeleton';
import { getPlayerRadar } from '../services/api';

const ACC = '#FF6B35';

// Percentile-based radar: every axis is 0-100 by construction, so the six
// per-90 metrics share one scale without any per-axis normalization tricks.
// Percentiles come precomputed from the backend (Python, vs players sharing
// the same primary_position) -- this component only draws them.
function RadarTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const m = payload[0].payload;
  return (
    <div style={{
      background: 'var(--surface3, #1C2333)', border: '1px solid rgba(255,255,255,0.1)',
      borderRadius: 8, padding: '7px 10px', boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
    }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
        {m.label} <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>/90</span>
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2, fontVariantNumeric: 'tabular-nums' }}>
        {m.value.toFixed(2)} per 90 · {Math.round(m.percentile)}th percentile
      </div>
    </div>
  );
}

export default function PlayerRadar({ playerId }) {
  const [radar, setRadar] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (playerId == null) return;
    setRadar(null);
    setLoading(true);
    getPlayerRadar(playerId)
      .then(setRadar)
      .catch(() => setRadar(null)) // 404 (no minutes / no position): hide quietly
      .finally(() => setLoading(false));
  }, [playerId]);

  if (loading) return <Skeleton height={220} style={{ borderRadius: 12 }} />;
  if (!radar) return null;

  const data = radar.metrics.map(m => ({ ...m }));

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 2 }}>
        <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
          Per-90 Profile
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
          percentile vs {radar.pool_size} {radar.primary_position}s
        </div>
      </div>
      <ResponsiveContainer width="100%" height={230}>
        <RadarChart data={data} outerRadius="72%" margin={{ top: 12, right: 30, bottom: 4, left: 30 }}>
          <PolarGrid stroke="rgba(255,255,255,0.08)" />
          <PolarAngleAxis
            dataKey="label"
            tick={{ fill: 'var(--text-secondary)', fontSize: 10.5 }}
          />
          <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
          <Radar
            dataKey="percentile"
            stroke={ACC}
            strokeWidth={2}
            fill={ACC}
            fillOpacity={0.18}
            dot={{ r: 2.5, fill: ACC, strokeWidth: 0 }}
            isAnimationActive={false}
          />
          <Tooltip content={<RadarTooltip />} cursor={false} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
