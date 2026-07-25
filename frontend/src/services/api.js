const BASE = import.meta.env.VITE_API_BASE || 'https://pitchiq-backend-787059661234.europe-west1.run.app';

// Set by AuthProvider whenever the Supabase session changes, so every call
// below automatically carries the current user's JWT -- callers don't pass
// a token around themselves.
let currentToken = null;
export function setAuthToken(token) {
  currentToken = token;
}

async function get(path) {
  const headers = currentToken ? { Authorization: `Bearer ${currentToken}` } : {};
  const res = await fetch(`${BASE}${path}`, { headers });
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

// Kept as an explicit-token call (not the shared currentToken) -- Login.jsx
// needs the just-issued token's whoami result before AuthProvider's own
// listener has necessarily run, to decide which page to land on.
export const getWhoAmI = (token) => getAuthed('/api/whoami', token);
