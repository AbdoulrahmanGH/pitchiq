import Modal, { ModalCloseButton } from './Modal';
import Avatar from './Avatar';
import ScoutingNotes from './ScoutingNotes';
import { POS_COLORS } from '../constants';

const POS_FULL = { GK: 'Goalkeeper', DEF: 'Defender', MID: 'Midfielder', FWD: 'Forward' };

function StatTile({ label, value, color }) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: 12, padding: '14px 16px',
    }}>
      <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontFamily: 'Space Grotesk', fontSize: 24, fontWeight: 700, color: color || 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </div>
    </div>
  );
}

export default function PlayerModal({ player, open, onClose }) {
  if (!player) return null;

  const posColor = POS_COLORS[player.pos] || {};
  const progressiveActions = (player.total_progressive_passes || 0) + (player.total_progressive_carries || 0);

  return (
    <Modal open={open} onClose={onClose} maxWidth={560}>
      <div style={{ padding: '20px 22px', display: 'flex', alignItems: 'center', gap: 14, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <Avatar name={player.name} pos={player.pos} size={52} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: 19, fontWeight: 700, color: 'var(--text-primary)' }}>
            {player.name}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 3 }}>
            <span style={{
              fontSize: 9.5, fontWeight: 700, letterSpacing: '0.08em', padding: '2px 7px', borderRadius: 4,
              background: posColor.bg, color: posColor.color,
            }}>
              {player.pos}
            </span>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{POS_FULL[player.pos] || 'Position unresolved'}</span>
          </div>
        </div>
        <ModalCloseButton onClick={onClose} />
      </div>

      <div style={{ padding: 22 }}>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 14 }}>
          Season stats · {player.matches_played} {player.matches_played === 1 ? 'match' : 'matches'} played
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 12 }}>
          <StatTile label="Minutes"            value={player.total_minutes} />
          <StatTile label="Goals"               value={player.total_goals}   color="#FF6B35" />
          <StatTile label="Assists"             value={player.total_assists} color="var(--blue)" />
          <StatTile label="xG"                  value={player.xg} />
          <StatTile label="xA"                  value={player.xa} />
          <StatTile label="Passes"              value={player.total_passes_attempted} />
          <StatTile label="Progressive Actions" value={progressiveActions} color="var(--purple)" />
          <StatTile label="Tackles"             value={player.total_tackles} />
          <StatTile label="Pressures"           value={player.total_pressures} />
          <StatTile label="Pressure Regains"    value={player.total_pressure_regains} color="var(--green)" />
        </div>
      </div>

      <ScoutingNotes playerId={player.player_id} />
    </Modal>
  );
}
