export const POS_ABBREV = {
  Goalkeeper: 'GK',
  Defender:   'DEF',
  Midfielder: 'MID',
  Forward:    'FWD',
};

export const POS_COLORS = {
  GK:  { color: '#58A6FF', bg: 'rgba(88,166,255,0.12)'  },
  DEF: { color: '#3FB950', bg: 'rgba(63,185,80,0.12)'   },
  MID: { color: '#A78BFA', bg: 'rgba(167,139,250,0.12)' },
  FWD: { color: '#FF5A1F', bg: 'rgba(255,90,31,0.12)'   },
};

// First + last initials for a player avatar badge -- used wherever a raw
// player_id would otherwise show (StatsBomb/DB ids are large and
// meaningless to a viewer, not jersey numbers).
export function initials(name) {
  const parts = name.trim().split(/\s+/);
  return parts.length === 1
    ? parts[0].slice(0, 2).toUpperCase()
    : (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

// The scouting rating scale, spelled out once so it's used consistently
// everywhere a rating is entered or displayed (write form legend, saved
// note cards, the My Scouting Notes list).
export const SCOUTING_RATING_LABELS = {
  1: 'Not recommended',
  2: 'Depth option',
  3: 'Squad rotation candidate',
  4: 'Strong prospect',
  5: 'Priority target',
};
