// Shimmering placeholder block, reused by each page's loading state to
// approximate its real layout instead of a bare "Loading..." string.
// Reuses the existing `pulse` keyframe (index.css) rather than defining a
// second animation.
export default function Skeleton({ width = '100%', height = 16, radius = 8, style }) {
  return (
    <div
      style={{
        width, height, borderRadius: radius,
        background: 'rgba(255,255,255,0.06)',
        animation: 'pulse 1.4s ease-in-out infinite',
        ...style,
      }}
    />
  );
}
