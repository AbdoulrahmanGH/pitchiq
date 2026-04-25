const BASE = 'http://localhost:8000';

async function get(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const getPlayerPerformance = () => get('/api/players/performance');
export const getFatigueRisk        = () => get('/api/players/fatigue-risk');
export const getSquadDepth         = () => get('/api/players/depth');
export const getMatchesSummary     = () => get('/api/matches/summary');
export const getTeamReadiness      = () => get('/api/team/readiness');
