const BASE = import.meta.env.VITE_API_BASE || 'https://pitchiq-backend-787059661234.europe-west1.run.app';

async function get(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function getAuthed(path, token) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const getPlayerPerformance = () => get('/api/players/performance');
export const getFatigueRisk        = () => get('/api/players/fatigue-risk');
export const getSquadDepth         = () => get('/api/players/depth');
export const getMatchesSummary     = () => get('/api/matches/summary');
export const getTeamReadiness      = () => get('/api/team/readiness');

export const getWhoAmI = (token) => getAuthed('/api/whoami', token);
