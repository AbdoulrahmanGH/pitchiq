// Small segmented control for the match-modal pitch visuals: raw StatsBomb
// coordinates are always in the acting team's own attacking frame (toward
// x=120), so a single-team view needs no mirroring -- the toggle switches
// which team's actions are drawn.
export default function TeamToggle({ teams, value, onChange }) {
  return (
    <div style={{ display: 'inline-flex', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, padding: 2 }}>
      {teams.map(t => {
        const active = t.id === value;
        return (
          <button
            key={t.id}
            onClick={() => onChange(t.id)}
            style={{
              border: 'none', cursor: 'pointer', borderRadius: 6,
              padding: '4px 10px', fontSize: 10.5, fontWeight: 600,
              letterSpacing: '0.02em',
              background: active ? 'rgba(255,107,53,0.16)' : 'transparent',
              color: active ? '#FF6B35' : 'var(--text-secondary)',
              transition: 'background 0.15s, color 0.15s',
            }}
          >
            {t.name}
          </button>
        );
      })}
    </div>
  );
}
