import { useState, useEffect } from 'react';
import Modal, { ModalCloseButton } from './Modal';
import Avatar from './Avatar';
import Skeleton from './Skeleton';
import ShotMap from './ShotMap';
import { getMatchDetail } from '../services/api';

function formatDate(dateStr) {
  if (!dateStr) return '';
  const [year, month, day] = dateStr.split('-');
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${months[parseInt(month, 10) - 1]} ${day}, ${year}`;
}

function LineupRow({ player }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
      <Avatar name={player.name} pos={undefined} size={26} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {player.name}
        </div>
        {player.position && <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{player.position}</div>}
      </div>
      {player.goals > 0 && (
        <span
          title={`${player.goals} goal${player.goals > 1 ? 's' : ''}`}
          style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: '0.04em', padding: '2px 6px', borderRadius: 4, background: 'var(--orange-dim)', color: 'var(--orange)' }}
        >
          G{player.goals > 1 ? ` ×${player.goals}` : ''}
        </span>
      )}
      {player.assists > 0 && (
        <span
          title={`${player.assists} assist${player.assists > 1 ? 's' : ''}`}
          style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: '0.04em', padding: '2px 6px', borderRadius: 4, background: 'var(--blue-dim)', color: 'var(--blue)' }}
        >
          A{player.assists > 1 ? ` ×${player.assists}` : ''}
        </span>
      )}
    </div>
  );
}

function MetricTile({ label, homeVal, awayVal, homeTeam, awayTeam, suffix, lowerIsBetter }) {
  if (homeVal == null && awayVal == null) return null;
  const homeBetter = homeVal != null && awayVal != null && homeVal !== awayVal &&
    (lowerIsBetter ? homeVal < awayVal : homeVal > awayVal);
  const awayBetter = homeVal != null && awayVal != null && homeVal !== awayVal &&
    (lowerIsBetter ? awayVal < homeVal : awayVal > homeVal);
  const fmt = (v) => v == null ? '—' : `${v.toFixed(1)}${suffix || ''}`;
  return (
    <div style={{ flex: 1, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12, padding: '12px 16px' }}>
      <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 10, textAlign: 'center' }}>
        {label}
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: 19, fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: homeBetter ? 'var(--green)' : 'var(--text-primary)' }}>
            {fmt(homeVal)}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {homeTeam.name}
          </div>
        </div>
        <div style={{ minWidth: 0, textAlign: 'right' }}>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: 19, fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: awayBetter ? 'var(--green)' : 'var(--text-primary)' }}>
            {fmt(awayVal)}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {awayTeam.name}
          </div>
        </div>
      </div>
    </div>
  );
}

function TeamMetrics({ homeTeam, awayTeam }) {
  if (homeTeam.ppda == null && awayTeam.ppda == null &&
      homeTeam.field_tilt_pct == null && awayTeam.field_tilt_pct == null) {
    return null;
  }
  return (
    <div style={{ display: 'flex', gap: 12 }}>
      <MetricTile
        label="PPDA (pressing intensity)"
        homeVal={homeTeam.ppda} awayVal={awayTeam.ppda}
        homeTeam={homeTeam} awayTeam={awayTeam}
        lowerIsBetter
      />
      <MetricTile
        label="Field Tilt"
        homeVal={homeTeam.field_tilt_pct} awayVal={awayTeam.field_tilt_pct}
        homeTeam={homeTeam} awayTeam={awayTeam}
        suffix="%"
      />
    </div>
  );
}

function TeamColumn({ team }) {
  return (
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>{team.name}</div>
        <div style={{ fontFamily: 'Space Grotesk', fontSize: 22, fontWeight: 700, color: 'var(--text-primary)' }}>{team.score}</div>
      </div>
      {team.lineup.length === 0 ? (
        <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '12px 0' }}>No lineup data available for this match.</div>
      ) : (
        team.lineup.map(p => <LineupRow key={p.player_id} player={p} />)
      )}
    </div>
  );
}

export default function MatchModal({ matchId, open, onClose }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!open || matchId == null) return;
    setDetail(null);
    setError(null);
    setLoading(true);
    getMatchDetail(matchId)
      .then(setDetail)
      .catch(e => setError(e.status === 404 ? 'This match could not be found.' : 'Failed to load match details.'))
      .finally(() => setLoading(false));
  }, [open, matchId]);

  return (
    <Modal open={open} onClose={onClose} maxWidth={680}>
      <div style={{ padding: '20px 22px', display: 'flex', alignItems: 'center', gap: 14, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: 17, fontWeight: 700, color: 'var(--text-primary)' }}>
            Match Detail
          </div>
          {detail && (
            <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 2 }}>
              {formatDate(detail.date)} · {detail.stadium || 'Venue unknown'}
            </div>
          )}
        </div>
        <ModalCloseButton onClick={onClose} />
      </div>

      <div style={{ padding: 22 }}>
        {loading && (
          <div style={{ display: 'flex', gap: 24 }}>
            {[0, 1].map(i => (
              <div key={i} style={{ flex: 1 }}>
                <Skeleton width={100} height={14} style={{ marginBottom: 14 }} />
                {[0, 1, 2, 3, 4].map(j => <Skeleton key={j} height={34} style={{ marginBottom: 8 }} />)}
              </div>
            ))}
          </div>
        )}

        {!loading && error && (
          <div style={{ padding: '16px 20px', background: 'var(--red-dim)', border: '1px solid rgba(248,81,73,0.2)', borderRadius: 12, color: 'var(--red)', fontSize: 13 }}>
            {error}
          </div>
        )}

        {!loading && !error && detail && (
          <>
            {detail.shots?.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 10 }}>
                  Shot Map
                </div>
                <ShotMap shots={detail.shots} homeTeam={detail.home_team} awayTeam={detail.away_team} />
              </div>
            )}
            {(detail.home_team.ppda != null || detail.away_team.ppda != null ||
              detail.home_team.field_tilt_pct != null || detail.away_team.field_tilt_pct != null) && (
              <div style={{ marginBottom: 24 }}>
                <TeamMetrics homeTeam={detail.home_team} awayTeam={detail.away_team} />
              </div>
            )}
            <div style={{ display: 'flex', gap: 24 }}>
              <TeamColumn team={detail.home_team} />
              <div style={{ width: 1, background: 'rgba(255,255,255,0.06)', flexShrink: 0 }} />
              <TeamColumn team={detail.away_team} />
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
