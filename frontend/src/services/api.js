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
  if (!res.ok) {
    const err = new Error(`${res.status} ${res.statusText}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

async function getAuthed(path, token) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function post(path) {
  const headers = currentToken ? { Authorization: `Bearer ${currentToken}` } : {};
  const res = await fetch(`${BASE}${path}`, { method: 'POST', headers });
  if (!res.ok) {
    const err = new Error(`${res.status} ${res.statusText}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

async function postJSON(path, body) {
  const headers = {
    'Content-Type': 'application/json',
    ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
  };
  const res = await fetch(`${BASE}${path}`, { method: 'POST', headers, body: JSON.stringify(body) });
  if (!res.ok) {
    const err = new Error(`${res.status} ${res.statusText}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export const getPlayerPerformance = () => get('/api/players/performance');
export const getFatigueRisk        = () => get('/api/players/fatigue-risk');
export const getSquadDepth         = () => get('/api/players/depth');
export const getMatchesSummary     = () => get('/api/matches/summary');
export const getTeamReadiness      = () => get('/api/team/readiness');
export const getTeamInfo           = () => get('/api/team/info');
export const getMatchDetail        = (matchId) => get(`/api/matches/${matchId}/detail`);
export const getPipelineStatus      = () => get('/api/pipeline/status');
export const triggerPipelineRefresh = () => post('/api/pipeline/refresh');

// Omit playerId to get every note the caller has authored, across all
// players -- powers the Scout's "My Scouting Notes" view.
export const getScoutingNotes  = (playerId) =>
  get(playerId != null ? `/api/scouting/notes?player_id=${playerId}` : '/api/scouting/notes');
export const postScoutingNote  = (playerId, note, rating) =>
  postJSON('/api/scouting/notes', { player_id: playerId, note, rating });
export const getPlayerStatuses = () => get('/api/players/status');
export const getPlayerRadar    = (playerId) => get(`/api/players/${playerId}/radar`);
export const postPlayerStatus  = (playerId, status, note) =>
  postJSON('/api/players/status', { player_id: playerId, status, note });
// previousQuestion/previousAnswer: the immediately preceding chat turn --
// short-term follow-up memory so a reply like "yes" after a clarifying
// question ("Did you mean Luis Suarez?") resolves correctly.
export const askAssistant = (question, previousQuestion, previousAnswer) =>
  postJSON('/api/ai/ask', {
    question,
    previous_question: previousQuestion,
    previous_answer: previousAnswer,
  });

// Kept as an explicit-token call (not the shared currentToken) -- Login.jsx
// needs the just-issued token's whoami result before AuthProvider's own
// listener has necessarily run, to decide which page to land on.
export const getWhoAmI = (token) => getAuthed('/api/whoami', token);
