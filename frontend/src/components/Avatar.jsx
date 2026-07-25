import { POS_COLORS } from '../constants';

function initials(name) {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

// StatsBomb's open data has no player photography, and scraping images from
// elsewhere raises licensing and reliability problems. An initials avatar,
// color-coded by position (same palette as the position badge elsewhere in
// the app), is the honest substitute.
export default function Avatar({ name, pos, size = 28 }) {
  const c = POS_COLORS[pos] || { color: '#8B949E' };
  return (
    <div style={{
      width: size, height: size, borderRadius: size / 2.8, flexShrink: 0,
      background: c.color,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'Space Grotesk', fontWeight: 700, color: '#0D1117',
      fontSize: size * 0.36,
    }}>
      {initials(name)}
    </div>
  );
}
