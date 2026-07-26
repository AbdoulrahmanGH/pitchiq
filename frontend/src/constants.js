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
  FWD: { color: '#FF6B35', bg: 'rgba(255,107,53,0.12)'  },
};

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
